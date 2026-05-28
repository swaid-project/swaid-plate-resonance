#include "gui/tuner_app.h"
#include "gui/tuner_panels.h"
#include "imgui.h"
#include "implot.h"
#include "imgui_impl_glfw.h"
#include "imgui_impl_opengl3.h"
#include <GLFW/glfw3.h>
#include <iostream>
#include <algorithm>
#include <cmath>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace chladni {

TunerApp::TunerApp(const std::string& title, int width, int height)
    : title_(title), width_(width), height_(height) {
  channels_.resize(8);
  transducer_to_channel_map_ = {0, 1, 2, 3}; // Default 1:1 for first 4
  physics_ = std::make_shared<PhysicsEngine>(200);
  
  // Default Plate Config: Rectangular Steel 300x200x1mm
  ctx_.lx = 0.30;
  ctx_.ly = 0.20;
  ctx_.h = 0.001;
  ctx_.e = 193e9; // Steel
  ctx_.rho = 8000.0;
  ctx_.nu = 0.29;
  ctx_.damping = 0.01;
  ctx_.n_modes = 15;
  ctx_.geometry = Geometry::kRectangular;
  ctx_.sign = 1;

  // Default 4-transducer setup
  ctx_.transducers.push_back({-0.10, -0.07, 0.0, 0.0, std::nullopt});
  ctx_.transducers.push_back({ 0.10, -0.07, 0.0, 0.0, std::nullopt});
  ctx_.transducers.push_back({-0.10,  0.07, 0.0, 0.0, std::nullopt});
  ctx_.transducers.push_back({ 0.10,  0.07, 0.0, 0.0, std::nullopt});

  init_zmq("ipc:///tmp/swaid.sock");
}

TunerApp::~TunerApp() {
  close_zmq();
  shutdown();
}

bool TunerApp::init() {
  if (!glfwInit()) return false;
  glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
  glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
  glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);

  window_ = glfwCreateWindow(width_, height_, title_.c_str(), NULL, NULL);
  if (!window_) return false;
  glfwMakeContextCurrent(window_);
  glfwSwapInterval(1);

  IMGUI_CHECKVERSION();
  ImGui::CreateContext();
  ImPlot::CreateContext();
  ImGuiIO& io = ImGui::GetIO();
  io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;
  io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;

  ImGui_ImplGlfw_InitForOpenGL(window_, true);
  ImGui_ImplOpenGL3_Init("#version 330");

  glGenTextures(1, &plate_texture_);
  glBindTexture(GL_TEXTURE_2D, plate_texture_);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);

  physics_->init_particles(num_particles_, ctx_.lx, ctx_.ly);
  return true;
}

void TunerApp::shutdown() {
  if (plate_texture_) glDeleteTextures(1, &plate_texture_);
  ImGui_ImplOpenGL3_Shutdown();
  ImGui_ImplGlfw_Shutdown();
  ImPlot::DestroyContext();
  ImGui::DestroyContext();
  glfwDestroyWindow(window_);
  glfwTerminate();
}

void TunerApp::run() {
  if (!init()) return;
  while (!glfwWindowShouldClose(window_)) {
    glfwPollEvents();
    ImGui_ImplOpenGL3_NewFrame();
    ImGui_ImplGlfw_NewFrame();
    ImGui::NewFrame();
    ImGui::DockSpaceOverViewport(0, ImGui::GetMainViewport());

    update_texture();
    render_ui();
    render_viewport();

    ImGui::Render();
    int display_w, display_h;
    glfwGetFramebufferSize(window_, &display_w, &display_h);
    glViewport(0, 0, display_w, display_h);
    glClearColor(0.1f, 0.1f, 0.1f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);
    ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
    glfwSwapBuffers(window_);
  }
}

void TunerApp::update_texture() {
  // Sync follow master channels
  for (int i = 0; i < 8; ++i) {
      bool changed = false;
      if (channels_[i].follow_master_freq) {
          if (channels_[i].freq != master_freq_) {
              channels_[i].freq = master_freq_;
              changed = true;
          }
      }
      if (channels_[i].follow_master_amp) {
          if (channels_[i].amp != master_amp_) {
              channels_[i].amp = master_amp_;
              changed = true;
          }
      }
      if (changed && auto_sync_) sync_channel(i);
  }

  // Update physics transducers based on mapped channels for simulation
  for(size_t i=0; i < ctx_.transducers.size() && i < transducer_to_channel_map_.size(); ++i) {
      int ch_idx = transducer_to_channel_map_[i];
      if (ch_idx >= 0 && ch_idx < 8) {
          ctx_.transducers[i].amplitude = channels_[ch_idx].amp;
          ctx_.transducers[i].phase_rad = channels_[ch_idx].phase * (M_PI / 180.0);
      }
  }
  
  // Use the frequency from the first mapped channel as primary
  float primary_freq = master_freq_;
  if (!transducer_to_channel_map_.empty()) {
      int ch0 = transducer_to_channel_map_[0];
      if (ch0 >= 0 && ch0 < 8) primary_freq = channels_[ch0].freq;
  }

  physics_->compute_visuals(primary_freq, ctx_, current_sand_, current_deformation_);
  
  if (reset_particles_requested_) {
      physics_->init_particles(num_particles_, ctx_.lx, ctx_.ly);
      reset_particles_requested_ = false;
  }
  
  Eigen::MatrixXcd resp = physics_->compute_driven_response(primary_freq, ctx_);
  physics_->step_particles(resp, ctx_.lx, ctx_.ly, 0.016f);

  int res = physics_->get_resolution();
  std::vector<unsigned char> data(res * res * 4);
  unsigned char* ptr = data.data();
  
  for (int i = 0; i < res; ++i) {
    for (int j = 0; j < res; ++j) {
      double val = current_sand_(i, j);
      unsigned char c = static_cast<unsigned char>(std::clamp(val * 255.0, 0.0, 255.0));
      *ptr++ = c; 
      *ptr++ = static_cast<unsigned char>(c * 0.9); 
      *ptr++ = static_cast<unsigned char>(c * 0.6); 
      *ptr++ = 255;
    }
  }

  glBindTexture(GL_TEXTURE_2D, plate_texture_);
  glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, res, res, 0, GL_RGBA, GL_UNSIGNED_BYTE, data.data());
}

