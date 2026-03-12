// =============================================================================
// gerador_gui.cpp  –  Gerador de Áudio em Tempo Real com GUI (v2)
// =============================================================================
// Usa: PortAudio (áudio baixa latência) + Dear ImGui + SDL2 + OpenGL3 (GUI)
//
// v2: Volume por canal, fase por canal, link L/R, latência reduzida,
//     buffer size ajustável, visualização de onda, GUI dark-neon moderna.
//
// Compilar: make        (ver Makefile)
// =============================================================================

#include "imgui.h"
#include "imgui_impl_sdl2.h"
#include "imgui_impl_opengl3.h"

#include <SDL.h>
#include <SDL_opengl.h>
#include <portaudio.h>

#include <cmath>
#include <cstdio>
#include <cstring>
#include <atomic>
#include <string>
#include <vector>
#include <algorithm>

// ─── Constantes ──────────────────────────────────────────────────────────────
static constexpr int   SAMPLE_RATE        = 48000;  // 48 kHz → menos ms/frame
static constexpr int   DEFAULT_BUF_SIZE   = 32;     // 32 frames ≈ 0.67 ms !!
static constexpr float TWO_PI             = 6.283185307179586f;
static constexpr float DEG_TO_RAD         = TWO_PI / 360.0f;
static constexpr int   SCOPE_SIZE         = 1024;   // ring buffer para scope

// ─── Tipos de onda ───────────────────────────────────────────────────────────
enum WaveType {
    WAVE_SINE = 0,
    WAVE_SQUARE,
    WAVE_SAW,
    WAVE_TRIANGLE,
    WAVE_NOISE,
    WAVE_COUNT
};

static const char* waveNames[] = {
    u8"  Seno",
    u8"  Quadrada",
    u8"  Dente-de-serra",
    u8"  Triângulo",
    u8"  Ruído Branco"
};

// ─── Parâmetros partilhados (lock‑free) ──────────────────────────────────────
struct AudioParams {
    std::atomic<float> freqL{440.0f};
    std::atomic<float> freqR{440.0f};
    std::atomic<int>   waveL{WAVE_SINE};
    std::atomic<int>   waveR{WAVE_SINE};
    std::atomic<float> volL{0.5f};
    std::atomic<float> volR{0.5f};
    std::atomic<float> volMaster{1.0f};
    std::atomic<float> phaseOffL{0.0f};  // radianos
    std::atomic<float> phaseOffR{0.0f};
    std::atomic<float> dutyL{50.0f};   // duty cycle 1–99 %
    std::atomic<float> dutyR{50.0f};
    std::atomic<bool>  muted{false};
};

// ─── Ring buffer para visualização ───────────────────────────────────────────
struct ScopeBuffer {
    float samplesL[SCOPE_SIZE] = {};
    float samplesR[SCOPE_SIZE] = {};
    std::atomic<int> writePos{0};
};

// ─── Estado do callback ──────────────────────────────────────────────────────
struct CallbackState {
    float phaseL = 0.0f;
    float phaseR = 0.0f;
    uint32_t noiseL = 12345;
    uint32_t noiseR = 67890;
    AudioParams* params = nullptr;
    ScopeBuffer* scope  = nullptr;
};

// ─── Fast PRNG (xorshift32) ─────────────────────────────────────────────────
static inline float fastNoise(uint32_t& s) {
    s ^= s << 13; s ^= s >> 17; s ^= s << 5;
    return static_cast<float>(static_cast<int32_t>(s)) / 2147483648.0f;
}

// ─── Gerador de amostra (com duty cycle) ─────────────────────────────────────
// duty = 0.0–1.0  (0.5 = simétrico / default)
static inline float generateSample(float phase, int type, uint32_t& ns, float duty) {
    // Clamp duty para evitar divisão por zero
    duty = (duty < 0.01f) ? 0.01f : (duty > 0.99f) ? 0.99f : duty;
    float t = phase / TWO_PI; // normalizado [0, 1)
    switch (type) {
        case WAVE_SINE:
            // Duty cycle na seno: remapear t para que a metade positiva
            // dure 'duty' do período e a negativa '1-duty'.
            // Quando duty=0.5, mapped=t → sinf(2π·t) = sinf(phase) (inalterado).
        {
            float mapped;
            if (t < duty)
                mapped = 0.5f * t / duty;              // [0, duty) → [0, 0.5)
            else
                mapped = 0.5f + 0.5f * (t - duty) / (1.0f - duty); // [duty, 1) → [0.5, 1)
            return sinf(mapped * TWO_PI);
        }
        case WAVE_SQUARE:
            return (t < duty) ? 1.0f : -1.0f;
        case WAVE_SAW:
            // Dente-de-serra: rampa ascendente de -1 a +1 ao longo de todo o período.
            // Duty desloca o ponto onde cruza o zero.
            // Com duty=0.5 cruza o zero a meio → saw clássico.
            return -1.0f + 2.0f * t;
        case WAVE_TRIANGLE:
            // Triângulo: sobe de -1 a +1 durante 'duty' do período,
            // desce de +1 a -1 durante '1-duty'.
            if (t < duty)
                return -1.0f + 2.0f * (t / duty);
            else
                return 1.0f - 2.0f * ((t - duty) / (1.0f - duty));
        case WAVE_NOISE: return fastNoise(ns);
        default:         return 0.0f;
    }
}

