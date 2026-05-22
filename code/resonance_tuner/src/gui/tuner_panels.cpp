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
    
    ImGui::Separator();
    ImGui::TextColored(ImVec4(1, 1, 0, 1), "Master Controls:");
    ImGui::SetNextItemWidth(200);
    if (ImGui::SliderFloat("Master Frequency (Hz)", &app->master_freq_, 20.0f, 20000.0f, "%.1f", ImGuiSliderFlags_Logarithmic)) {
        // TunerApp::update_texture handles the per-channel sync if auto_sync is on
    }
    ImGui::SameLine();
    ImGui::SetNextItemWidth(100);
    ImGui::InputFloat("##MasterFreqInput", &app->master_freq_, 1.0f, 10.0f, "%.1f");

    if (ImGui::CollapsingHeader("Hardware Mapping (Sim -> Soundcard)", ImGuiTreeNodeFlags_None)) {
        ImGui::Text("Map the 4 simulation transducers to physical soundcard channels:");
        for (int i = 0; i < 4; ++i) {
            ImGui::PushID(i + 100);
            char label[32]; sprintf(label, "Transducer %d -> Ch", i + 1);
            ImGui::SetNextItemWidth(80);
            ImGui::Combo(label, &app->transducer_to_channel_map_[i], "0\0 1\0 2\0 3\0 4\0 5\0 6\0 7\0");
            ImGui::PopID();
            if (i < 3) ImGui::SameLine();
        }
    }
    
    if (ImGui::BeginTable("SoundcardChannels", 6, ImGuiTableFlags_Borders | ImGuiTableFlags_RowBg)) {
        ImGui::TableSetupColumn("Ch", ImGuiTableColumnFlags_WidthFixed, 30.0f);
        ImGui::TableSetupColumn("Follow Master", ImGuiTableColumnFlags_WidthFixed, 50.0f);
        ImGui::TableSetupColumn("Frequency (Hz)");
        ImGui::TableSetupColumn("Amplitude (0-1)");
        ImGui::TableSetupColumn("Phase (deg)");
        ImGui::TableSetupColumn("Action", ImGuiTableColumnFlags_WidthFixed, 60.0f);
        ImGui::TableHeadersRow();

        for (int i = 0; i < 8; ++i) {
            ImGui::TableNextRow();
            ImGui::PushID(i);
            
            ImGui::TableSetColumnIndex(0);
            ImGui::Text("%d", i);

            ImGui::TableSetColumnIndex(1);
            if (ImGui::Checkbox("##Follow", &app->channels_[i].follow_master)) {
                if (app->channels_[i].follow_master) {
                    app->channels_[i].freq = app->master_freq_;
                    if (app->auto_sync_) app->sync_channel(i);
                }
            }
            
            ImGui::TableSetColumnIndex(2);
            ImGui::BeginDisabled(app->channels_[i].follow_master);
            ImGui::SetNextItemWidth(-1);
            if (ImGui::SliderFloat("##Freq", &app->channels_[i].freq, 20.0f, 20000.0f, "%.1f", ImGuiSliderFlags_Logarithmic)) {
                if (app->auto_sync_) app->sync_channel(i);
            }
            ImGui::SetNextItemWidth(-1);
            if (ImGui::InputFloat("##FreqInput", &app->channels_[i].freq, 1.0f, 10.0f, "%.1f")) {
                if (app->auto_sync_) app->sync_channel(i);
            }
            ImGui::EndDisabled();
            
            ImGui::TableSetColumnIndex(3);
            ImGui::SetNextItemWidth(-1);
            if (ImGui::SliderFloat("##Amp", &app->channels_[i].amp, 0.0f, 1.0f, "%.3f")) {
                if (app->auto_sync_) app->sync_channel(i);
            }
            ImGui::SetNextItemWidth(-1);
            if (ImGui::InputFloat("##AmpInput", &app->channels_[i].amp, 0.001f, 0.01f, "%.3f")) {
                if (app->auto_sync_) app->sync_channel(i);
            }
            
            ImGui::TableSetColumnIndex(4);
            ImGui::SetNextItemWidth(-1);
            if (ImGui::SliderFloat("##Phase", &app->channels_[i].phase, 0.0f, 360.0f, "%.1f")) {
                if (app->auto_sync_) app->sync_channel(i);
            }
            ImGui::SetNextItemWidth(-1);
            if (ImGui::InputFloat("##PhaseInput", &app->channels_[i].phase, 1.0f, 10.0f, "%.1f")) {
                if (app->auto_sync_) app->sync_channel(i);
            }
            
            ImGui::TableSetColumnIndex(5);
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
    ImGui::Text("All Effects Shortcut Grid:");
    for (int i = 0; i < 20; ++i) {
        char buf[8]; sprintf(buf, "%d", i);
        bool is_selected = (app->selected_led_effect_ == i);
        if (is_selected) ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.2f, 0.7f, 0.2f, 1.0f));
        
        if (ImGui::Button(buf, ImVec2(40, 40))) {
            app->selected_led_effect_ = i;
            app->sync_led(i);
        }
        
        if (is_selected) ImGui::PopStyleColor();
        if ((i + 1) % 5 != 0) ImGui::SameLine();
    }
}

