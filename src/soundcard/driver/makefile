# Variables
CXX       = g++
PYTHON    = python3
CXXFLAGS  = -std=c++17 -I. -I./imgui
SHARED    = -shared -fPIC

APP_LIBS  = -lportaudio -lglfw -lGL -ldl -lpthread -ljsoncpp -lzmq
ZMQ_LIBS  = -lzmq

IMGUI_DIR   = ./imgui
IMGUI_SRCS  = $(wildcard $(IMGUI_DIR)/*.cpp)
IMGUI_OBJS  = $(IMGUI_SRCS:.cpp=.o)

MAIN_TARGET = sine_gen
RCV_TARGET  = test/rcv_app
TRANS_SO    = test/trans.so

all: $(MAIN_TARGET) $(RCV_TARGET) $(TRANS_SO)

run: run-main

run-main: $(MAIN_TARGET)
	./$(MAIN_TARGET)

run-rcv: $(RCV_TARGET)
	./$(RCV_TARGET)

run-hi: $(TRANS_SO)
	$(PYTHON) test/test_hi.py

run-stack: all
	@echo "Starting ZeroMQ receiver in background (GUI mode, auto-device)."
	@./$(RCV_TARGET) --auto-device --mode gui & \
	RCV_PID=$$!; \
	trap 'kill $$RCV_PID 2>/dev/null || true' EXIT INT TERM; \
	$(PYTHON) test/test_hi.py

$(MAIN_TARGET): main.o $(IMGUI_OBJS)
	$(CXX) $(CXXFLAGS) main.o $(IMGUI_OBJS) $(APP_LIBS) -o $(MAIN_TARGET)

$(RCV_TARGET): test/rcv.o $(IMGUI_OBJS)
	$(CXX) $(CXXFLAGS) test/rcv.o $(IMGUI_OBJS) $(APP_LIBS) -o $(RCV_TARGET)

$(TRANS_SO): test/trans.cpp
	$(CXX) $(CXXFLAGS) $(SHARED) test/trans.cpp $(ZMQ_LIBS) -o $(TRANS_SO)

main.o: main.cpp
	$(CXX) $(CXXFLAGS) -c main.cpp -o main.o

test/rcv.o: test/rcv.cpp
	$(CXX) $(CXXFLAGS) -c test/rcv.cpp -o test/rcv.o

$(IMGUI_DIR)/%.o: $(IMGUI_DIR)/%.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f *.o test/*.o $(IMGUI_DIR)/*.o $(MAIN_TARGET) $(RCV_TARGET) $(TRANS_SO)