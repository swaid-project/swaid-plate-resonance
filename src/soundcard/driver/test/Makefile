CXX       = g++
PYTHON    = python3
ROOT_DIR  = ..
IMGUI_DIR = $(ROOT_DIR)/imgui

CXXFLAGS  = -std=c++17 -I$(ROOT_DIR) -I$(IMGUI_DIR)
APP_LIBS  = -lportaudio -lglfw -lGL -ldl -lpthread -ljsoncpp -lzmq
ZMQ_LIBS  = -lzmq

RCV_APP   = rcv_app
TRANS_SO  = trans.so
RUN_PY    = $(CURDIR)/run_python.sh

IMGUI_SRCS = $(wildcard $(IMGUI_DIR)/*.cpp)
IMGUI_OBJS = $(IMGUI_SRCS:.cpp=.o)

.PHONY: all clean run-rcv run-py run-stack run-all

all: $(RCV_APP) $(TRANS_SO)

$(RCV_APP): rcv.o $(IMGUI_OBJS)
	$(CXX) $(CXXFLAGS) rcv.o $(IMGUI_OBJS) $(APP_LIBS) -o $(RCV_APP)

rcv.o: rcv.cpp
	$(CXX) $(CXXFLAGS) -c rcv.cpp -o rcv.o

$(TRANS_SO): trans.cpp
	$(CXX) $(CXXFLAGS) -shared -fPIC trans.cpp $(ZMQ_LIBS) -o $(TRANS_SO)

$(IMGUI_DIR)/%.o: $(IMGUI_DIR)/%.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

run-rcv: $(RCV_APP)
	cd $(ROOT_DIR) && ./test/$(RCV_APP)

run-py: $(TRANS_SO)
	"$(RUN_PY)"

run-stack: all
	@echo "Starting receiver in background, then launching Python sender..."
	@cd $(ROOT_DIR) && ./test/$(RCV_APP) --auto-device --mode gui & \
	RCV_PID=$$!; \
	trap 'kill $$RCV_PID 2>/dev/null || true' EXIT INT TERM; \
	"$(RUN_PY)"

run-all: run-stack

clean:
	rm -f rcv.o $(RCV_APP) $(TRANS_SO) $(IMGUI_DIR)/*.o
