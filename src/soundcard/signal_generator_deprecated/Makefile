# ==============================================================================
# Makefile — Gerador de Áudio em Tempo Real (GUI)
# ==============================================================================
# Dependências: SDL2, PortAudio, OpenGL, Dear ImGui (clonado em ./imgui/)
#
# Uso:
#   make          → compila gerador_gui
#   make clean    → limpa binário e objetos
#   make run      → compila e executa
# ==============================================================================

CXX      := g++
CXXFLAGS := -O2 -std=c++17 -Wall -Wextra

# Paths do ImGui
IMGUI_DIR := imgui
IMGUI_BACKENDS := $(IMGUI_DIR)/backends

# Includes
INCLUDES := -I$(IMGUI_DIR) -I$(IMGUI_BACKENDS)

# Flags de SDL2, PortAudio e OpenGL via pkg-config
SDL2_CFLAGS  := $(shell pkg-config --cflags sdl2)
SDL2_LIBS    := $(shell pkg-config --libs sdl2)
PA_CFLAGS    := $(shell pkg-config --cflags portaudio-2.0)
PA_LIBS      := $(shell pkg-config --libs portaudio-2.0)
GL_LIBS      := $(shell pkg-config --libs gl)

ALL_CFLAGS := $(CXXFLAGS) $(INCLUDES) $(SDL2_CFLAGS) $(PA_CFLAGS)
ALL_LIBS   := $(SDL2_LIBS) $(PA_LIBS) $(GL_LIBS) -lm

# Fontes ImGui necessárias
IMGUI_SRCS := \
	$(IMGUI_DIR)/imgui.cpp \
	$(IMGUI_DIR)/imgui_draw.cpp \
	$(IMGUI_DIR)/imgui_tables.cpp \
	$(IMGUI_DIR)/imgui_widgets.cpp \
	$(IMGUI_BACKENDS)/imgui_impl_sdl2.cpp \
	$(IMGUI_BACKENDS)/imgui_impl_opengl3.cpp

# Objetos
IMGUI_OBJS := $(IMGUI_SRCS:.cpp=.o)
APP_OBJ    := gerador_gui.o

TARGET := gerador_gui

# --- Regras -------------------------------------------------------------------

all: $(TARGET)

$(TARGET): $(APP_OBJ) $(IMGUI_OBJS)
	$(CXX) $(ALL_CFLAGS) -o $@ $^ $(ALL_LIBS)

%.o: %.cpp
	$(CXX) $(ALL_CFLAGS) -c -o $@ $<

run: $(TARGET)
	./$(TARGET)

clean:
	rm -f $(TARGET) $(APP_OBJ) $(IMGUI_OBJS)

.PHONY: all clean run
