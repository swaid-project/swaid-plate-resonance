// --- JSON related
#include <map>          
#include <sys/inotify.h>
#include <jsoncpp/json/json.h>
#include <fstream>
#include <sstream>

// --- ZeroMQ communication
#include <chrono>
#include <limits>
#include <zmq.hpp>

const char* CATALOGUE_PATH = "json_files/catalogue.json";   
const char* ZMQ_ENDPOINT   = "ipc:///tmp/swaid.sock";

std::map<std::string, Json::Value> loadCatalogue(const std::string& file);
std::pair <std::string, std::string> jsonExtractor(const std::string& payload);
void jsonListenerThread();