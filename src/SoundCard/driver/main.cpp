#include <iostream>
#include <vector>
#include <cmath>
#include <atomic>
#include <string>
#include <iomanip> // Used to format latency output

// --- Third-Party Libraries ---
// You will need to make sure these are correctly included and linked
#include "imgui.h"
#include "imgui_impl_glfw.h"
#include "imgui_impl_opengl3.h"
#include <GLFW/glfw3.h> // sudo apt install libglfw3-dev. Library for OpenGL
#include <portaudio.h> // sudo apt install portaudio19-dev. Audio processing I/O library

// --- Constants ---
const double PI = 3.14159265358979323846;
const int SAMPLE_RATE = 48000;
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
std::vector<Generator> generators(5);
std::atomic<double> measuredLatency{0.0}; // To measure latency
bool guiRunning = false;

// --- Audio Callback ---
static int audioCallback(const void *inputBuffer, void *outputBuffer,
                         unsigned long framesPerBuffer,
                         const PaStreamCallbackTimeInfo* timeInfo,
                         PaStreamCallbackFlags statusFlags,
                         void *userData) {

    measuredLatency.store((timeInfo->outputBufferDacTime - timeInfo->currentTime) * 1000.0);
    float *out = (float*)outputBuffer;
    (void) inputBuffer;

    for (unsigned int i = 0; i < framesPerBuffer; i++) {
        float mixL = 0.0f;
        float mixR = 0.0f;

        for (auto& gen : generators) {
            float f = gen.freq.load();
            float aL = gen.ampL.load();
            float aR = gen.ampR.load();
            float pL = gen.phaseDegL.load() * (PI / 180.0);
            float pR = gen.phaseDegR.load() * (PI / 180.0);

            // Phase calculation:
            double phaseIncrement = (2.0 * PI * f) / SAMPLE_RATE;
            gen.currentBasePhase += phaseIncrement;
            if (gen.currentBasePhase >= 2.0 * PI) {
                gen.currentBasePhase -= 2.0 * PI;
            }

            mixL += aL * std::sin(gen.currentBasePhase + pL);
            mixR += aR * std::sin(gen.currentBasePhase + pR);
        }

        // Simple channel mapping to Front Left (0) and Front Right (1)
        out[i * NUM_CHANNELS + 0] = mixL;
        out[i * NUM_CHANNELS + 1] = mixR;

        // Zero other channels (2-7)
        for (int ch = 2; ch < NUM_CHANNELS; ch++) {
            out[i * NUM_CHANNELS + ch] = 0.0f;
        }
    }
    return paContinue;
}

// --- Text User Interface (TUI) ---
void runTUI() {
    std::cout << "\n--- TUI Mode Activated ---\n";
    std::cout << "Commands: \n";
    std::cout << "  'set <id> <freq> <ampL> <ampR> <phaseL> <phaseR>'\n";
    std::cout << "  'status' (to see latency and current values)\n";
    std::cout << "  'exit'\n";

    std::string cmd;
    while (true) {
        std::cout << "\n[Latency: " << std::fixed << std::setprecision(2) << measuredLatency.load() << "ms] > ";
        if (!(std::cin >> cmd)) break;
        
        if (cmd == "exit") break;
        else if (cmd == "status") {
            std::cout << "\n--- Current Status ---\n";
            std::cout << "Reported Latency: " << measuredLatency.load() << " ms\n";
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
                std::cout << "Updated Generator " << id << "\n";
            } else {
                std::cout << "Invalid input.\n";
                std::cin.clear(); std::cin.ignore(10000, '\n');
            }
        }
    }
}

// --- Graphical User Interface (GUI) with Dear ImGui ---
static void glfw_error_callback(int error, const char* description) {
    fprintf(stderr, "Glfw Error %d: %s\n", error, description);
}

