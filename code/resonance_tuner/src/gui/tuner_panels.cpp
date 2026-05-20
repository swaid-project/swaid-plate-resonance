#include "gui/tuner_panels.h"
#include "gui/tuner_app.h"
#include "imgui.h"
#include <filesystem>
#include <algorithm>
#include <fstream>
#include <nlohmann/json.hpp>

namespace chladni {

void TunerPanels::draw_tuner_ui(TunerApp* app) {
    ImGui::Begin("Hardware Tuner & Control");
    
    if (ImGui::BeginTabBar("TunerTabs")) {
        if (ImGui::BeginTabItem("Manual Soundcard")) {
            draw_soundcard_config(app);
            ImGui::EndTabItem();
        }
        if (ImGui::BeginTabItem("LED Effects")) {
            draw_led_config(app);
            ImGui::EndTabItem();
        }
        if (ImGui::BeginTabItem("Symbol Trigger")) {
            draw_symbol_trigger(app);
            ImGui::EndTabItem();
        }
        if (ImGui::BeginTabItem("Plate & Transducers")) {
            draw_plate_config(app->get_ctx(), app);
            ImGui::EndTabItem();
        }
        ImGui::EndTabBar();
    }
    
    ImGui::End();
}

void TunerPanels::draw_soundcard_config(TunerApp* app) {
    ImGui::Checkbox("Auto-Sync to Hardware", &app->auto_sync_);
    ImGui::SameLine();
    if (ImGui::Button("Sync All Now")) {
        for (int i = 0; i < 8; ++i) app->sync_channel(i);
    }
    
    if (ImGui::BeginTable("SoundcardChannels", 5, ImGuiTableFlags_Borders | ImGuiTableFlags_RowBg)) {
        ImGui::TableSetupColumn("Ch", ImGuiTableColumnFlags_WidthFixed, 30.0f);
        ImGui::TableSetupColumn("Freq (Hz)");
        ImGui::TableSetupColumn("Amp (0-1)");
        ImGui::TableSetupColumn("Phase (deg)");
        ImGui::TableSetupColumn("Action", ImGuiTableColumnFlags_WidthFixed, 60.0f);
        ImGui::TableHeadersRow();

        for (int i = 0; i < 8; ++i) {
            ImGui::TableNextRow();
            ImGui::PushID(i);
            
            ImGui::TableSetColumnIndex(0);
            ImGui::Text("%d", i);
            
            ImGui::TableSetColumnIndex(1);
            ImGui::SetNextItemWidth(-1);
            if (ImGui::SliderFloat("##Freq", &app->channels_[i].freq, 20.0f, 20000.0f, "%.1f", ImGuiSliderFlags_Logarithmic)) {
                if (app->auto_sync_) app->sync_channel(i);
            }
            
            ImGui::TableSetColumnIndex(2);
            ImGui::SetNextItemWidth(-1);
            if (ImGui::SliderFloat("##Amp", &app->channels_[i].amp, 0.0f, 1.0f, "%.3f")) {
                if (app->auto_sync_) app->sync_channel(i);
            }
            
            ImGui::TableSetColumnIndex(3);
            ImGui::SetNextItemWidth(-1);
            if (ImGui::SliderFloat("##Phase", &app->channels_[i].phase, 0.0f, 360.0f, "%.1f")) {
                if (app->auto_sync_) app->sync_channel(i);
            }
            
            ImGui::TableSetColumnIndex(4);
            if (ImGui::Button("Sync")) {
                app->sync_channel(i);
            }
            
            ImGui::PopID();
        }
        ImGui::EndTable();
    }
    
    ImGui::Separator();
    if (ImGui::Button("MASTER MUTE", ImVec2(120, 40))) app->sync_master(true, false);
    ImGui::SameLine();
    if (ImGui::Button("UNMUTE", ImVec2(120, 40))) app->sync_master(false, false);
    ImGui::SameLine();
    if (ImGui::Button("RESET ALL", ImVec2(120, 40))) app->sync_master(false, true);
}

void TunerPanels::draw_led_config(TunerApp* app) {
    ImGui::Text("Select LED Effect (0-19):");
    if (ImGui::SliderInt("Effect ID", &app->selected_led_effect_, 0, 19)) {
        if (app->auto_sync_) app->sync_led(app->selected_led_effect_);
    }
    if (ImGui::Button("Apply Effect", ImVec2(-1, 40))) {
        app->sync_led(app->selected_led_effect_);
    }
    
    ImGui::Separator();
    ImGui::Text("Common Effects:");
    const char* names[] = {"Rainbow", "Breathing", "Scanner", "Matrix", "Galaxy"};
    int ids[] = {0, 3, 7, 14, 17};
    for (int i=0; i<5; ++i) {
        if (ImGui::Button(names[i])) {
            app->selected_led_effect_ = ids[i];
            app->sync_led(ids[i]);
        }
        if (i < 4) ImGui::SameLine();
    }
}

void TunerPanels::draw_symbol_trigger(TunerApp* app) {
    static std::vector<std::string> symbol_files;
    static int selected_file_idx = 0;
    static nlohmann::json current_symbols;
    
    auto refresh_files = [&]() {
        symbol_files.clear();
        try {
            for (const auto& entry : std::filesystem::directory_iterator("../simulator/sim/symbols")) {
                if (entry.path().extension() == ".json") symbol_files.push_back(entry.path().filename().string());
            }
            std::sort(symbol_files.rbegin(), symbol_files.rend());
        } catch (...) {}
    };
    
    if (symbol_files.empty()) refresh_files();
    
    if (ImGui::Button("Refresh Symbol Files")) refresh_files();
    
    if (!symbol_files.empty()) {
        if (ImGui::BeginCombo("Dictionary", symbol_files[selected_file_idx].c_str())) {
            for (int i=0; i<symbol_files.size(); ++i) {
                if (ImGui::Selectable(symbol_files[i].c_str(), i == selected_file_idx)) {
                    selected_file_idx = i;
                    std::ifstream f("../simulator/sim/symbols/" + symbol_files[i]);
                    current_symbols = nlohmann::json::parse(f);
                }
            }
            ImGui::EndCombo();
        }
    }
    
    if (!current_symbols.is_null()) {
        ImGui::Text("Trigger Symbols:");
        if (ImGui::BeginTable("SymbolList", 3, ImGuiTableFlags_Borders | ImGuiTableFlags_RowBg | ImGuiTableFlags_ScrollY, ImVec2(0, 400))) {
            ImGui::TableSetupColumn("Symbol ID");
            ImGui::TableSetupColumn("Action");
            ImGui::TableHeadersRow();
            
            for (auto& sym : current_symbols) {
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                ImGui::Text("%s", sym["id"].get<std::string>().c_str());
                
                ImGui::TableSetColumnIndex(1);
                if (ImGui::Button(("Trigger##" + sym["id"].get<std::string>()).c_str())) {
                    app->trigger_symbol(sym["id"].get<std::string>(), app->selected_led_effect_);
                }
            }
            ImGui::EndTable();
        }
    }
}

void TunerPanels::draw_plate_config(SimulationContext& ctx, TunerApp* app) {
    draw_material_selector(ctx);
    if (ImGui::CollapsingHeader("Plate Geometry", ImGuiTreeNodeFlags_DefaultOpen)) {
        static const char* items[] = {"Square", "Rectangular", "Circular"};
        int current = (int)ctx.geometry;
        if (ImGui::Combo("Geometry", &current, items, 3)) { ctx.geometry = (Geometry)current; }
        double lx_mm = ctx.lx * 1000.0; if (ImGui::InputDouble("Lx (mm)", &lx_mm)) ctx.lx = lx_mm / 1000.0;
        if (ctx.geometry == Geometry::kRectangular) { double ly_mm = ctx.ly * 1000.0; if (ImGui::InputDouble("Ly (mm)", &ly_mm)) ctx.ly = ly_mm / 1000.0; }
        double h_mm = ctx.h * 1000.0; if (ImGui::InputDouble("Thickness (mm)", &h_mm)) ctx.h = h_mm / 1000.0;
    }
    
    if (ImGui::CollapsingHeader("Transducer Positions (4 Required)", ImGuiTreeNodeFlags_DefaultOpen)) {
        for (size_t i = 0; i < ctx.transducers.size(); ++i) {
            std::string label = "Transducer " + std::to_string(i+1);
            if (ImGui::TreeNode(label.c_str())) {
                double tx_mm = ctx.transducers[i].x * 1000.0; double ty_mm = ctx.transducers[i].y * 1000.0;
                if (ImGui::InputDouble("X (mm)", &tx_mm)) { ctx.transducers[i].x = tx_mm / 1000.0; }
                if (ImGui::InputDouble("Y (mm)", &ty_mm)) { ctx.transducers[i].y = ty_mm / 1000.0; }
                app->get_physics()->clamp_transducer(ctx.transducers[i], ctx);
                ImGui::TreePop();
            }
        }
    }
}

void TunerPanels::draw_material_selector(SimulationContext& ctx) {
    if (ImGui::CollapsingHeader("Material", ImGuiTreeNodeFlags_DefaultOpen)) {
        static const char* materials[] = { "Aluminium", "Steel", "Brass", "Glass" };
        static int current_mat = 1;
        if (ImGui::Combo("Preset", &current_mat, materials, 4)) {
            if (current_mat == 0) { ctx.e = 69e9; ctx.rho = 2700.0; ctx.nu = 0.33; }
            else if (current_mat == 1) { ctx.e = 193e9; ctx.rho = 8000.0; ctx.nu = 0.29; }
        }
        ImGui::InputDouble("E (Pa)", &ctx.e);
        ImGui::InputDouble("rho (kg/m3)", &ctx.rho);
        ImGui::InputDouble("nu", &ctx.nu);
    }
}

} // namespace chladni
