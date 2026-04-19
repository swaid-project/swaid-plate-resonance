# Gerador de Áudio em Tempo Real — GUI

Aplicação C++ com interface gráfica para gerar áudio em tempo real com **baixa latência**, permitindo controlar **tipo de onda** e **frequência** de forma independente para cada ouvido (esquerdo/direito).

## Funcionalidades

- 🎧 **Frequência independente** por ouvido (20 Hz – 20 kHz)
- 🎵 **4 tipos de onda**: Seno, Quadrada, Dente-de-serra, Triângulo
- 🔊 Controlo de volume e mute
- 📊 Seleção de dispositivo de saída (auto-deteta Creative Labs SB0490)
- ⚡ **Latência ultra-baixa** (buffer de 64 frames ≈ 1.5 ms)
- 🎛️ Presets rápidos (440 Hz, Binaural, Teste Stereo)

## Stack Tecnológica

| Componente | Biblioteca |
|---|---|
| Áudio tempo real | [PortAudio](http://www.portaudio.com/) |
| Interface gráfica | [Dear ImGui](https://github.com/ocornut/imgui) |
| Janela / Input / OpenGL | [SDL2](https://www.libsdl.org/) |
| Rendering | OpenGL 3.3 Core |

## Dependências (Ubuntu)

```bash
sudo apt install build-essential libsdl2-dev portaudio19-dev libgl1-mesa-dev
```

O Dear ImGui é incluído diretamente no projeto (pasta `imgui/`).

## Compilar e Executar

```bash
# Clonar ImGui (se ainda não fizeste)
git clone --depth 1 https://github.com/ocornut/imgui.git imgui

# Compilar
make

# Executar
./gerador_gui
# ou
make run
```

## Estrutura do Projeto

```
├── gerador.cpp          # Versão original (terminal, sem GUI)
├── gerador_gui.cpp      # Nova versão com GUI (ImGui + SDL2 + PortAudio)
├── Makefile             # Build system
├── README.md            # Este ficheiro
└── imgui/               # Dear ImGui (clonado do GitHub)
    ├── imgui.cpp/h
    ├── imgui_draw.cpp
    ├── imgui_tables.cpp
    ├── imgui_widgets.cpp
    └── backends/
        ├── imgui_impl_sdl2.cpp/h
        └── imgui_impl_opengl3.cpp/h
```

## Notas sobre Latência

### Ubuntu (ALSA — o que usamos)
- Com `FRAMES_PER_BUFFER = 64` e sample rate 44100 Hz, a latência teórica é **~1.45 ms**.
- A latência real depende do driver ALSA e do dispositivo. Tipicamente 3–10 ms.
- Para latência ainda menor, podes usar **JACK** (`sudo apt install jackd2 qjackctl`).

### Windows (se quiseres portar)
- **WASAPI modo exclusivo**: latência ~3–5 ms sem instalar nada extra.
- **ASIO** (via ASIO4ALL ou driver nativo da Creative): latência ~1–3 ms.
  - Precisas do [ASIO SDK da Steinberg](https://www.steinberg.net/developers/) para compilar PortAudio com suporte ASIO.

### Creative Labs SB0490
- A aplicação tenta auto-detetar este dispositivo.
- Se não aparecer, verifica com `aplay -l` que o Linux a reconhece.

## Arquitetura de Baixa Latência

```
┌──────────────────────┐     lock-free (atomic)     ┌─────────────────────┐
│   GUI Thread (ImGui) │ ─────────────────────────→  │  Audio Callback     │
│   - Sliders freq L/R │    std::atomic<float>       │  - Gera amostras    │
│   - Combo onda L/R   │    std::atomic<int>         │  - Preenche buffer  │
│   - Volume / Mute    │                             │  - 64 frames/call   │
└──────────────────────┘                             └─────────────────────┘
                                                              │
                                                              ▼
                                                     ┌───────────────┐
                                                     │  PortAudio    │
                                                     │  → ALSA/JACK  │
                                                     │  → Hardware   │
                                                     └───────────────┘
```

A comunicação entre a GUI e o callback de áudio é feita com `std::atomic` (lock-free), garantindo que o callback **nunca bloqueia** — essencial para manter a latência mínima.
