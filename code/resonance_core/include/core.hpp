#define DEBUG 1

// --- Main libraries
#include <iostream>
#include <vector>
#include <cmath>
#include <atomic> 
#include <string>
#include <iomanip> 
#include <thread>
#include <unistd.h>

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

// --- GUI/TUI related
#ifdef DEBUG
    #include "imgui.h"
    #include "imgui_impl_glfw.h"
    #include "imgui_impl_opengl3.h"
#endif

extern const char* CATALOGUE_PATH;   
extern const char* ZMQ_ENDPOINT;

extern std::atomic<bool> jsonLive;

// --- Loading file into a map memory
std::map<std::string, Json::Value> loadCatalogue(const std::string& file);

// --- Extrating the JSON objects
std::pair <std::string, std::string> jsonExtractor(const std::string& payload);

// --- Hearing the SDK connection
void jsonListenerThread();

// GUI/TUI DEBUG related. It will be wiped
#ifdef DEBUG
    void runGUI();
    void runTUI();
#endif