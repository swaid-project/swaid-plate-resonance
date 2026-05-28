cmake_minimum_required(VERSION 3.10)
project(ResonanceCore CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Project Structure ────────────────────────────────────────────────────────
include_directories(include)
include_directories(../soundcard/include)
include_directories(../led_driver/include)
include_directories(../third_party)
include_directories(../third_party/imgui)
link_directories(lib)

file(GLOB CORE_SOURCES 
    "src/*.cpp" 
    "../soundcard/src/audio_driver.cpp" 
    "../led_driver/src/embedded_sal.cpp"
)

add_executable(resonance_core ${CORE_SOURCES})

# ── Dependencies & Linking ───────────────────────────────────────────────────

target_link_libraries(resonance_core PRIVATE 
    portaudio 
    zmq 
    pthread
)

# ── Compiler Settings ────────────────────────────────────────────────────────

if(MSVC)
    target_compile_options(resonance_core PRIVATE /W4)
else()
    target_compile_options(resonance_core PRIVATE -Wall -Wextra -Wpedantic -O3)
endif()
