#include "../include/core.hpp"
#include "../../soundcard/include/audio_driver.hpp"

// --- Loading file into a map memory
std::map<std::string, Json::Value> loadCatalogue(const std::string& file) {

    std::ifstream f(file, std::ifstream::binary);

    if (!f.is_open()) { 
        std::cerr << "Could not open catalogue: " << file << "\n"; 
        return {}; 
    }

    Json::Value root;
    f >> root;

    std::map<std::string, Json::Value> catalogue;

    for (const auto& key : root.getMemberNames())
        catalogue[key] = root[key];

    return catalogue;
}

// --- Extrating the JSON objects
std::pair <std::string, std::string> jsonExtractor(const std::string& payload) {

    Json::Value message;
    Json::CharReaderBuilder builder;

    std::string errs;
    std::istringstream iss(payload);

    if (!Json::parseFromStream(builder, iss, &message, &errs)) {
        std::cerr << "JSON parse error: " << errs << "\n";
        return {"",""};
    }

    
    if (message["message_type"] == "trigger")
        return {message["command"]["symbol_id"].asString(), message["command"]["fade_transition"].asString()};

    std::cerr << "No valid trigger message.\n";
    return {"",""};
}


// --- Hearing the SDK connection
void jsonListenerThread() {
    auto catalogue = loadCatalogue(CATALOGUE_PATH);

    if (catalogue.empty()) {
        std::cerr << "Catalogue empty — ZeroMQ listener exiting.\n";
        return;
    }

    // initPicoSerial(); // Attempt to connect to Pico LEDs (non-critical)
 
    zmq::context_t context(1);
	zmq::socket_t pull_socket(context, zmq::socket_type::pull);
	pull_socket.set(zmq::sockopt::rcvhwm, 100);
	pull_socket.set(zmq::sockopt::rcvtimeo, 200);

    const std::string endpoint(ZMQ_ENDPOINT);

	if (endpoint.rfind("ipc://", 0) == 0) {
		std::string ipcPath = endpoint.substr(6);
		if (!ipcPath.empty()) {
			unlink(ipcPath.c_str());
		}
	}

    try {
		pull_socket.bind(endpoint);
	} catch (const zmq::error_t& e) {
		std::cerr << "ZeroMQ bind failed at " << endpoint << ": " << e.what() << "\n";
		return;
	}

	std::cout << "ZeroMQ listener ready - listening on " << endpoint << "\n";

	while (jsonLive.load()) {
		zmq::message_t msg;
		auto result = pull_socket.recv(msg, zmq::recv_flags::none);

		if (!result) {
			continue;
		}

		std::string payload(static_cast<char*>(msg.data()), msg.size());
		auto [symbol, fade] = jsonExtractor(payload);

        std::cout << "Parsed symbol: " << symbol << "\n";
		if (!symbol.empty()) {

			applyPattern(catalogue, symbol, fade);

            /*

            // --- Parallel LED control 
			auto itLed = SYMBOL_TO_LED_EFFECT.find(symbol);
			if (itLed != SYMBOL_TO_LED_EFFECT.end()) {
				int targetFx = itLed->second;
				std::thread([targetFx]() {
					sendLedEffect(targetFx);
				}).detach();
			} 
            
            */
		}
	}
}


#ifdef DEBUG

