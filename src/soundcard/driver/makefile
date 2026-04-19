# Variables
CXX      = g++
CXXFLAGS = -std=c++17 -I. -I./imgui -I./imgui/backends
LIBS     = -lportaudio -lglfw -lGL -ldl -lpthread -ljsoncpp
TARGET   = sine_gen
IMGUI_DIR  = ./imgui
IMGUI_SRCS = $(wildcard $(IMGUI_DIR)/*.cpp)
IMGUI_OBJS = $(IMGUI_SRCS:.cpp=.o)

all: $(TARGET)

run: $(TARGET)
	./$(TARGET)

$(TARGET): main.o $(IMGUI_OBJS)
	$(CXX) $(CXXFLAGS) main.o $(IMGUI_OBJS) $(LIBS) -o $(TARGET)

main.o: main.cpp
	$(CXX) $(CXXFLAGS) -c main.cpp -o main.o

$(IMGUI_DIR)/%.o: $(IMGUI_DIR)/%.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f *.o $(IMGUI_DIR)/*.o $(TARGET)