// ─── Audio callback (thread de alta prioridade, NUNCA bloqueia) ──────────────
static int audioCallback(const void*, void* out,
                         unsigned long frames,
                         const PaStreamCallbackTimeInfo*,
                         PaStreamCallbackFlags,
                         void* ud)
{
    auto* st  = static_cast<CallbackState*>(ud);
    auto* buf = static_cast<float*>(out);

    const float fL  = st->params->freqL.load(std::memory_order_relaxed);
    const float fR  = st->params->freqR.load(std::memory_order_relaxed);
    const int   wL  = st->params->waveL.load(std::memory_order_relaxed);
    const int   wR  = st->params->waveR.load(std::memory_order_relaxed);
    const float vL  = st->params->volL.load(std::memory_order_relaxed);
    const float vR  = st->params->volR.load(std::memory_order_relaxed);
    const float vm  = st->params->volMaster.load(std::memory_order_relaxed);
    const float poL = st->params->phaseOffL.load(std::memory_order_relaxed);
    const float poR = st->params->phaseOffR.load(std::memory_order_relaxed);
    const float dL  = st->params->dutyL.load(std::memory_order_relaxed);
    const float dR  = st->params->dutyR.load(std::memory_order_relaxed);
    const bool  mut = st->params->muted.load(std::memory_order_relaxed);

    const float gL = mut ? 0.0f : vL * vm;
    const float gR = mut ? 0.0f : vR * vm;
    const float iL = TWO_PI * fL / static_cast<float>(SAMPLE_RATE);
    const float iR = TWO_PI * fR / static_cast<float>(SAMPLE_RATE);

    int sp = st->scope->writePos.load(std::memory_order_relaxed);

    for (unsigned long i = 0; i < frames; ++i) {
        float pL = st->phaseL + poL;
        if (pL >= TWO_PI) pL -= TWO_PI;
        float pR = st->phaseR + poR;
        if (pR >= TWO_PI) pR -= TWO_PI;

        float sL = gL * generateSample(pL, wL, st->noiseL, dL);
        float sR = gR * generateSample(pR, wR, st->noiseR, dR);

        *buf++ = sL;
        *buf++ = sR;

        st->scope->samplesL[sp] = sL;
        st->scope->samplesR[sp] = sR;
        sp = (sp + 1) % SCOPE_SIZE;

        st->phaseL += iL;
        if (st->phaseL >= TWO_PI) st->phaseL -= TWO_PI;
        st->phaseR += iR;
        if (st->phaseR >= TWO_PI) st->phaseR -= TWO_PI;
    }

    st->scope->writePos.store(sp, std::memory_order_relaxed);
    return paContinue;
}

// ─── Listar dispositivos de saída ────────────────────────────────────────────
struct DeviceInfo {
    int index; std::string name; double lowLat;
};

static std::vector<DeviceInfo> listOutputDevices() {
    std::vector<DeviceInfo> v;
    int n = Pa_GetDeviceCount();
    for (int i = 0; i < n; ++i) {
        const PaDeviceInfo* d = Pa_GetDeviceInfo(i);
        if (d && d->maxOutputChannels >= 2)
            v.push_back({i, d->name, d->defaultLowOutputLatency});
    }
    return v;
}

