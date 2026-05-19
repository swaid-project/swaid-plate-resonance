
// --- Main libraries
#include <iostream>
#include <vector>
#include <cmath>
#include <atomic> 
#include <string>
#include <iomanip> 
#include <thread>
#include <unistd.h>

// --- Audio related
#include <GLFW/glfw3.h> // sudo apt install libglfw3-dev. Library for OpenGL
#include <portaudio.h> // sudo apt install portaudio19-dev. Audio processing I/O library

// --- Global state 
std::vector<Generator> generators(NUM_GENERATORS); // One per physical output channel
std::atomic<double> measuredLatency{0.0}; // To measure latency
std::atomic<bool> headsetMode{true}; // true: fold all channels into Front L/R for monitoring, false: Independent HW Mapping
std::atomic<bool> masterMute{false}; // Safety kill switch
std::atomic<bool> jsonLive{false};

// --- Constants 
const double PI = 3.14159265358979323846;
const int SAMPLE_RATE = 48000; // Obviusly this can be changed
const int FRAMES_PER_BUFFER = 256;

// --- 7.1 characteristics
const int NUM_CHANNELS    = 8; 
const int NUM_GENERATORS  = 8; 
const int NUM_TRANSDUCERS = 4;

// --- 7.1 channels
const char* CH_LABEL[NUM_GENERATORS] = {
    "Front L", "Front R",
    "Center" , "Subwoof",
    "Rear L" , "Rear R" ,
    "Side L" , "Side R" , 
};

// --- Data Structures ---
struct Generator {
    std::atomic<float> freq{440.0f};
    std::atomic<float> amp{0.0f};
    std::atomic<float> phaseDeg{0.0f};

    // Internal state (Audio thread only)
    double currentBasePhase = 0.0;
};

// --- Duration for the amplitude for fade
int fadeDurationMs(const std::string& t);

// --- Sending the pattern to the soundcard generators
void applyPattern(const std::map<std::string, Json::Value>& catalogue, const std::string& symbol_id, const std::string& fade_transition);

// --- Helper function to reset all generators
void resetGenerators();

// --- Audio callback
static int audioCallback(const void *inputBuffer, 
                         void *outputBuffer,
                         unsigned long framesPerBuffer,
                         const PaStreamCallbackTimeInfo* timeInfo,
                         PaStreamCallbackFlags statusFlags,
                         void *userData);

// --- Audio Device Selection
int selectAudioDevice();


                         




