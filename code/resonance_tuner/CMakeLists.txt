cmake_minimum_required(VERSION 3.10)
project(ResonanceTuner CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Dependencies ─────────────────────────────────────────────────────────────
find_package(OpenGL REQUIRED)
find_package(Threads REQUIRED)
add_definitions(-DGL_GLEXT_PROTOTYPES)

# Project dependencies
set(SIM_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../simulator)
set(SDK_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../resonance_sdk)

add_subdirectory(${SIM_DIR} simulator_build)
add_subdirectory(${SDK_DIR} resonance_sdk_build)

# ── Paths ───────────────────────────────────────────────────────────────────
set(THIRD_PARTY_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../third_party)

# ── Includes ────────────────────────────────────────────────────────────────
include_directories(include)
include_directories(${SIM_DIR}/src)
include_directories(${SDK_DIR}/include)
include_directories(${THIRD_PARTY_DIR}/eigen)
include_directories(${THIRD_PARTY_DIR})
include_directories(${THIRD_PARTY_DIR}/glfw/include)
include_directories(${THIRD_PARTY_DIR}/imgui)
include_directories(${THIRD_PARTY_DIR}/imgui/backends)
include_directories(${THIRD_PARTY_DIR}/implot)
include_directories(${THIRD_PARTY_DIR}/stb)

# ── Sources ─────────────────────────────────────────────────────────────────
set(IMGUI_SOURCES
    ${THIRD_PARTY_DIR}/imgui/imgui.cpp
    ${THIRD_PARTY_DIR}/imgui/imgui_draw.cpp
    ${THIRD_PARTY_DIR}/imgui/imgui_tables.cpp
    ${THIRD_PARTY_DIR}/imgui/imgui_widgets.cpp
    ${THIRD_PARTY_DIR}/imgui/backends/imgui_impl_glfw.cpp
    ${THIRD_PARTY_DIR}/imgui/backends/imgui_impl_opengl3.cpp
    ${THIRD_PARTY_DIR}/implot/implot.cpp
    ${THIRD_PARTY_DIR}/implot/implot_items.cpp
)

set(TUNER_SOURCES
    src/main.cpp
    src/gui/tuner_app.cpp
    src/gui/tuner_panels.cpp
    ${IMGUI_SOURCES}
)

# ── Target ──────────────────────────────────────────────────────────────────
add_executable(resonance_tuner ${TUNER_SOURCES})

target_link_libraries(resonance_tuner
    simulator_core
    resonance_sdk
    glfw
    ${OPENGL_LIBRARIES}
    Threads::Threads
    dl
)

# ── Compiler Settings ────────────────────────────────────────────────────────
if(MSVC)
    target_compile_options(resonance_tuner PRIVATE /W4)
else()
    target_compile_options(resonance_tuner PRIVATE -Wall -Wextra -Wpedantic -O3)
endif()