// ─── Estilo dark‑neon moderno ────────────────────────────────────────────────
static void applyStyle() {
    ImGuiStyle& s = ImGui::GetStyle();
    s.WindowRounding    = 8.0f;
    s.FrameRounding     = 6.0f;
    s.GrabRounding      = 4.0f;
    s.PopupRounding     = 6.0f;
    s.ScrollbarRounding = 6.0f;
    s.TabRounding       = 6.0f;
    s.ChildRounding     = 8.0f;
    s.WindowBorderSize  = 0.0f;
    s.FrameBorderSize   = 0.0f;
    s.FramePadding      = ImVec2(10, 6);
    s.ItemSpacing       = ImVec2(10, 8);
    s.ItemInnerSpacing  = ImVec2(8, 4);
    s.WindowPadding     = ImVec2(18, 14);
    s.ScrollbarSize     = 14.0f;
    s.GrabMinSize       = 14.0f;
    s.SeparatorTextBorderSize = 2.0f;

    ImVec4* c = s.Colors;
    // Backgrounds
    c[ImGuiCol_WindowBg]       = ImVec4(0.07f, 0.07f, 0.09f, 1.00f);
    c[ImGuiCol_ChildBg]        = ImVec4(0.09f, 0.09f, 0.12f, 1.00f);
    c[ImGuiCol_PopupBg]        = ImVec4(0.10f, 0.10f, 0.14f, 0.97f);
    // Borders
    c[ImGuiCol_Border]         = ImVec4(0.18f, 0.20f, 0.25f, 0.50f);
    // Frames
    c[ImGuiCol_FrameBg]        = ImVec4(0.13f, 0.13f, 0.17f, 1.00f);
    c[ImGuiCol_FrameBgHovered] = ImVec4(0.18f, 0.18f, 0.23f, 1.00f);
    c[ImGuiCol_FrameBgActive]  = ImVec4(0.22f, 0.22f, 0.28f, 1.00f);
    // Title
    c[ImGuiCol_TitleBg]        = ImVec4(0.05f, 0.05f, 0.07f, 1.00f);
    c[ImGuiCol_TitleBgActive]  = ImVec4(0.07f, 0.07f, 0.10f, 1.00f);
    // Scrollbar
    c[ImGuiCol_ScrollbarBg]       = ImVec4(0.05f, 0.05f, 0.07f, 0.50f);
    c[ImGuiCol_ScrollbarGrab]     = ImVec4(0.22f, 0.22f, 0.28f, 1.00f);
    c[ImGuiCol_ScrollbarGrabHovered] = ImVec4(0.30f, 0.30f, 0.38f, 1.00f);
    c[ImGuiCol_ScrollbarGrabActive]  = ImVec4(0.00f, 0.78f, 0.85f, 1.00f);
    // Accent = ciano
    c[ImGuiCol_CheckMark]      = ImVec4(0.00f, 0.82f, 0.88f, 1.00f);
    c[ImGuiCol_SliderGrab]     = ImVec4(0.00f, 0.78f, 0.85f, 1.00f);
    c[ImGuiCol_SliderGrabActive] = ImVec4(0.00f, 0.92f, 1.00f, 1.00f);
    // Buttons
    c[ImGuiCol_Button]         = ImVec4(0.14f, 0.14f, 0.18f, 1.00f);
    c[ImGuiCol_ButtonHovered]  = ImVec4(0.00f, 0.58f, 0.65f, 0.75f);
    c[ImGuiCol_ButtonActive]   = ImVec4(0.00f, 0.78f, 0.85f, 1.00f);
    // Headers (combo etc)
    c[ImGuiCol_Header]         = ImVec4(0.14f, 0.14f, 0.18f, 1.00f);
    c[ImGuiCol_HeaderHovered]  = ImVec4(0.00f, 0.50f, 0.58f, 0.45f);
    c[ImGuiCol_HeaderActive]   = ImVec4(0.00f, 0.78f, 0.85f, 1.00f);
    // Separator
    c[ImGuiCol_Separator]      = ImVec4(0.20f, 0.22f, 0.28f, 1.00f);
    c[ImGuiCol_SeparatorHovered] = ImVec4(0.00f, 0.65f, 0.72f, 1.00f);
    c[ImGuiCol_SeparatorActive]  = ImVec4(0.00f, 0.78f, 0.85f, 1.00f);
    // Tabs
    c[ImGuiCol_Tab]              = ImVec4(0.10f, 0.10f, 0.14f, 1.00f);
    c[ImGuiCol_TabHovered]       = ImVec4(0.00f, 0.62f, 0.70f, 0.55f);
    c[ImGuiCol_TabActive]        = ImVec4(0.00f, 0.52f, 0.60f, 1.00f);
    c[ImGuiCol_TabSelectedOverline] = ImVec4(0.00f, 0.78f, 0.85f, 1.00f);
    // Text
    c[ImGuiCol_Text]           = ImVec4(0.90f, 0.91f, 0.94f, 1.00f);
    c[ImGuiCol_TextDisabled]   = ImVec4(0.45f, 0.46f, 0.50f, 1.00f);
    // Plots
    c[ImGuiCol_PlotLines]      = ImVec4(0.00f, 0.78f, 0.85f, 1.00f);
    c[ImGuiCol_PlotLinesHovered] = ImVec4(0.00f, 0.92f, 1.00f, 1.00f);
    c[ImGuiCol_PlotHistogram]    = ImVec4(1.00f, 0.55f, 0.10f, 1.00f);
    c[ImGuiCol_PlotHistogramHovered] = ImVec4(1.00f, 0.70f, 0.30f, 1.00f);
    // Table
    c[ImGuiCol_TableHeaderBg]    = ImVec4(0.10f, 0.10f, 0.14f, 1.00f);
    c[ImGuiCol_TableBorderStrong] = ImVec4(0.20f, 0.20f, 0.25f, 1.00f);
    c[ImGuiCol_TableBorderLight]  = ImVec4(0.16f, 0.16f, 0.20f, 1.00f);
}

