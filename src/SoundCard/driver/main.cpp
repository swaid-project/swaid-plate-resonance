#include <iostream>
#include <vector>
#include <cmath>
#include <atomic> 
#include <string>
#include <iomanip> // Used to format latency output

// --- Third-Party Libraries ---
#include "imgui.h"
#include "imgui_impl_glfw.h"
#include "imgui_impl_opengl3.h" // These libraries are needed for the minimalist look that the GUI contains
#include <GLFW/glfw3.h> // sudo apt install libglfw3-dev. Library for OpenGL
#include <portaudio.h> // sudo apt install portaudio19-dev. Audio processing I/O library

// --- Constants ---
const double PI = 3.14159265358979323846;
const int SAMPLE_RATE = 48000; // Obviusly this can be changed
const int FRAMES_PER_BUFFER = 256;
const int NUM_CHANNELS = 8; // Assuming a 7.1 soundcard

// --- Data Structures ---
struct Generator {
    std::atomic<float> freq{440.0f}; 
    std::atomic<float> ampL{0.0f};
    std::atomic<float> ampR{0.0f};
    std::atomic<float> phaseDegL{0.0f};
    std::atomic<float> phaseDegR{0.0f};

    // Internal state (Audio thread only)
    double currentBasePhase = 0.0;
};

// Global state
std::vector<Generator> generators(5); // Corresponding to each output
std::atomic<double> measuredLatency{0.0}; // To measure latency
std::atomic<bool> headsetMode{true}; // true: Stereo Mix, false: Independent HW Mapping
std::atomic<bool> masterMute{false}; // Safety kill switch
bool guiRunning = false;

// Helper function to reset all generators
void resetGenerators() {
    for (auto& gen : generators) {
        gen.freq.store(440.0f);
        gen.ampL.store(0.0f);
        gen.ampR.store(0.0f);
        gen.phaseDegL.store(0.0f);
        gen.phaseDegR.store(0.0f);
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

        float mixL = 0.0f;
        float mixR = 0.0f;
        int genIdx = 0;

        for (auto& gen : generators) {
            float f = gen.freq.load();
            float aL = gen.ampL.load();
            float aR = gen.ampR.load();
            float pL = gen.phaseDegL.load() * (PI / 180.0);
            float pR = gen.phaseDegR.load() * (PI / 180.0);

            double phaseIncrement = (2.0 * PI * f) / SAMPLE_RATE;
            gen.currentBasePhase += phaseIncrement;
            if (gen.currentBasePhase >= 2.0 * PI) gen.currentBasePhase -= 2.0 * PI;

            float sampleL = aL * std::sin(gen.currentBasePhase + pL);
            float sampleR = aR * std::sin(gen.currentBasePhase + pR);

            if (headsetMode.load()) {
                mixL += sampleL;
                mixR += sampleR;
            } else {
                if (genIdx < NUM_CHANNELS) {
                    out[i * NUM_CHANNELS + genIdx] = sampleL + sampleR;
                }
            }
            genIdx++;
        }

        if (headsetMode.load()) {
            out[i * NUM_CHANNELS + 0] = mixL;
            out[i * NUM_CHANNELS + 1] = mixR;
        }
    }
    return paContinue;
}

// --- Text User Interface (TUI) ---
void runTUI() {
    std::cout << "\n--- TUI Mode Activated ---\n";
    std::cout << "Commands: \n";
    std::cout << "  'set <id> <freq> <ampL> <ampR> <phaseL> <phaseR>'\n";
    std::cout << "  'mode <headset|hw>'\n";
    std::cout << "  'mute' / 'unmute'\n";
    std::cout << "  'reset' (Reset all generators to defaults)\n";
    std::cout << "  'status' / 'exit'\n";
    std::cout << "  'help' (Explains all the variables of 'set')";

    std::string cmd;
    while (true) {
        std::cout << "\n[Mute: " << (masterMute.load() ? "ON" : "OFF") 
                  << " | Latency: " << std::fixed << std::setprecision(2) << measuredLatency.load() << "ms] > ";
        
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
        else if (cmd == "status") {
            for(int i=0; i<5; i++) {
                std::cout << "Gen " << i << ": " << generators[i].freq.load() << "Hz | L:" 
                          << generators[i].ampL.load() << " R:" << generators[i].ampR.load() << "\n";
            }
        }
        else if (cmd == "set") {
            int id; float f, aL, aR, pL, pR;
            if (std::cin >> id >> f >> aL >> aR >> pL >> pR && id >= 0 && id < 5) {
                generators[id].freq.store(f);
                generators[id].ampL.store(aL);
                generators[id].ampR.store(aR);
                generators[id].phaseDegL.store(pL);
                generators[id].phaseDegR.store(pR);
            } else {
                std::cout << "Invalid input.\n";
                std::cin.clear(); std::cin.ignore(10000, '\n');
            }
        }
        else if (cmd == "help"){

            std::cout << "The following variables can be manipulated via 'set ...': \n";
            std::cout << "<id>     Generator ID.                    \t[0;1;2;3;4]\n";
            std::cout << "<freq>   Signal's frequency.              \t[20:24000] Hz \n";
            std::cout << "<amp*>   L/R Channel signal amplitude.   \t[0:1] \n";
            std::cout << "<phase*>  L/R Channel signal phase.   \t[0:360] º\n";
        }
    }
}

