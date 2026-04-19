#include <iostream>
#include <vector>
#include <cmath>
#include <atomic> // To avoid data races
#include <string>
#include <iomanip> // Used to format latency output
#include <thread>
#include <unistd.h>

// --- Third-Party Libraries ---
#include "imgui.h"
#include "imgui_impl_glfw.h"
#include "imgui_impl_opengl3.h" // These libraries are needed for the minimalist look that the GUI contains
#include <GLFW/glfw3.h> // sudo apt install libglfw3-dev. Library for OpenGL
#include <portaudio.h> // sudo apt install portaudio19-dev. Audio processing I/O library

// --- IPC communication
#include "json_driver_interface.h"
#include <sys/mman.h>
#include <fcntl.h>

// --- Constants ---
const double PI = 3.14159265358979323846;
const int SAMPLE_RATE = 48000; // Obviusly this can be changed
const int FRAMES_PER_BUFFER = 256;

// 7.1 Variant
//const int NUM_CHANNELS = 8; 
//const int NUM_GENERATORS = 8; // One independent generator per physical output channel 

// 5.1 Variant
const int NUM_CHANNELS = 6; 
const int NUM_GENERATORS = 6; // One independent generator per physical output channel

const char* CH_LABEL[NUM_GENERATORS] = {
    "Front L", "Front R",
    "Center ", "Subwoof",
    "Rear  L", "Rear  R",
    // "Side L", "Side R", // Waiting for the 7.1 Soundcard
};

// --- Data Structures ---

struct Generator {
    std::atomic<float> freq{440.0f};
    std::atomic<float> amp{0.0f};
    std::atomic<float> phaseDeg{0.0f};

    // Internal state (Audio thread only)
    double currentBasePhase = 0.0;
};

// Global state
std::vector<Generator> generators(NUM_GENERATORS); // One per physical output channel
std::atomic<double> measuredLatency{0.0}; // To measure latency
std::atomic<bool> headsetMode{true}; // true: fold all channels into Front L/R for monitoring, false: Independent HW Mapping
std::atomic<bool> masterMute{false}; // Safety kill switch
std::atomic<bool> shmMode{false};

bool guiRunning = false;


// --- IPC to JSON extractor communication
SharedBlock* shm = nullptr;
uint32_t lastGen = 0; // To compare between the current status and the one being inserted in the shared memory

SharedBlock* attachShm() {
    int fd = shm_open(SHM_NAME, O_RDWR, 0666); // It's guaranteed to exist
    if (fd == -1) { 
	    std::cerr << "SHM not found — is the sender running?\n"; 
	    return nullptr; 
    }
    
    auto* blk = (SharedBlock*)mmap(nullptr, sizeof(SharedBlock), PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);

    close(fd);
    lastGen = blk->generation;
    return blk;
}


// Call this wherever you want to apply a new pattern — e.g. a button in the GUI
void applyFromShm(SharedBlock* blk) {
    sem_wait(&blk->mutex);
    for (int i = 0; i < NUM_TRANSDUCERS; i++) {
        generators[i].freq.store(    blk->transducers[i].freq);
        generators[i].amp.store(     blk->transducers[i].amp);
        generators[i].phaseDeg.store(blk->transducers[i].phaseDeg);
    }
    sem_post(&blk->mutex);
}

void pollShm(){
    if (!shm)
	shm = attachShm();
    if (shm && shmMode.load() && shm->generation != lastGen){
        applyFromShm(shm); // As soon as possible, extract the values from SHM
	lastGen = shm->generation;
    }

}

// Helper function to reset all generators
void resetGenerators() {
    for (auto& gen : generators) {
        gen.freq.store(440.0f);
        gen.amp.store(0.0f);
        gen.phaseDeg.store(0.0f);
        gen.currentBasePhase = 0.0; // Reset internal phase to prevent clicks
    }
}

// --- Audio Callback ---
static int audioCallback(const void *inputBuffer, void *outputBuffer,
                         unsigned long framesPerBuffer,
                         const PaStreamCallbackTimeInfo* timeInfo,
                         PaStreamCallbackFlags statusFlags,
                         void *userData) {

    measuredLatency.store((timeInfo->outputBufferDacTime - timeInfo->currentTime) * 1000.0); // Multiplied by 1000 to obtain the result in ms

    float *out = (float*)outputBuffer;
    (void) inputBuffer;

    for (unsigned int i = 0; i < framesPerBuffer; i++) {
        for (int ch = 0; ch < NUM_CHANNELS; ch++) out[i * NUM_CHANNELS + ch] = 0.0f;

        if (masterMute.load()) continue;

        bool hMode = headsetMode.load();
        float monitorL = 0.0f;
        float monitorR = 0.0f;

        for (int genIdx = 0; genIdx < NUM_GENERATORS; genIdx++) {
            auto& gen = generators[genIdx];

            // Lines that store the current values being inserted
            float f = gen.freq.load();
            float a = gen.amp.load();
            float p = gen.phaseDeg.load() * (PI / 180.0);

            double phaseIncrement = (2.0 * PI * f) / SAMPLE_RATE;
            gen.currentBasePhase += phaseIncrement;
            if (gen.currentBasePhase >= 2.0 * PI) gen.currentBasePhase -= 2.0 * PI;

            float sample = a * std::sin(gen.currentBasePhase + p);

            if (hMode) {
                // Fold into Front L/R for headset monitoring: even-indexed channels go L, odd go R
                if (genIdx % 2 == 0) monitorL += sample;
                else                 monitorR += sample;
            } else {
                // Each generator drives its own physical output channel directly
                out[i * NUM_CHANNELS + genIdx] = sample;
            }
        }

        if (hMode) {
            out[i * NUM_CHANNELS + 0] = monitorL;
            out[i * NUM_CHANNELS + 1] = monitorR;
        }
    }
    return paContinue;
}