void TunerPanels::draw_symbol_trigger(TunerApp* app) {
    static char path_buf[512];
    static bool first_run = true;
    if (first_run) {
        strncpy(path_buf, app->symbol_file_path_.c_str(), sizeof(path_buf));
        first_run = false;
    }

    static nlohmann::json current_symbols;
    static std::string loaded_path = "";

    ImGui::TextColored(ImVec4(1, 1, 0, 1), "Symbol Dictionary Selection:");
    ImGui::InputText("File Path", path_buf, sizeof(path_buf));
    app->symbol_file_path_ = path_buf;

    if (ImGui::Button("Load Dictionary from Path", ImVec2(-1, 30)) || (loaded_path != app->symbol_file_path_ && current_symbols.is_null())) {
        std::ifstream f(app->symbol_file_path_);
        if (f.is_open()) {
            try {
                current_symbols = nlohmann::json::parse(f);
                loaded_path = app->symbol_file_path_;
            } catch (...) {
                current_symbols = nullptr;
                loaded_path = "ERROR";
            }
        } else {
            current_symbols = nullptr;
            loaded_path = "NOT_FOUND";
        }
    }

    if (loaded_path == "ERROR") {
        ImGui::TextColored(ImVec4(1, 0, 0, 1), "Error: Failed to parse JSON file.");
    } else if (loaded_path == "NOT_FOUND") {
        ImGui::TextColored(ImVec4(1, 0, 0, 1), "Error: File not found at specified path.");
    } else if (!current_symbols.is_null()) {
        ImGui::TextColored(ImVec4(0, 1, 0, 1), "Dictionary Loaded: %zu symbols found.", current_symbols.is_array() ? current_symbols.size() : 0);
    }

    ImGui::Separator();

    if (!current_symbols.is_null() && current_symbols.is_array()) {
        ImGui::Text("Trigger Symbols:");
        if (ImGui::BeginTable("SymbolList", 3, ImGuiTableFlags_Borders | ImGuiTableFlags_RowBg | ImGuiTableFlags_ScrollY, ImVec2(0, 400))) {
            ImGui::TableSetupColumn("Symbol ID");
            ImGui::TableSetupColumn("Action");
            ImGui::TableHeadersRow();
            
            for (auto& sym : current_symbols) {
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                
                std::string id_str;
                if (sym.contains("display_name")) {
                    id_str = sym["display_name"].get<std::string>();
                } else if (sym.contains("id")) {
                    if (sym["id"].is_string()) {
                        id_str = sym["id"].get<std::string>();
                    } else if (sym["id"].is_number()) {
                        id_str = std::to_string(sym["id"].get<int>());
                    }
                }

                ImGui::Text("%s", id_str.c_str());
                
                ImGui::TableSetColumnIndex(1);
                if (ImGui::Button(("Trigger##" + id_str).c_str())) {
                    app->trigger_symbol(id_str, app->selected_led_effect_);
                    app->load_symbol_to_manual(sym);
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