// --- Graphical User Interface (GUI) ---
void runGUI() {
    if (!glfwInit()) return;
    GLFWwindow* window = glfwCreateWindow(800, 600, "Multi-Channel Sine Generator", NULL, NULL);
    if (!window) return;
    glfwMakeContextCurrent(window);
    glfwSwapInterval(1);

    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGui_ImplGlfw_InitForOpenGL(window, true);
    ImGui_ImplOpenGL3_Init("#version 130");

    ImVec4 clear_color = ImVec4(0.45f, 0.55f, 0.60f, 1.00f);
    guiRunning = true;

    while (!glfwWindowShouldClose(window)) {
        glfwPollEvents();
        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();

        ImGui::Begin("Global Controls");
        
        // Master Mute
        bool isMuted = masterMute.load();
        if (isMuted) ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(1.0f, 0.0f, 0.0f, 1.0f));
        if (ImGui::Button(isMuted ? "UNMUTE ALL" : "MASTER MUTE", ImVec2(ImGui::GetContentRegionAvail().x * 0.5f, 40))) {
            masterMute.store(!isMuted);
        }
        if (isMuted) ImGui::PopStyleColor();

        ImGui::SameLine();

        // --- RESET BUTTON ---
        if (ImGui::Button("RESET ALL", ImVec2(ImGui::GetContentRegionAvail().x, 40))) {
            resetGenerators();
        }

        bool hMode = headsetMode.load();
        if (ImGui::Checkbox("Headset Monitoring Mode", &hMode)) headsetMode.store(hMode);
        
        ImGui::Text("System Latency: %.2f ms", measuredLatency.load());
        ImGui::End();

        ImGui::Begin("Sine Wave Generators");
        for (int i = 0; i < 5; i++) {
            ImGui::PushID(i);
            if (ImGui::CollapsingHeader(("Generator " + std::to_string(i + 1)).c_str(), ImGuiTreeNodeFlags_DefaultOpen)) {
                float f = generators[i].freq.load();
                float aL = generators[i].ampL.load(), aR = generators[i].ampR.load();
                float pL = generators[i].phaseDegL.load(), pR = generators[i].phaseDegR.load();

                if (ImGui::SliderFloat("Frequency (Hz)", &f, 20.0f, 24000.0f, "%.1f", ImGuiSliderFlags_Logarithmic)) generators[i].freq.store(f);
                if (ImGui::SliderFloat("Amplitude L", &aL, 0.0f, 1.0f, "%.3f")) generators[i].ampL.store(aL);
                if (ImGui::SliderFloat("Amplitude R", &aR, 0.0f, 1.0f, "%.3f")) generators[i].ampR.store(aR);
                if (ImGui::SliderFloat("Phase L (deg)", &pL, 0.0f, 360.0f, "%.1f")) generators[i].phaseDegL.store(std::fmod(pL, 360.0f));
                if (ImGui::SliderFloat("Phase R (deg)", &pR, 0.0f, 360.0f, "%.1f")) generators[i].phaseDegR.store(std::fmod(pR, 360.0f));
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
    // Cleanup...
}

int main() {
    Pa_Initialize();
    PaStream *stream;
    Pa_OpenDefaultStream(&stream, 0, NUM_CHANNELS, paFloat32, SAMPLE_RATE, FRAMES_PER_BUFFER, audioCallback, nullptr);
    Pa_StartStream(stream);

    std::cout << "Select Mode:\n[1] GUI\n[2] TUI\nChoice: ";
    int choice; std::cin >> choice;

    if (choice == 1) runGUI();
    else runTUI();

    Pa_StopStream(stream);
    Pa_Terminate();
    return 0;
}