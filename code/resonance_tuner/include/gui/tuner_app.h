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
  void sync_master(bool mute, bool reset);

  // Soundcard State (8 channels)
  std::vector<SoundcardChannel> channels_;
  bool auto_sync_ = true;
  int selected_led_effect_ = 0;

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
