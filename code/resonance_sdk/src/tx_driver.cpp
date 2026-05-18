#include <zmq.hpp>
#include <string>
#include <chrono>
#include <iostream>
#include <cstdio>


static zmq::context_t* ctx = nullptr;
static zmq::socket_t* push_socket = nullptr;

// 'extern "C"' prevents C++ name mangling, allowing Python to find these functions easily.
extern "C" {

    void init_zmq(const char* socket_path) {
        if (!ctx) {
            std::cout << "[C++ Native] Initializing ZeroMQ IPC client...\n";
            
            // Create Context with 1 I/O thread
            ctx = new zmq::context_t(1);
            
            // Create PUSH socket (Client side)
            push_socket = new zmq::socket_t(*ctx, zmq::socket_type::push);

            // Mitigation: High-Water Mark (HWM)
            // Limits the internal queue to 100 messages to prevent memory exhaustion
            // if the receiver (PR Daemon) stops processing.
            push_socket->set(zmq::sockopt::sndhwm, 100);

            // Mitigation: Deadlock Prevention
            // Sets a send timeout of 5ms. If the socket hangs, it forces an exit.
            push_socket->set(zmq::sockopt::sndtimeo, 5); 

            // Mitigation: Stale Sockets
            // Since this is the HI Subsystem (Client), we use connect() instead of bind().
            // This leaves the file lifecycle management strictly to the PR receiver.
            push_socket->connect(socket_path);
            
            std::cout << "[C++ Native] Connected to " << socket_path << "\n";
        }
    }

    void cleanup_zmq() {
        std::cout << "[C++ Native] Cleaning up ZeroMQ resources...\n";
        if (push_socket) { 
            delete push_socket; 
            push_socket = nullptr; 
        }
        if (ctx) { 
            delete ctx; 
            ctx = nullptr; 
        }
    }
    
    int send_trigger(const char* symbol_id, const char* led_id, const char* fade_transition, float volume_percent, int music_note, const char* music_rhythm, int bpm) {
        if (!push_socket) {
            std::cerr << "[C++ Native Error] ZeroMQ not initialized. Call init_zmq first.\n";
            return -1;
        }

        // 1. Generate current epoch timestamp in milliseconds
        auto now = std::chrono::system_clock::now();
        auto duration = now.time_since_epoch();
        long long timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(duration).count();

        char json_payload[512];
        int len = snprintf(json_payload, sizeof(json_payload),
            "{\n"
            "    \"message_type\": \"trigger\",\n"
            "    \"timestamp\" : %lld,\n"
            "    \"command\" : {\n"
            "        \"symbol_id\": \"%s\",\n"
            "        \"led_id\" : \"%s\",\n"
            "        \"fade_transition\" : \"%s\",\n"
            "        \"music_note\" : %d,\n"
            "        \"music_rhythm\" : \"%s\",\n"
            "        \"BPM\" : %d\n"
            "    }\n"
            "}",
            timestamp, symbol_id, led_id, fade_transition, music_note, music_rhythm, bpm
        );

        // Check for snprintf buffer truncation
        if (len < 0 || len >= sizeof(json_payload)) {
            std::cerr << "[C++ Native Error] JSON payload truncated or formatting failed.\n";
            return -1;
        }

        // Package and Send Message
        // zmq::message_t handles dynamic allocation internally and automatically 
        zmq::message_t zmq_msg(json_payload, len);

        try {
            // If the PR Daemon is busy and the HWM is reached, dontwait throws an exception
            // or returns false instead of freezing the Python HI.
            auto result = push_socket->send(zmq_msg, zmq::send_flags::dontwait);
            
            if (!result) {
                // Return 0 so Python knows the message was safely dropped
                return 0; 
            }
        } catch (const zmq::error_t& e) {
            std::cerr << "[C++ Native Error] ZMQ Send Failed: " << e.what() << "\n";
            return -1;
        }

        return 1; 
    }

} 