void TunerApp::render_ui() {
  TunerPanels::draw_tuner_ui(this);
}

void TunerApp::render_viewport() {
  ImGui::Begin("Simulation Viewport");
  
  if (ImPlot::BeginPlot("##PlatePlot", ImVec2(-1, -1), ImPlotFlags_Equal | ImPlotFlags_NoLegend)) {
      double x_min = -ctx_.lx / 2.0, x_max = ctx_.lx / 2.0;
      double y_min = -(ctx_.geometry == Geometry::kCircular ? ctx_.lx : ctx_.ly) / 2.0;
      double y_max = (ctx_.geometry == Geometry::kCircular ? ctx_.lx : ctx_.ly) / 2.0;
      
      ImPlot::SetupAxes(NULL, NULL, ImPlotAxisFlags_NoDecorations, ImPlotAxisFlags_NoDecorations);
      ImPlot::SetupAxesLimits(x_min * 1.1, x_max * 1.1, y_min * 1.1, y_max * 1.1);
      
      ImPlot::PlotImage("Plate", (void*)(intptr_t)plate_texture_, ImPlotPoint(x_min, y_min), ImPlotPoint(x_max, y_max));
      
      for (size_t i = 0; i < ctx_.transducers.size(); ++i) {
          std::string id = "T" + std::to_string(i + 1);
          if (ImPlot::DragPoint(static_cast<int>(i), &ctx_.transducers[i].x, &ctx_.transducers[i].y, ImVec4(1, 0.5, 0, 1), 4)) {
              physics_->clamp_transducer(ctx_.transducers[i], ctx_);
          }
      }
      
      if (show_particles_) {
          const auto& pts = physics_->get_particles();
          if (pts.rows() > 0) {
              ImPlotSpec spec;
              spec.Marker = ImPlotMarker_Circle;
              spec.MarkerSize = 1.0f;
              spec.MarkerFillColor = ImVec4(1, 1, 0.8, 1);
              spec.MarkerLineColor = ImVec4(1, 1, 0.8, 1);
              ImPlot::PlotScatter("Particles", pts.col(0).data(), pts.col(1).data(), static_cast<int>(pts.rows()), spec);
          }
      }
      ImPlot::EndPlot();
  }
  ImGui::End();
}

void TunerApp::sync_channel(int ch) {
    char buf[512];
    format_manual_audio(ch, channels_[ch].freq, channels_[ch].amp, channels_[ch].phase, buf, 512);
    send_zmq(buf);
}

void TunerApp::sync_led(int effect) {
    char buf[512];
    format_manual_led(effect, buf, 512);
    send_zmq(buf);
}

void TunerApp::trigger_symbol(const std::string& symbol_id, int led_id) {
    char buf[512];
    format_json(symbol_id.c_str(), std::to_string(led_id).c_str(), "MEDIUM", 1.0f, 0, "NONE", 120, buf, 512);
    send_zmq(buf);
}

void TunerApp::load_symbol_to_manual(const nlohmann::json& sym) {
    if (!sym.contains("hardware_config") || !sym["hardware_config"].contains("channels")) return;

    const auto& channels_data = sym["hardware_config"]["channels"];
    for (const auto& ch_data : channels_data) {
        int symbol_ch = ch_data.value("channel", 0); // 1-based channel in JSON
        int app_ch = symbol_ch - 1; // 0-based

        if (app_ch >= 0 && app_ch < 8) {
            channels_[app_ch].freq = ch_data.value("frequency_hz", 440.0f);
            channels_[app_ch].amp = ch_data.value("amplitude", 0.0f);
            channels_[app_ch].phase = (float)ch_data.value("phase_deg", 0.0);
            channels_[app_ch].follow_master_freq = false; 
            channels_[app_ch].follow_master_amp = false;

            // Load Transducer Positions if app_ch is within simulation transducers [0-3]
            if (app_ch < (int)ctx_.transducers.size()) {
                if (ch_data.contains("x")) ctx_.transducers[app_ch].x = ch_data["x"].get<double>();
                if (ch_data.contains("y")) ctx_.transducers[app_ch].y = ch_data["y"].get<double>();
                physics_->clamp_transducer(ctx_.transducers[app_ch], ctx_);
            }

            if (auto_sync_) sync_channel(app_ch);
        }
    }
}

void TunerApp::sync_master(bool mute, bool reset) {
    char buf[512];
    format_master_control(mute, reset, buf, 512);
    send_zmq(buf);
    if (!reset) is_muted_ = mute;
}

} // namespace chladni
