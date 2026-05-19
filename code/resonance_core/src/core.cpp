#include "../include/core.hpp"

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

    initPicoSerial(); // Attempt to connect to Pico LEDs (non-critical)
 
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

            // --- Parallel LED control 
			auto itLed = SYMBOL_TO_LED_EFFECT.find(symbol);
			if (itLed != SYMBOL_TO_LED_EFFECT.end()) {
				int targetFx = itLed->second;
				std::thread([targetFx]() {
					sendLedEffect(targetFx);
				}).detach();
			}
		}
	}
}