// --- Text User Interface (TUI) ---
void runTUI() {
    std::cout << "\n--- TUI Mode Activated ---\n";
    std::cout << "Commands: \n";
    std::cout << "  'set <id> <freq> <amp> <phase>'\n";
    std::cout << "  'mode <headset|hw>'\n";
    std::cout << "  'mute' / 'unmute'\n";
    std::cout << "  'reset' (Reset all generators to defaults)\n";
    std::cout << "  'shm <on|off>' (Live IPC mode - receive patterns from json_caller)\n";
    std::cout << "  'status' / 'exit'\n";
    std::cout << "  'help' (Explains all the variables of 'set')";

    std::atomic<bool> tuiRunning{true};
    std::thread shmPoller([&]() {
        while (tuiRunning.load()) {
            pollShm();
            std::this_thread::sleep_for(std::chrono::milliseconds(20)); // ~50Hz poll
        }
    });

    std::string cmd;
    while (true) {
        std::cout << "\n[Mute: " << (masterMute.load() ? "ON" : "OFF") 
                  << " | Latency: " << std::fixed << std::setprecision(2) << measuredLatency.load() << "ms] > " << " | SHM: " << (shmMode.load() ? "ON" : "OFF") << "] > "; 
        
        if (!(std::cin >> cmd)) break;
        
        if (cmd == "exit") break;
        else if (cmd == "mute") masterMute.store(true);
        else if (cmd == "unmute") masterMute.store(false);
        else if (cmd == "reset") {
            resetGenerators();
            std::cout << "All generators reset to default values.\n";
        }
        else if (cmd == "mode") {
            std::string m; std::cin >> m;
            if (m == "headset") headsetMode.store(true);
            else if (m == "hw") headsetMode.store(false);
            std::cout << "Mode updated.\n";
        }
	else if (cmd == "shm") {
            std::string m; std::cin >> m;
            if (m == "on") {
                if (!shm) std::cerr << "SHM not attached — start json_caller first.\n";
                else { shmMode.store(true);  std::cout << "Live IPC mode ON.\n"; }
            } else if (m == "off") {
                shmMode.store(false);
                std::cout << "Live IPC mode OFF.\n";
            }
        }
        else if (cmd == "status") {
            for (int i = 0; i < NUM_GENERATORS; i++) {
                std::cout << "Gen " << i << " [" << CH_LABEL[i] << "]: "
                          << generators[i].freq.load() << "Hz | Amp:"
                          << generators[i].amp.load() << " Phase:"
                          << generators[i].phaseDeg.load() << "deg\n";
            }
        }
        else if (cmd == "set") {
            int id; float f, a, p;
            if (std::cin >> id >> f >> a >> p && id >= 0 && id < NUM_GENERATORS) {
                generators[id].freq.store(f);
                generators[id].amp.store(a);
                generators[id].phaseDeg.store(p);
            } else {
                std::cout << "Invalid input.\n";
                std::cin.clear(); std::cin.ignore(10000, '\n');
            }
        }
        else if (cmd == "help") {
            std::cout << "The following variables can be manipulated via 'set ...': \n";
            std::cout << "<id>     Generator ID (one per physical output channel).\n";
            for (int i = 0; i < NUM_GENERATORS; i++)
                std::cout << "         " << i << " = ch" << i << " [" << CH_LABEL[i] << "]\n";
            std::cout << "<freq>   Signal's frequency.             \t[20:24000] Hz \n";
            std::cout << "<amp>    Signal amplitude.               \t[0:1] \n";
            std::cout << "<phase>  Signal phase.                   \t[0:360] º\n";
        }
    }
    tuiRunning.store(false);
    shmPoller.join();
}

