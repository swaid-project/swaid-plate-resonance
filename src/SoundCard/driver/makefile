# Variables
CXX      = g++
CXXFLAGS = -std=c++17 -I. -I./imgui -I./imgui/backends
LIBS     = -lportaudio -lglfw -lGL -ldl
TARGET   = sine_gen

IMGUI_DIR  = ./imgui
IMGUI_SRCS = $(wildcard $(IMGUI_DIR)/*.cpp)
IMGUI_OBJS = $(IMGUI_SRCS:.cpp=.o)

# ImGui backend files (GLFW + OpenGL3)
IMGUI_BACKEND_SRCS = $(IMGUI_DIR)/backends/imgui_impl_glfw.cpp $(IMGUI_DIR)/backends/imgui_impl_opengl3.cpp
IMGUI_BACKEND_OBJS = $(IMGUI_BACKEND_SRCS:.cpp=.o)

all: $(TARGET)

# --- NEW: Run target ---
run: $(TARGET)
	./$(TARGET)

$(TARGET): main.o $(IMGUI_OBJS) $(IMGUI_BACKEND_OBJS)
	$(CXX) $(CXXFLAGS) main.o $(IMGUI_OBJS) $(IMGUI_BACKEND_OBJS) $(LIBS) -o $(TARGET)

main.o: main.cpp
	$(CXX) $(CXXFLAGS) -c main.cpp -o main.o

$(IMGUI_DIR)/%.o: $(IMGUI_DIR)/%.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f *.o $(IMGUI_DIR)/*.o $(IMGUI_DIR)/backends/*.o $(TARGET)
