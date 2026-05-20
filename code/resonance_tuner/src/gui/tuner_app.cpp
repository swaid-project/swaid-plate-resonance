#include "gui/tuner_app.h"
#include "gui/tuner_panels.h"
#include "imgui.h"
#include "imgui_impl_glfw.h"
#include "imgui_impl_opengl3.h"
#include <GLFW/glfw3.h>
#include <iostream>

namespace chladni {

TunerApp::TunerApp(const std::string& title, int width, int height)
    : title_(title), width_(width), height_(height) {
  channels_.resize(8);
  physics_ = std::make_shared<PhysicsEngine>(200);
  
  // Default Plate Config
  ctx_.lx = 0.20;
  ctx_.ly = 0.20;
  ctx_.h = 0.001;
  ctx_.e = 193e9; // Steel
  ctx_.rho = 8000.0;
  ctx_.nu = 0.29;
  ctx_.damping = 0.01;
  ctx_.n_modes = 15;
  ctx_.geometry = Geometry::kSquare;
  ctx_.sign = 1;

  // Default 4-transducer setup
  ctx_.transducers.push_back({-0.07, -0.07, 0.0, 0.0, std::nullopt});
  ctx_.transducers.push_back({ 0.07, -0.07, 0.0, 0.0, std::nullopt});
  ctx_.transducers.push_back({-0.07,  0.07, 0.0, 0.0, std::nullopt});
  ctx_.transducers.push_back({ 0.07,  0.07, 0.0, 0.0, std::nullopt});

  init_zmq("ipc:///tmp/swaid.sock");
}

TunerApp::~TunerApp() {
  close_zmq();
  shutdown();
}

bool TunerApp::init() {
  if (!glfwInit()) return false;
  glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
  glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 0);
  window_ = glfwCreateWindow(width_, height_, title_.c_str(), NULL, NULL);
  if (!window_) return false;
  glfwMakeContextCurrent(window_);
  glfwSwapInterval(1);

  IMGUI_CHECKVERSION();
  ImGui::CreateContext();
  ImGuiIO& io = ImGui::GetIO();
  io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;
  io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;

  ImGui_ImplGlfw_InitForOpenGL(window_, true);
  ImGui_ImplOpenGL3_Init("#version 130");

  glGenTextures(1, &plate_texture_);
  glBindTexture(GL_TEXTURE_2D, plate_texture_);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);

  physics_->init_particles(num_particles_, ctx_.lx, ctx_.ly);
  return true;
}

void TunerApp::shutdown() {
  ImGui_ImplOpenGL3_Shutdown();
  ImGui_ImplGlfw_Shutdown();
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
  // Update physics transducers based on first 4 channels for simulation
  // (In reality, the mapping can be more complex, but let's assume 1:1 for the first 4)
  for(size_t i=0; i < ctx_.transducers.size() && i < 8; ++i) {
      ctx_.transducers[i].amplitude = channels_[i].amp;
      ctx_.transducers[i].phase_rad = channels_[i].phase * (M_PI / 180.0);
      // We use the first channel's frequency as the primary simulation frequency
      // unless we want a multi-frequency simulation (not fully supported by this physics engine yet)
  }
  
  float primary_freq = channels_[0].freq;

  physics_->compute_visuals(primary_freq, ctx_, current_sand_, current_deformation_);
  
  if (reset_particles_requested_) {
      physics_->init_particles(num_particles_, ctx_.lx, ctx_.ly);
      reset_particles_requested_ = false;
  }
  
  Eigen::MatrixXcd resp = physics_->compute_driven_response(primary_freq, ctx_);
  physics_->step_particles(resp, ctx_.lx, ctx_.ly, 0.016f);

  int res = physics_->get_resolution();
  std::vector<unsigned char> data(res * res * 3);
  for (int i = 0; i < res; ++i) {
    for (int j = 0; j < res; ++j) {
      double s = current_sand_(i, j);
      unsigned char val = static_cast<unsigned char>(s * 255);
      data[(i * res + j) * 3 + 0] = val;
      data[(i * res + j) * 3 + 1] = val;
      data[(i * res + j) * 3 + 2] = val;
    }
  }

  glBindTexture(GL_TEXTURE_2D, plate_texture_);
  glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, res, res, 0, GL_RGB, GL_UNSIGNED_BYTE, data.data());
}

void TunerApp::render_ui() {
  TunerPanels::draw_tuner_ui(this);
}

void TunerApp::render_viewport() {
  ImGui::Begin("Simulation Viewport");
  ImVec2 size = ImGui::GetContentRegionAvail();
  float aspect = (float)ctx_.lx / (float)ctx_.ly;
  float draw_w = size.x;
  float draw_h = size.x / aspect;
  if (draw_h > size.y) {
      draw_h = size.y;
      draw_w = size.y * aspect;
  }
  ImGui::Image((void*)(intptr_t)plate_texture_, ImVec2(draw_w, draw_h));
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

void TunerApp::sync_master(bool mute, bool reset) {
    char buf[512];
    format_master_control(mute, reset, buf, 512);
    send_zmq(buf);
}

} // namespace chladni