void runGUI() {
    // 1. Initialize GLFW
    glfwSetErrorCallback(glfw_error_callback);
    if (!glfwInit()) return;

    // Decide GL+GLSL versions
    const char* glsl_version = "#version 130";
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 0);

    // Create window with graphics context
    GLFWwindow* window = glfwCreateWindow(800, 600, "Multi-Channel Sine Generator", NULL, NULL);
    if (window == NULL) return;
    glfwMakeContextCurrent(window);
    glfwSwapInterval(1); // Enable vsync

    // 2. Initialize Dear ImGui
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO(); (void)io;
    //io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard; // Enable Keyboard Controls

    // Setup Dear ImGui style
    ImGui::StyleColorsDark();

    // Setup Platform/Renderer backends
    ImGui_ImplGlfw_InitForOpenGL(window, true);
    ImGui_ImplOpenGL3_Init(glsl_version);

    // Our state for the GUI
    ImVec4 clear_color = ImVec4(0.45f, 0.55f, 0.60f, 1.00f);

    // 3. Main Loop
    guiRunning = true;
    while (!glfwWindowShouldClose(window)) {
        glfwPollEvents();

        // Start the Dear ImGui frame
        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();

        // --- Our GUI Window ---
        ImGui::Begin("Sine Wave Generators");

        // Latency Monitor Display
        double lat = measuredLatency.load();
        ImGui::TextColored(ImVec4(0.0f, 1.0f, 0.0f, 1.0f), "System Latency: %.2f ms", lat);
        
        if (lat > 20.0) {
            ImGui::TextColored(ImVec4(1.0f, 0.5f, 0.0f, 1.0f), "Warning: High Latency (Check USB Buffer)");
        }

        ImGui::Text("Frequency Range: 20Hz - 24000Hz");
        ImGui::Text("7.1 USB Output (5 Logical Channels Mixed to FL/FR)");
        ImGui::Separator();

        for (int i = 0; i < 5; i++) {
            ImGui::PushID(i);
            std::string genName = "Generator " + std::to_string(i + 1);
            if (ImGui::CollapsingHeader(genName.c_str(), ImGuiTreeNodeFlags_DefaultOpen)) {
                // Get current values
                float f = generators[i].freq.load();
                float aL = generators[i].ampL.load();
                float aR = generators[i].ampR.load();
                float pL = generators[i].phaseDegL.load();
                float pR = generators[i].phaseDegR.load();

                // Create sliders for each parameter
                if (ImGui::SliderFloat("Frequency (Hz)", &f, 20.0f, 24000.0f, "%.1f", ImGuiSliderFlags_Logarithmic))
                    generators[i].freq.store(f);

                if (ImGui::SliderFloat("Amplitude Left", &aL, 0.0f, 1.0f, "%.3f"))
                    generators[i].ampL.store(aL);

                if (ImGui::SliderFloat("Amplitude Right", &aR, 0.0f, 1.0f, "%.3f"))
                    generators[i].ampR.store(aR);

                if (ImGui::SliderFloat("Phase Left (deg)", &pL, 0.0f, 360.0f, "%.1f"))
                    generators[i].phaseDegL.store(std::fmod(pL, 360.0f));

                if (ImGui::SliderFloat("Phase Right (deg)", &pR, 0.0f, 360.0f, "%.1f"))
                    generators[i].phaseDegR.store(std::fmod(pR, 360.0f));

                ImGui::Separator();
            }
            ImGui::PopID();
        }

        if (ImGui::Button("Exit Application")) {
            glfwSetWindowShouldClose(window, true);
        }

        ImGui::End();

        // --- Rendering ---
        ImGui::Render();
        int display_w, display_w_height;
        glfwGetFramebufferSize(window, &display_w, &display_w_height);
        glViewport(0, 0, display_w, display_w_height);
        glClearColor(clear_color.x, clear_color.y, clear_color.z, clear_color.w);
        glClear(GL_COLOR_BUFFER_BIT);
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());

        glfwSwapBuffers(window);
    }

    // 4. Cleanup
    ImGui_ImplOpenGL3_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();

    glfwDestroyWindow(window);
    glfwTerminate();
    guiRunning = false;
}

// --- Main ---
int main() {
    // 1. Initialize Audio
    PaError err = Pa_Initialize();
    if (err != paNoError) {
        std::cerr << "PortAudio error: " << Pa_GetErrorText(err) << "\n";
        return 1;
    }

    PaStream *stream;
    err = Pa_OpenDefaultStream(&stream,
                               0,               // No input
                               NUM_CHANNELS,    // 8 output channels
                               paFloat32,       // 32-bit float
                               SAMPLE_RATE,
                               FRAMES_PER_BUFFER,
                               audioCallback,
                               nullptr);

    if (err != paNoError) {
        std::cerr << "Failed to open audio stream: " << Pa_GetErrorText(err) << "\n";
        Pa_Terminate();
        return 1;
    }

    Pa_StartStream(stream);

    // 2. Prompt for UI mode
    std::cout << "Select Interface Mode:\n";
    std::cout << "[1] GUI\n";
    std::cout << "[2] TUI\n";
    std::cout << "Choice: ";

    int choice;
    if (!(std::cin >> choice)) {
        choice = 2; // Default to TUI
    }

    if (choice == 1) {
        runGUI();
    } else {
        runTUI();
    }

    // 3. Cleanup
    Pa_StopStream(stream);
    Pa_CloseStream(stream);
    Pa_Terminate();

    std::cout << "Audio stream closed. Exiting.\n";
    return 0;
}