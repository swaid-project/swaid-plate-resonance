#pragma once

#include <string>
#include <memory>
#include <atomic>
#include <vector>
#include "core/physics.h"
#include "core/analyzer.h"
#include "mqdriver_tx.hpp"

struct GLFWwindow;

namespace chladni {

struct SoundcardChannel {
    float freq = 440.0f;
    float amp = 0.0f;
    float phase = 0.0f;
    bool follow_master_freq = false;
    bool follow_master_amp = false;
};

class TunerApp {
 public:
  TunerApp(const std::string& title, int width, int height);
  ~TunerApp();

  void run();

  std::shared_ptr<PhysicsEngine> get_physics() { return physics_; }
  SimulationContext& get_ctx() { return ctx_; }
  
  // Hardware Sync
  void sync_channel(int ch);
  void sync_led(int effect);
  void trigger_symbol(const std::string& symbol_id, int led_id);
  void load_symbol_to_manual(const nlohmann::json& symbol_data);
  void sync_master(bool mute, bool reset);

  // Soundcard State (8 channels)
  std::vector<SoundcardChannel> channels_;
  std::vector<int> transducer_to_channel_map_; // Maps transducer index [0-3] to channel index [0-7]
  float master_freq_ = 440.0f;
  float master_amp_ = 0.0f;
  float master_freq_step_ = 10.0f;
  float master_amp_step_ = 0.01f;
  bool is_muted_ = false;
  bool auto_sync_ = true;
  int selected_led_effect_ = 0;
  std::string symbol_file_path_ = "/home/miguel/Documents/ELETRO/4ANO 2S/ESIS/swaid-plate-resonance/code/simulator/sim/symbols/master_symbols.json";

 private:
  bool init();
  void shutdown();

  void render_ui();
  void render_viewport();
  void update_texture();
  
  GLFWwindow* window_;
  std::string title_;
  int width_, height_;

  unsigned int plate_texture_ = 0;
  Eigen::MatrixXd current_sand_;
  Eigen::MatrixXd current_deformation_;

  std::shared_ptr<PhysicsEngine> physics_;
  SimulationContext ctx_;

  // Viewport State
  bool show_particles_ = true;
  int num_particles_ = 2000;
  bool reset_particles_requested_ = true;
};

} // namespace chladni