// ─── Helper: painel de canal ─────────────────────────────────────────────────
static void drawChannelPanel(const char* title, const char* id,
                             int& wave, float& freq, float& vol,
                             float& phaseDeg, float& duty,
                             const ImVec4& accent, float panelWidth)
{
    ImGui::PushID(id);
    ImGui::PushStyleColor(ImGuiCol_ChildBg, ImVec4(0.10f, 0.10f, 0.13f, 1.0f));
    ImGui::PushStyleVar(ImGuiStyleVar_ChildRounding, 10.0f);
    // Largura explícita para que os dois painéis caibam lado a lado
    ImGui::BeginChild(id, ImVec2(panelWidth, 340), ImGuiChildFlags_Borders);

    // Título
    ImGui::PushStyleColor(ImGuiCol_Text, accent);
    ImGui::SetWindowFontScale(1.2f);
    ImGui::Text("%s", title);
    ImGui::SetWindowFontScale(1.0f);
    ImGui::PopStyleColor();

    // Linha decorativa
    ImVec2 p = ImGui::GetCursorScreenPos();
    ImGui::GetWindowDrawList()->AddRectFilled(
        p, ImVec2(p.x + ImGui::GetContentRegionAvail().x, p.y + 2),
        ImGui::ColorConvertFloat4ToU32(ImVec4(accent.x, accent.y, accent.z, 0.4f)));
    ImGui::Dummy(ImVec2(0, 6));

    float iw = ImGui::GetContentRegionAvail().x;  // largura dentro do painel

    // Onda
    ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.55f, 0.56f, 0.60f, 1.0f));
    ImGui::Text("ONDA");
    ImGui::PopStyleColor();
    ImGui::SetNextItemWidth(iw);
    ImGui::Combo("##wave", &wave, waveNames, WAVE_COUNT);
    ImGui::Spacing();

    // Frequência
    ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.55f, 0.56f, 0.60f, 1.0f));
    ImGui::Text(u8"FREQUÊNCIA");
    ImGui::PopStyleColor();
    ImGui::SetNextItemWidth(iw);
    ImGui::PushStyleColor(ImGuiCol_SliderGrab, accent);
    ImGui::SliderFloat("##freq", &freq, 20.0f, 20000.0f,
                       "%.1f Hz", ImGuiSliderFlags_Logarithmic);
    ImGui::PopStyleColor();
    ImGui::SetNextItemWidth(iw * 0.45f);
    ImGui::InputFloat("Hz##exact", &freq, 1.0f, 10.0f, "%.2f");
    freq = std::clamp(freq, 20.0f, 20000.0f);
    ImGui::Spacing();

    // Volume (0–100)
    ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.55f, 0.56f, 0.60f, 1.0f));
    ImGui::Text("VOLUME");
    ImGui::PopStyleColor();
    ImGui::SetNextItemWidth(iw);
    ImGui::PushStyleColor(ImGuiCol_SliderGrab, accent);
    ImGui::SliderFloat("##vol", &vol, 0.0f, 100.0f, "%.0f%%");
    ImGui::PopStyleColor();
    ImGui::Spacing();

    // Fase
    ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.55f, 0.56f, 0.60f, 1.0f));
    ImGui::Text("FASE");
    ImGui::PopStyleColor();
    ImGui::SetNextItemWidth(iw);
    ImGui::PushStyleColor(ImGuiCol_SliderGrab, accent);
    ImGui::SliderFloat("##phase", &phaseDeg, 0.0f, 360.0f, u8"%.1f\u00b0");
    ImGui::PopStyleColor();
    ImGui::Spacing();

    // Duty Cycle
    ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.55f, 0.56f, 0.60f, 1.0f));
    ImGui::Text("DUTY CYCLE");
    ImGui::PopStyleColor();
    ImGui::SetNextItemWidth(iw);
    ImGui::PushStyleColor(ImGuiCol_SliderGrab, accent);
    ImGui::SliderFloat("##duty", &duty, 1.0f, 99.0f, "%.0f%%");
    ImGui::PopStyleColor();

    ImGui::EndChild();
    ImGui::PopStyleVar();
    ImGui::PopStyleColor();
    ImGui::PopID();
}

