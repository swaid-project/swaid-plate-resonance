# Variables
CXX       = g++
PYTHON    = python3
CXXFLAGS  = -std=c++17 -I. -I./imgui -I./imgui/backends
SHARED    = -shared -fPIC
APP_LIBS  = -lportaudio -lglfw -lGL -ldl -lpthread -ljsoncpp -lzmq
ZMQ_LIBS  = -lzmq
IMGUI_DIR  = ./imgui
IMGUI_SRCS = $(wildcard $(IMGUI_DIR)/*.cpp)
IMGUI_OBJS = $(IMGUI_SRCS:.cpp=.o)

RX_DRIVER_TARGET = rx_driver
TX_SO = tx_driver.so

.PHONY: all clean run run-rx run-tx run-hi run-stack

all: $(RX_DRIVER_TARGET) $(TX_SO)

run: run-rx

run-rx: $(RX_DRIVER_TARGET)
	./$(RX_DRIVER_TARGET)

run-hi: $(TX_SO)
	$(PYTHON) test_files/test_hi.py

run-stack: all
	@echo "Starting ZeroMQ receiver in a new terminal..."
	@xterm -title "Sine Generator" -e "$(CURDIR)/$(RX_DRIVER_TARGET)" & \
	sleep 0.5; \
	$(PYTHON) test_files/test_hi.py

# --- RX Sine generator ---
$(RX_DRIVER_TARGET): rx_driver.o $(IMGUI_OBJS)
	$(CXX) $(CXXFLAGS) rx_driver.o $(IMGUI_OBJS) $(APP_LIBS) -o $(RX_DRIVER_TARGET)
	chmod +x $(RX_DRIVER_TARGET)


rx_driver.o: rx_driver.cpp
	$(CXX) $(CXXFLAGS) -c rx_driver.cpp -o rx_driver.o

# --- Python sender shared library ---
$(TX_SO): tx_driver.cpp
	$(CXX) $(CXXFLAGS) $(SHARED) tx_driver.cpp $(ZMQ_LIBS) -o $(TX_SO)

# --- ImGui objects ---
$(IMGUI_DIR)/%.o: $(IMGUI_DIR)/%.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f *.o test_files/*.o $(IMGUI_DIR)/*.o $(RX_DRIVER_TARGET) $(TX_SO)