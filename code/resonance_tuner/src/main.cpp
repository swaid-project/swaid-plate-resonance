#include "gui/tuner_app.h"
#include <iostream>
#include <exception>

int main(int argc, char** argv) {
  (void)argc;
  (void)argv;
  try {
    std::cout << "Starting SWAID Resonance Tuner..." << std::endl;
    chladni::TunerApp app("SWAID Resonance Tuner", 1280, 800);
    app.run();
  } catch (const std::exception& e) {
    std::cerr << "CRITICAL ERROR: " << e.what() << std::endl;
    return 1;
  }
  return 0;
}