// =============================================================================
//  MAIN
// =============================================================================
int main(int, char*[]) {

    // ── PortAudio ────────────────────────────────────────────────────────────
    PaError paErr = Pa_Initialize();
    if (paErr != paNoError) {
        fprintf(stderr, "PortAudio Init: %s\n", Pa_GetErrorText(paErr));
        return 1;
    }
    auto devices = listOutputDevices();
    if (devices.empty()) {
        fprintf(stderr, "Sem dispositivos!\n");
        Pa_Terminate(); return 1;
    }

    int selDev = 0;
    for (size_t i = 0; i < devices.size(); ++i)
        if (devices[i].name.find("Creative") != std::string::npos ||
            devices[i].name.find("SB0490")   != std::string::npos)
        { selDev = (int)i; break; }

    // ── SDL2 + OpenGL ────────────────────────────────────────────────────────
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_TIMER) != 0) {
        fprintf(stderr, "SDL: %s\n", SDL_GetError());
        Pa_Terminate(); return 1;
    }
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);

    SDL_Window* win = SDL_CreateWindow(
        u8"Gerador de Áudio v2",
        SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
        920, 740,
        SDL_WINDOW_OPENGL | SDL_WINDOW_RESIZABLE | SDL_WINDOW_ALLOW_HIGHDPI);
    if (!win) { SDL_Quit(); Pa_Terminate(); return 1; }

    SDL_GLContext gl = SDL_GL_CreateContext(win);
    SDL_GL_MakeCurrent(win, gl);
    SDL_GL_SetSwapInterval(1);

    // ── ImGui ────────────────────────────────────────────────────────────────
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;
    applyStyle();
    io.FontGlobalScale = 1.1f;
    ImGui_ImplSDL2_InitForOpenGL(win, gl);
    ImGui_ImplOpenGL3_Init("#version 330");

    // ── Estado ───────────────────────────────────────────────────────────────
    AudioParams params;
    ScopeBuffer scope;
    CallbackState cbSt;
    cbSt.params = &params;
    cbSt.scope  = &scope;

    float gFreqL = 440, gFreqR = 440;
    int   gWaveL = 0, gWaveR = 0;
    float gVolL = 50.0f, gVolR = 50.0f, gMaster = 100.0f;  // 0–100 na GUI
    float gPhaseL = 0, gPhaseR = 0;
    float gDutyL = 50.0f, gDutyR = 50.0f;  // 1–99 na GUI (%)
    bool  gMuted = false, gLink = false;
    int   gDev = selDev, gBuf = DEFAULT_BUF_SIZE;
    bool  streamOk = false;
    PaStream* stream = nullptr;

    // ── Abrir stream ─────────────────────────────────────────────────────────
    auto openStream = [&]() {
        if (stream) { Pa_StopStream(stream); Pa_CloseStream(stream); stream = nullptr; streamOk = false; }
        cbSt.phaseL = cbSt.phaseR = 0;

        const PaDeviceInfo* di = Pa_GetDeviceInfo(devices[gDev].index);
        PaStreamParameters op{};
        op.device           = devices[gDev].index;
        op.channelCount     = 2;
        op.sampleFormat     = paFloat32;
        op.suggestedLatency = di ? di->defaultLowOutputLatency : 0.002;

        paErr = Pa_OpenStream(&stream, nullptr, &op,
                              SAMPLE_RATE, gBuf,
                              paClipOff | paDitherOff | paPrimeOutputBuffersUsingStreamCallback,
                              audioCallback, &cbSt);
        if (paErr != paNoError) {
            fprintf(stderr, "OpenStream: %s\n", Pa_GetErrorText(paErr));
            stream = nullptr; return;
        }
        paErr = Pa_StartStream(stream);
        if (paErr != paNoError) {
            fprintf(stderr, "StartStream: %s\n", Pa_GetErrorText(paErr));
            Pa_CloseStream(stream); stream = nullptr; return;
        }
        streamOk = true;
        const PaStreamInfo* si = Pa_GetStreamInfo(stream);
        if (si) printf("[AUDIO] \"%s\" buf=%d lat=%.2fms SR=%.0f\n",
                       devices[gDev].name.c_str(), gBuf,
                       si->outputLatency*1000, si->sampleRate);
    };
    openStream();

    // Cores
    ImVec4 colL = ImVec4(0.20f, 0.82f, 1.00f, 1.00f);
    ImVec4 colR = ImVec4(1.00f, 0.50f, 0.22f, 1.00f);

    // ── Main loop ────────────────────────────────────────────────────────────
    bool run = true;
    while (run) {
        SDL_Event ev;
        while (SDL_PollEvent(&ev)) {
            ImGui_ImplSDL2_ProcessEvent(&ev);
            if (ev.type == SDL_QUIT) run = false;
            if (ev.type == SDL_WINDOWEVENT && ev.window.event == SDL_WINDOWEVENT_CLOSE)
                run = false;
        }

        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplSDL2_NewFrame();
        ImGui::NewFrame();

        // ── Fullscreen window ────────────────────────────────────────────────
        const ImGuiViewport* vp = ImGui::GetMainViewport();
        ImGui::SetNextWindowPos(vp->WorkPos);
        ImGui::SetNextWindowSize(vp->WorkSize);
        ImGui::Begin("##main", nullptr,
            ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoMove |
            ImGuiWindowFlags_NoCollapse | ImGuiWindowFlags_NoTitleBar |
            ImGuiWindowFlags_NoBringToFrontOnFocus);

        // ─── HEADER ─────────────────────────────────────────────────────
        {
            ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.00f, 0.85f, 0.92f, 1.0f));
            ImGui::SetWindowFontScale(1.45f);
            ImGui::Text(u8"  GERADOR DE ÁUDIO");
            ImGui::SetWindowFontScale(1.0f);
            ImGui::PopStyleColor();

            ImGui::SameLine(ImGui::GetWindowWidth() - 340);
            if (streamOk) {
                const PaStreamInfo* si = Pa_GetStreamInfo(stream);
                float lat = si ? (float)(si->outputLatency * 1000.0) : 0;
                ImVec4 bc = (lat < 4) ? ImVec4(0.15f,0.95f,0.45f,1)
                          : (lat < 8) ? ImVec4(1,0.8f,0.2f,1)
                          :              ImVec4(1,0.3f,0.3f,1);
                ImGui::PushStyleColor(ImGuiCol_Text, bc);
                ImGui::Text(u8"● LIVE  %.1f ms  |  %d Hz  |  buf %d",
                            lat, SAMPLE_RATE, gBuf);
                ImGui::PopStyleColor();
            } else {
                ImGui::TextColored(ImVec4(1,0.3f,0.3f,1), u8"● OFFLINE");
            }

            // Linha decorativa sob header
            ImVec2 p = ImGui::GetCursorScreenPos();
            ImDrawList* dl = ImGui::GetWindowDrawList();
            float w = ImGui::GetContentRegionAvail().x;
            dl->AddRectFilledMultiColor(
                p, ImVec2(p.x + w, p.y + 2),
                ImGui::ColorConvertFloat4ToU32(colL),
                ImGui::ColorConvertFloat4ToU32(colR),
                ImGui::ColorConvertFloat4ToU32(colR),
                ImGui::ColorConvertFloat4ToU32(colL));
            ImGui::Dummy(ImVec2(0, 8));
        }

        // ─── DISPOSITIVO + BUFFER ────────────────────────────────────────
        {
            ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.50f, 0.51f, 0.55f, 1));
            ImGui::Text(u8"DISPOSITIVO");
            ImGui::PopStyleColor();

            ImGui::SetNextItemWidth(ImGui::GetContentRegionAvail().x * 0.62f);
            if (ImGui::BeginCombo("##dev", devices[gDev].name.c_str())) {
                for (int i = 0; i < (int)devices.size(); ++i) {
                    char lb[300];
                    snprintf(lb, sizeof(lb), "[%d] %s  (%.1fms)",
                             devices[i].index, devices[i].name.c_str(),
                             devices[i].lowLat*1000);
                    if (ImGui::Selectable(lb, i==gDev)) { gDev=i; openStream(); }
                }
                ImGui::EndCombo();
            }

            ImGui::SameLine();
            ImGui::SetNextItemWidth(130);
            static const int bSz[] = {16,32,64,128,256,512};
            static const char* bLb[] = {"16","32","64","128","256","512"};
            int bi=1; for(int i=0;i<6;++i) if(bSz[i]==gBuf) bi=i;
            if (ImGui::BeginCombo("Buffer##bs", bLb[bi])) {
                for (int i = 0; i < 6; ++i) {
                    char t[80]; snprintf(t,80,"%d (%.2fms)", bSz[i], bSz[i]*1000.0f/SAMPLE_RATE);
                    if (ImGui::Selectable(t, bSz[i]==gBuf)) { gBuf=bSz[i]; openStream(); }
                }
                ImGui::EndCombo();
            }
        }

        ImGui::Spacing();

        // ─── LINK L/R ────────────────────────────────────────────────────
        {
            ImGui::PushStyleColor(ImGuiCol_CheckMark, ImVec4(1.0f,0.85f,0.0f,1));
            ImGui::Checkbox(u8"  Link L/R", &gLink);
            ImGui::PopStyleColor();
            if (gLink) {
                ImGui::SameLine();
                ImGui::TextColored(ImVec4(1,0.85f,0,0.6f),
                    u8" — L controla R");
            }
        }

        ImGui::Spacing();

        // ─── PAINÉIS L / R ──────────────────────────────────────────────
        {
            float avail = ImGui::GetContentRegionAvail().x;
            float pw = (avail - 14.0f) * 0.5f;

            // Coluna L
            drawChannelPanel(u8"  ESQUERDO  (L)", "L",
                             gWaveL, gFreqL, gVolL, gPhaseL, gDutyL, colL, pw);

            ImGui::SameLine(0, 14);

            // Coluna R
            drawChannelPanel(u8"  DIREITO  (R)", "R",
                             gWaveR, gFreqR, gVolR, gPhaseR, gDutyR, colR, pw);

            if (gLink) {
                gFreqR=gFreqL; gWaveR=gWaveL;
                gVolR=gVolL;   gPhaseR=gPhaseL;
                gDutyR=gDutyL;
            }
        }

        ImGui::Spacing();

        // ─── MASTER VOLUME + MUTE ───────────────────────────────────────
        {
            ImGui::PushStyleColor(ImGuiCol_ChildBg, ImVec4(0.10f,0.10f,0.13f,1));
            ImGui::PushStyleVar(ImGuiStyleVar_ChildRounding, 10);
            ImGui::BeginChild("##master", ImVec2(0,56), ImGuiChildFlags_Borders);

            // Mute toggle
            ImVec4 mCol = gMuted ? ImVec4(0.85f,0.12f,0.12f,1) : ImVec4(0.14f,0.14f,0.18f,1);
            ImVec4 mHov = gMuted ? ImVec4(0.95f,0.20f,0.20f,1) : ImVec4(0.22f,0.22f,0.28f,1);
            ImGui::PushStyleColor(ImGuiCol_Button, mCol);
            ImGui::PushStyleColor(ImGuiCol_ButtonHovered, mHov);
            ImGui::PushStyleVar(ImGuiStyleVar_FrameRounding, 8);
            if (ImGui::Button(gMuted ? u8"  MUTED " : u8"  MUTE  ", ImVec2(100,34)))
                gMuted = !gMuted;
            ImGui::PopStyleVar();
            ImGui::PopStyleColor(2);

            ImGui::SameLine();
            ImGui::SetNextItemWidth(ImGui::GetContentRegionAvail().x - 8);
            ImGui::PushStyleColor(ImGuiCol_SliderGrab, ImVec4(0.82f,0.82f,0.88f,1));
            ImGui::SliderFloat("##mst", &gMaster, 0, 100, "Master  %.0f%%");
            ImGui::PopStyleColor();

            ImGui::EndChild();
            ImGui::PopStyleVar();
            ImGui::PopStyleColor();
        }

        ImGui::Spacing();

        // ─── SCOPE / WAVEFORM (snapshot 2 períodos, L e R sobrepostos) ────
        {
            ImGui::PushStyleColor(ImGuiCol_ChildBg, ImVec4(0.05f,0.05f,0.07f,1));
            ImGui::PushStyleVar(ImGuiStyleVar_ChildRounding, 10);
            float sh = std::max(120.0f, ImGui::GetContentRegionAvail().y - 60.0f);
            ImGui::BeginChild("##scope", ImVec2(0, sh), ImGuiChildFlags_Borders);

            ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.42f,0.43f,0.48f,1));
            float minFreq = std::min(gFreqL, gFreqR);
            float windowMs = (2.0f / minFreq) * 1000.0f;
            char scopeLabel[128];
            snprintf(scopeLabel, sizeof(scopeLabel),
                     u8"FORMA DE ONDA  (janela = 2 períodos de %.1f Hz = %.2f ms)", minFreq, windowMs);
            ImGui::Text("%s", scopeLabel);
            ImGui::PopStyleColor();

            // Gerar snapshot matemático: janela temporal = 2 períodos da freq mais baixa
            static constexpr int SNAP_N = 512;
            static float snapL[SNAP_N], snapR[SNAP_N];

            uint32_t dummyNL = 11111, dummyNR = 22222;

            // Duração total da janela em segundos = 2 / min(freqL, freqR)
            float totalTime = 2.0f / minFreq;

            for (int i = 0; i < SNAP_N; ++i) {
                float t = static_cast<float>(i) / static_cast<float>(SNAP_N) * totalTime;

                // Fase = 2π × freq × t + offset
                float phL = TWO_PI * gFreqL * t + gPhaseL * DEG_TO_RAD;
                float phR = TWO_PI * gFreqR * t + gPhaseR * DEG_TO_RAD;

                // Manter fase em [0, TWO_PI)
                phL = fmodf(phL, TWO_PI);
                phR = fmodf(phR, TWO_PI);
                if (phL < 0) phL += TWO_PI;
                if (phR < 0) phR += TWO_PI;

                float aL = (gVolL / 100.0f) * (gMaster / 100.0f);
                float aR = (gVolR / 100.0f) * (gMaster / 100.0f);

                snapL[i] = aL * generateSample(phL, gWaveL, dummyNL, gDutyL / 100.0f);
                snapR[i] = aR * generateSample(phR, gWaveR, dummyNR, gDutyR / 100.0f);
            }

            float pw = ImGui::GetContentRegionAvail().x;
            float ph = ImGui::GetContentRegionAvail().y - 8.0f;

            // Desenhar ambas as ondas sobrepostas usando ImDrawList
            ImVec2 origin = ImGui::GetCursorScreenPos();
            ImDrawList* dl = ImGui::GetWindowDrawList();

            // Fundo do gráfico
            dl->AddRectFilled(origin, ImVec2(origin.x + pw, origin.y + ph),
                              ImGui::ColorConvertFloat4ToU32(ImVec4(0.04f,0.04f,0.06f,1)));

            // Linha central (zero)
            float midY = origin.y + ph * 0.5f;
            dl->AddLine(ImVec2(origin.x, midY), ImVec2(origin.x + pw, midY),
                        ImGui::ColorConvertFloat4ToU32(ImVec4(0.25f,0.25f,0.30f,0.6f)), 1.0f);

            // Linhas de grid ±0.5
            float q1Y = origin.y + ph * 0.25f;
            float q3Y = origin.y + ph * 0.75f;
            ImU32 gridCol = ImGui::ColorConvertFloat4ToU32(ImVec4(0.18f,0.18f,0.22f,0.4f));
            dl->AddLine(ImVec2(origin.x, q1Y), ImVec2(origin.x + pw, q1Y), gridCol, 1.0f);
            dl->AddLine(ImVec2(origin.x, q3Y), ImVec2(origin.x + pw, q3Y), gridCol, 1.0f);

            // Linha vertical a meio (1 período da freq mais baixa)
            float halfX = origin.x + pw * 0.5f;
            dl->AddLine(ImVec2(halfX, origin.y), ImVec2(halfX, origin.y + ph), gridCol, 1.0f);

            // Labels de amplitude
            dl->AddText(ImVec2(origin.x + 4, origin.y + 2),
                        ImGui::ColorConvertFloat4ToU32(ImVec4(0.4f,0.4f,0.45f,1)), "+1.0");
            dl->AddText(ImVec2(origin.x + 4, midY - 14),
                        ImGui::ColorConvertFloat4ToU32(ImVec4(0.4f,0.4f,0.45f,1)), " 0.0");
            dl->AddText(ImVec2(origin.x + 4, origin.y + ph - 16),
                        ImGui::ColorConvertFloat4ToU32(ImVec4(0.4f,0.4f,0.45f,1)), "-1.0");

            // Labels de tempo no eixo X
            {
                char tbuf[32];
                ImU32 tCol = ImGui::ColorConvertFloat4ToU32(ImVec4(0.4f,0.4f,0.45f,1));
                // t=0
                dl->AddText(ImVec2(origin.x + 4, origin.y + ph + 2), tCol, "0");
                // t = T (1 período)
                snprintf(tbuf, sizeof(tbuf), "%.2fms", windowMs * 0.5f);
                dl->AddText(ImVec2(halfX - 16, origin.y + ph + 2), tCol, tbuf);
                // t = 2T
                snprintf(tbuf, sizeof(tbuf), "%.2fms", windowMs);
                dl->AddText(ImVec2(origin.x + pw - 50, origin.y + ph + 2), tCol, tbuf);
            }

            // Desenhar onda L (ciano)
            ImU32 colLU32 = ImGui::ColorConvertFloat4ToU32(ImVec4(colL.x, colL.y, colL.z, 0.9f));
            for (int i = 0; i < SNAP_N - 1; ++i) {
                float x0 = origin.x + (static_cast<float>(i) / (SNAP_N-1)) * pw;
                float x1 = origin.x + (static_cast<float>(i+1) / (SNAP_N-1)) * pw;
                float y0 = midY - snapL[i] * (ph * 0.48f);
                float y1 = midY - snapL[i+1] * (ph * 0.48f);
                dl->AddLine(ImVec2(x0, y0), ImVec2(x1, y1), colLU32, 2.0f);
            }

            // Desenhar onda R (laranja)
            ImU32 colRU32 = ImGui::ColorConvertFloat4ToU32(ImVec4(colR.x, colR.y, colR.z, 0.85f));
            for (int i = 0; i < SNAP_N - 1; ++i) {
                float x0 = origin.x + (static_cast<float>(i) / (SNAP_N-1)) * pw;
                float x1 = origin.x + (static_cast<float>(i+1) / (SNAP_N-1)) * pw;
                float y0 = midY - snapR[i] * (ph * 0.48f);
                float y1 = midY - snapR[i+1] * (ph * 0.48f);
                dl->AddLine(ImVec2(x0, y0), ImVec2(x1, y1), colRU32, 2.0f);
            }

            // Legenda
            float legX = origin.x + pw - 140;
            float legY = origin.y + 6;
            dl->AddLine(ImVec2(legX, legY+6), ImVec2(legX+20, legY+6), colLU32, 2.5f);
            dl->AddText(ImVec2(legX+24, legY),
                        ImGui::ColorConvertFloat4ToU32(colL), "L");
            dl->AddLine(ImVec2(legX+50, legY+6), ImVec2(legX+70, legY+6), colRU32, 2.5f);
            dl->AddText(ImVec2(legX+74, legY),
                        ImGui::ColorConvertFloat4ToU32(colR), "R");

            // Reservar espaço para que ImGui saiba o tamanho
            ImGui::Dummy(ImVec2(pw, ph));

            ImGui::EndChild();
            ImGui::PopStyleVar();
            ImGui::PopStyleColor();
        }

        ImGui::Spacing();

        // ─── PRESETS ─────────────────────────────────────────────────────
        {
            ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.42f,0.43f,0.48f,1));
            ImGui::Text("PRESETS");
            ImGui::PopStyleColor();
            ImGui::SameLine();
            ImGui::PushStyleVar(ImGuiStyleVar_FrameRounding, 14);

            if (ImGui::Button(u8" 440 Hz Seno ")) {
                gFreqL=gFreqR=440; gWaveL=gWaveR=0; gPhaseL=gPhaseR=0; gDutyL=gDutyR=50;
            }
            ImGui::SameLine();
            if (ImGui::Button(u8" Binaural 40 Hz ")) {
                gFreqL=400; gFreqR=440; gWaveL=gWaveR=0; gPhaseL=gPhaseR=0; gDutyL=gDutyR=50;
            }
            ImGui::SameLine();
            if (ImGui::Button(u8" Stereo Test ")) {
                gFreqL=261.63f; gFreqR=329.63f; gWaveL=WAVE_SAW; gWaveR=WAVE_TRIANGLE; gDutyL=gDutyR=50;
            }
            ImGui::SameLine();
            if (ImGui::Button(u8" Phase 180\u00b0 ")) {
                gFreqL=gFreqR=440; gWaveL=gWaveR=0; gPhaseL=0; gPhaseR=180; gDutyL=gDutyR=50;
            }
            ImGui::SameLine();
            if (ImGui::Button(u8" Detune ")) {
                gFreqL=440; gFreqR=442; gWaveL=gWaveR=WAVE_SAW;
                gVolL=gVolR=40.0f; gPhaseL=gPhaseR=0; gDutyL=gDutyR=50;
            }

            ImGui::PopStyleVar();
        }

        ImGui::End();

        // ── Enviar params (volumes GUI 0–100 → callback 0.0–1.0) ─────────
        params.freqL.store(gFreqL, std::memory_order_relaxed);
        params.freqR.store(gFreqR, std::memory_order_relaxed);
        params.waveL.store(gWaveL, std::memory_order_relaxed);
        params.waveR.store(gWaveR, std::memory_order_relaxed);
        params.volL.store(gVolL / 100.0f, std::memory_order_relaxed);
        params.volR.store(gVolR / 100.0f, std::memory_order_relaxed);
        params.volMaster.store(gMaster / 100.0f, std::memory_order_relaxed);
        params.phaseOffL.store(gPhaseL * DEG_TO_RAD, std::memory_order_relaxed);
        params.phaseOffR.store(gPhaseR * DEG_TO_RAD, std::memory_order_relaxed);
        params.dutyL.store(gDutyL / 100.0f, std::memory_order_relaxed);
        params.dutyR.store(gDutyR / 100.0f, std::memory_order_relaxed);
        params.muted.store(gMuted, std::memory_order_relaxed);

        // ── Render ───────────────────────────────────────────────────────
        ImGui::Render();
        int dw, dh;
        SDL_GL_GetDrawableSize(win, &dw, &dh);
        glViewport(0, 0, dw, dh);
        glClearColor(0.07f, 0.07f, 0.09f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT);
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        SDL_GL_SwapWindow(win);
    }

    // ── Cleanup ──────────────────────────────────────────────────────────
    if (stream) { Pa_StopStream(stream); Pa_CloseStream(stream); }
    Pa_Terminate();
    ImGui_ImplOpenGL3_Shutdown();
    ImGui_ImplSDL2_Shutdown();
    ImGui::DestroyContext();
    SDL_GL_DeleteContext(gl);
    SDL_DestroyWindow(win);
    SDL_Quit();
    return 0;
}
