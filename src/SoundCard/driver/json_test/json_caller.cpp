//if include <json/value.h> line fails (latest kernels), try also:
//  #include <jsoncpp/json/json.h>

#include <cstring>
#include <jsoncpp/json/json.h>
#include <fstream>
#include <iostream>
using namespace std;

struct Export_Data{
    std::atomic<float> freq;
    std::atomic<float> amp;
    std::atomic<float> phaseDeg;

    // Internal state (Audio thread only)
    double currentBasePhase = 0.0;
};

pair <string, string> json_extracter(string file){
    std::ifstream message_file(file, std::ifstream::binary);
    Json::Value message;
    message_file >> message;

    string symbol, transition_time;


        cout << message << "\n" ; //This will print the entire json object.
				  //
        //The following lines will let you access the indexed objects.
        cout << message["message_type"] << "\n"; 
        cout << message["timestamp"] << "\n"; 

    if (message["message_type"] == "trigger") {

        cout << message["command"]["symbol_id"] << "\n"; 
        cout << message["command"]["led_id"] << "\n"; 
        cout << message["command"]["transition_time_ms"] << "\n"; 
        cout << message["command"]["volume_percent"] << "\n"; 

        cout << message["sound"] << "\n"; //NULL! There is no element with key "profession". Hence a new empty element will be created.

        symbol = message["command"]["symbol_id"].asString();
        transition_time = message["command"]["transition_time_ms"].asString();


    } else if (message["message_type"] ==  "config_update") {

        cout << message["activate_catalog"] << "\n"; 

        cout << message["sound"] << "\n"; //NULL! There is no element with key "profession". Hence a new empty element will be created.
	

    } else {
        cout << "There is no valid message" << "\n";
    }

   return {symbol,transition_time};
}

int json_search(string file, string symbol_id){
    std::ifstream message_file(file, std::ifstream::binary);
    Json::Value catalogue;
    message_file >> catalogue;

    Export_Data channel[4];


    if (!catalogue.isMember(symbol_id)) {
        std::cerr << "Pattern '" << symbol_id << "' not found.\n";
        return Json::nullValue;
    }

    cout << "Found it!" << "\n";

    for (int i = 0; i < 4; i++){
        channel[i].freq.store(catalogue[symbol_id]["hardware_config"]["tranduscers"]);
        channel[i].amp.store(catalogue[symbol_id]["hardware_config"]["tranduscers"]);
        channel[i].phaseDeg.store(catalogue[symbol_id]["hardware_config"]["tranduscers"]);
    }


    return 0;
}

int main () {


	auto [symbol,transition_time] = json_extracter("trigger_test.json");
    json_extracter("config_test.json");
    json_search("catalogue.json",symbol);
	return 0;
}

