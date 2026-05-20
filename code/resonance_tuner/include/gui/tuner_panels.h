#pragma once

#include "core/physics.h"
#include <string>

namespace chladni {

class TunerApp;

class TunerPanels {
 public:
  static void draw_tuner_ui(TunerApp* app);
  
 private:
  static void draw_soundcard_config(TunerApp* app);
  static void draw_led_config(TunerApp* app);
  static void draw_symbol_trigger(TunerApp* app);
  static void draw_plate_config(SimulationContext& ctx, TunerApp* app);
  static void draw_material_selector(SimulationContext& ctx);
};

} // namespace chladni
