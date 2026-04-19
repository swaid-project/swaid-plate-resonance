# Variables
CXX      = g++
CXXFLAGS = -std=c++17 -I. -I./imgui -I./imgui/backends
LIBS     = -lportaudio -lglfw -lGL -ldl -lrt -lpthread
TARGET   = sine_gen

IMGUI_DIR  = ./imgui
IMGUI_SRCS = $(wildcard $(IMGUI_DIR)/*.cpp)
IMGUI_OBJS = $(IMGUI_SRCS:.cpp=.o)

JSONS = json_test/json_test

all: $(TARGET) $(JSONS)

# --- NEW: Run target ---
run: $(TARGET)
	./$(TARGET)

run-json: $(JSONS)
	./$(JSONS)

$(TARGET): main.o $(IMGUI_OBJS)
	$(CXX) $(CXXFLAGS) main.o $(IMGUI_OBJS) $(LIBS) -o $(TARGET)

main.o: main.cpp json_test/json_driver_interface.h
	$(CXX) $(CXXFLAGS) -I./json_test -c main.cpp -o main.o

$(JSONS) : json_test/json_caller.cpp json_test/json_driver_interface.h
	$(CXX) $(CXXFLAGS) -I./json_test json_test/json_caller.cpp -o $(JSONS) -ljsoncpp -lrt

$(IMGUI_DIR)/%.o: $(IMGUI_DIR)/%.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f *.o $(IMGUI_DIR)/*.o $(TARGET) $(JSONS)
