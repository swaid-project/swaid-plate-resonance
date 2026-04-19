//if include <json/value.h> line fails (latest kernels), try also:
//  #include <jsoncpp/json/json.h>

#include <cstring>
#include <jsoncpp/json/json.h>
#include <fstream>
#include <iostream>
#include <atomic>
#include <map>

// -- Used to the IPC (shared memory) between this JSON extractor and exporter and the SoundGenerator driver
#include "json_driver_interface.h"
#include "sys/mman.h"
#include "sys/stat.h"
#include <fcntl.h>
#include <unistd.h> 

using namespace std;

struct Export_Data{
    float freq;
    float amp;
    float phaseDeg;

    // Internal state (Audio thread only)
    double currentBasePhase = 0.0;
};

// -- IPC shared memory 

SharedBlock* openShm() {
    bool firstTime = false;
    int fd = shm_open(SHM_NAME, O_CREAT | O_RDWR, 0666);
    
    struct stat st;
    fstat(fd,&st);
    firstTime = (st.st_size == 0);

    ftruncate (fd, sizeof(SharedBlock)); // To change the size of the opened shared memory
    auto* blk = (SharedBlock*)mmap(nullptr, sizeof(SharedBlock), PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0); // To manipulate the opened shared memory
    close(fd);

    if (firstTime) {
	sem_init(&blk->mutex,1,1); // Works across processes
	blk->generation = 0;
    }

    return blk;
}

void writeToShm(SharedBlock* blk, const array<Export_Data, 4>& transducers) {
    sem_wait(&blk->mutex);
    for (int i = 0; i < 4; i++) {
        blk->transducers[i].freq     = transducers[i].freq;
        blk->transducers[i].amp      = transducers[i].amp;
        blk->transducers[i].phaseDeg = transducers[i].phaseDeg;
    }
    blk->generation++;
    sem_post(&blk->mutex);
}

// -- JSON navigating and mapping
map <string, Json::Value> loadCatalogue(const string& file) {

    ifstream message_file(file, ifstream::binary);

    if (!message_file.is_open()) {
        cerr << "Could not open catalogue.\n";
        return {};
    }

    Json::Value root;
    message_file >> root;

    map <string, Json::Value> catalogue;

    for (const auto& key : root.getMemberNames()) // to go through the indexes
        catalogue[key] = root[key];

    return catalogue;
}

pair <string, string> jsonExtractor(const string& file){
    
    ifstream message_file(file, ifstream::binary);

    if (!message_file.is_open()) {
        cerr << "Could not open catalogue.\n";
        return {};
    }

    Json::Value message;
    message_file >> message;

    string symbol, transition_time;


        // cout << message << "\n" ; //This will print the entire json object.

    if (message["message_type"] == "trigger") {
        
        symbol = message["command"]["symbol_id"].asString();
        transition_time = message["command"]["transition_time_ms"].asString();
        return {symbol,transition_time};


    }  else {
        cerr << "There is no valid message \n";
	return {};
    }

}


array <Export_Data,4> jsonSearch(const map <string, Json::Value>& catalogue, string const& symbol_id){

    auto it = catalogue.find(symbol_id);

    if (it == catalogue.end()) {
        std::cerr << "Pattern '" << symbol_id << "' not found.\n";
        return {};
    }

    const Json::Value& pattern = it->second; 

    array <Export_Data,4> transducers {};

    cout << "Found it!" << "\n" ;

    for (const auto& t : pattern["hardware_config"]["transducers"]){
	int idx = t["channel"].asInt() - 1; 

        transducers[idx].freq =  t["frequency_hz" ].asFloat();
        transducers[idx].amp  =  t["amplitude" ].asFloat();
        transducers[idx].phaseDeg = t["phase_deg" ].asFloat();
    }

    for (int i = 0; i < 4; i++){
	cout << "======================= Channel "<< i << " =======================\n";
	cout << "Frequency of the channel: " << transducers[i].freq << "\n";
	cout << "Amplitude of the channel: " << transducers[i].amp<< "\n";
	cout << "Phase of the channel    : " << transducers[i].phaseDeg << "\n";
    }



    return transducers;
}


int main () {

    auto* shm = openShm();

    auto catalogue = loadCatalogue("json_test/catalogue.json"); // It loads the catalogue containing all info from the possible symbols to the program's memory
    auto [symbol,transition_time] = jsonExtractor("json_test/trigger_test.json"); // Fetchs the SymbolID from the sent JSON message
    array <Export_Data,4> transducers = jsonSearch(catalogue,symbol); // Stores in a 4-sized all transducers needed values to export to the driver
    
    writeToShm(shm, transducers);
    munmap(shm,sizeof(SharedBlock)); // Deletes the address range specified
    //shm_unlink(SHM_NAME); // Cleaning up

    return 0;
}