// --- Text User Interface (TUI) 
void runTUI() {
    std::cout << "\n--- TUI Mode Activated ---\n";
    std::cout << "Commands: \n";
    std::cout << "  'set <id> <freq> <amp> <phase>'\n";
    std::cout << "  'mode <headset|hw>'\n";
    std::cout << "  'mute' / 'unmute'\n";
    std::cout << "  'reset' (Reset all generators to defaults)\n";
    std::cout << "  'json <on|off>'  (live ZeroMQ listener)\n";
    std::cout << "  'status' / 'exit'\n";
    std::cout << "  'help' (Explains all the variables of 'set')";

    std::thread listener;
    std::string cmd;

    while (true) {
        std::cout << "\n[Mute: " << (masterMute.load() ? "ON" : "OFF") 
                  << " | Latency: " << std::fixed << std::setprecision(2) << measuredLatency.load() << "ms] > " << " | ZeroMQ: " << (jsonLive.load() ? "LIVE" : "OFF") << "] > "; 
        
        if (!(std::cin >> cmd)) 
            break;
        
        if (cmd == "exit") 
            break;
        else if (cmd == "mute") 
            masterMute.store(true);
        else if (cmd == "unmute") 
            masterMute.store(false);
        else if (cmd == "reset") {
            resetGenerators();
            std::cout << "All generators reset to default values.\n";
        }
        else if (cmd == "mode") {
            std::string m; std::cin >> m;

            if (m == "headset") 
                headsetMode.store(true);
            else if (m == "hw") 
                headsetMode.store(false);

            std::cout << "Mode updated.\n";
        }
	    else if (cmd == "json") {
            std::string m; 
            std::cin >> m;
            if (m == "on" && !jsonLive.load()) {
                jsonLive.store(true);
                listener = std::thread(jsonListenerThread);
                std::cout << "JSON listener ON.\n";
            } else if (m == "off" && jsonLive.load()) {
                jsonLive.store(false);
                if (listener.joinable()) 
                    listener.join();

                std::cout << "JSON listener OFF.\n";
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
                std::cin.clear(); 
                std::cin.ignore(10000, '\n');
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

    if (jsonLive.load()) {
        jsonLive.store(false);
        if (listener.joinable()) 
            listener.join();
    }
}

// --- Graphical User Interface (GUI) 

void runGUI() {

    if (!glfwInit()) 
        return;
    GLFWwindow* window = glfwCreateWindow(900, 800, "Multi-Channel Sine Generator", NULL, NULL);
    
    if (!window) 
        return;

    glfwMakeContextCurrent(window);
    glfwSwapInterval(1);

    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGui_ImplGlfw_InitForOpenGL(window, true);
    ImGui_ImplOpenGL3_Init("#version 130");

    ImVec4 clear_color = ImVec4(0.10f, 0.10f, 0.12f, 1.00f);
    std::thread listener;

    while (!glfwWindowShouldClose(window)) {
        glfwPollEvents();
        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();

        ImGui::Begin("Global Controls");
        bool isMuted = masterMute.load();
        if (isMuted) 
            ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.8f, 0.1f, 0.1f, 1.0f));

        if (ImGui::Button(isMuted ? "UNMUTE ALL" : "MASTER MUTE", ImVec2(ImGui::GetContentRegionAvail().x * 0.5f, 40))) {
            masterMute.store(!isMuted);
        }

        if (isMuted) 
            ImGui::PopStyleColor();

        ImGui::SameLine();

        if (ImGui::Button("RESET ALL", ImVec2(ImGui::GetContentRegionAvail().x, 40))) {
            resetGenerators();
        }

        bool hMode = headsetMode.load();

        if (ImGui::Checkbox("Headset Monitoring Mode", &hMode)) {
            headsetMode.store(hMode);
        }

	    bool jLive = jsonLive.load();

        if (ImGui::Checkbox("Live JSON Mode (watch trigger file)", &jLive)) {
            if (jLive && !jsonLive.load()) {
                jsonLive.store(true);
                listener = std::thread(jsonListenerThread);
            } else if (!jLive && jsonLive.load()) {
                jsonLive.store(false);
                if (listener.joinable()) 
                    listener.join();
            }
        }
        if (jsonLive.load()) {
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

                if (ImGui::SliderFloat("Frequency (Hz)", &f, 20.0f, 24000.0f, "%.1f", ImGuiSliderFlags_Logarithmic)) 
                    generators[i].freq.store(f);
                if (ImGui::SliderFloat("Amplitude",      &a, 0.0f,  1.0f,     "%.3f"))  
                    generators[i].amp.store(a);
                if (ImGui::SliderFloat("Phase (deg)",    &p, 0.0f,  360.0f,   "%.1f"))                               
                    generators[i].phaseDeg.store(std::fmod(p, 360.0f));
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

    if (jsonLive.load()) {
        jsonLive.store(false);
        if (listener.joinable()) 
            listener.join();
    }
    
    ImGui_ImplOpenGL3_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();
    glfwDestroyWindow(window);
    glfwTerminate();
}

#endif // DEBUG