// --- Graphical User Interface (GUI) ---
void runGUI() {
    if (!glfwInit()) return;
    GLFWwindow* window = glfwCreateWindow(900, 800, "Multi-Channel Sine Generator", NULL, NULL);
    if (!window) return;
    glfwMakeContextCurrent(window);
    glfwSwapInterval(1);

    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGui_ImplGlfw_InitForOpenGL(window, true);
    ImGui_ImplOpenGL3_Init("#version 130");

    ImVec4 clear_color = ImVec4(0.10f, 0.10f, 0.12f, 1.00f);

    while (!glfwWindowShouldClose(window)) {
        glfwPollEvents();
        pollShm();
        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();

        ImGui::Begin("Global Controls");
        bool isMuted = masterMute.load();
        if (isMuted) ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.8f, 0.1f, 0.1f, 1.0f));
        if (ImGui::Button(isMuted ? "UNMUTE ALL" : "MASTER MUTE", ImVec2(ImGui::GetContentRegionAvail().x * 0.5f, 40))) {
            masterMute.store(!isMuted);
        }
        if (isMuted) ImGui::PopStyleColor();

        ImGui::SameLine();

        if (ImGui::Button("RESET ALL", ImVec2(ImGui::GetContentRegionAvail().x, 40))) {
            resetGenerators();
        }

        bool hMode = headsetMode.load();
        if (ImGui::Checkbox("Headset Monitoring Mode", &hMode)) headsetMode.store(hMode);

	bool sMode = shmMode.load();
        if (ImGui::Checkbox("Live IPC Mode (receive from json_caller)", &sMode)) {
            if (sMode && !shm)
	            shm = attachShm();
            if (sMode && !shm)
                ImGui::SetTooltip("SHM not attached — start json_caller first.");
            else
                shmMode.store(sMode);
        }
        if (shmMode.load()) {
            ImGui::SameLine();
            ImGui::TextColored(ImVec4(0.0f, 1.0f, 0.4f, 1.0f), "LIVE");
        }
        ImGui::Text("System Latency: %.2f ms", measuredLatency.load());
        ImGui::End();


        
        ImGui::Begin("Sine Wave Generators");
        for (int i = 0; i < NUM_GENERATORS; i++) {
            ImGui::PushID(i);
            std::string header = "ch" + std::to_string(i) + "  " + CH_LABEL[i];
            if (ImGui::CollapsingHeader(header.c_str(), ImGuiTreeNodeFlags_DefaultOpen)) {
                float f = generators[i].freq.load();
                float a = generators[i].amp.load();
                float p = generators[i].phaseDeg.load();

                if (ImGui::SliderFloat("Frequency (Hz)", &f, 20.0f, 24000.0f, "%.1f", ImGuiSliderFlags_Logarithmic)) generators[i].freq.store(f);
                if (ImGui::SliderFloat("Amplitude",      &a, 0.0f,  1.0f,     "%.3f"))                               generators[i].amp.store(a);
                if (ImGui::SliderFloat("Phase (deg)",    &p, 0.0f,  360.0f,   "%.1f"))                               generators[i].phaseDeg.store(std::fmod(p, 360.0f));
            }
            
            ImGui::PopID();
        }
        
        ImGui::End();

        ImGui::Render();
        int dw, dh; glfwGetFramebufferSize(window, &dw, &dh);
        glViewport(0, 0, dw, dh);
        glClearColor(clear_color.x, clear_color.y, clear_color.z, clear_color.w);
        glClear(GL_COLOR_BUFFER_BIT);
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        glfwSwapBuffers(window);
    }
    
    ImGui_ImplOpenGL3_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();
    glfwDestroyWindow(window);
    glfwTerminate();
}

// --- Audio Device Selection ---
int selectAudioDevice() {
    int numDevices = Pa_GetDeviceCount();
    std::cout << "\nAvailable audio devices:\n";
    for (int i = 0; i < numDevices; i++) {
        const PaDeviceInfo* info = Pa_GetDeviceInfo(i);
        if (info->maxOutputChannels >= NUM_CHANNELS)
            std::cout << "  [" << i << "] " << info->name 
                      << " (out: " << info->maxOutputChannels << "ch)\n";
    }
    std::cout << "Select device index: ";
    int choice; std::cin >> choice;
    return choice;
}

int main() {
    Pa_Initialize();
    PaStream *stream;
    
    int deviceIdx = selectAudioDevice();
    const PaDeviceInfo* deviceInfo = Pa_GetDeviceInfo(deviceIdx);
    
    PaStreamParameters outputParams;
    outputParams.device                    = deviceIdx;
    outputParams.channelCount              = NUM_CHANNELS;
    outputParams.sampleFormat              = paFloat32;
    outputParams.suggestedLatency          = deviceInfo->defaultLowOutputLatency;
    outputParams.hostApiSpecificStreamInfo = nullptr;
    Pa_OpenStream(&stream, nullptr, &outputParams, SAMPLE_RATE, FRAMES_PER_BUFFER, paNoFlag, audioCallback, nullptr);

    Pa_StartStream(stream);
    
    shm = attachShm();
    if (!shm) 
        std::cout << "SHM not available yet — start json_caller before enabling Live IPC.\n";

    std::cout << "Select Mode:\n[1] GUI\n[2] TUI\nChoice: ";
    int choice; std::cin >> choice;

    if (choice == 1) runGUI();
    else runTUI();

    Pa_StopStream(stream);
    Pa_CloseStream(stream);
    Pa_Terminate();

    if (shm){
        munmap(shm, sizeof(SharedBlock));
        shm_unlink(SHM_NAME);
    }

    return 0;
}
