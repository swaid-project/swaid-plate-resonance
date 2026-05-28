cmake_minimum_required(VERSION 3.10)
project(ResonanceTuner CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Dependencies ─────────────────────────────────────────────────────────────
find_package(OpenGL REQUIRED)
find_package(Threads REQUIRED)
add_definitions(-DGL_GLEXT_PROTOTYPES)

# ── Paths ───────────────────────────────────────────────────────────────────
set(SIM_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../simulator)
set(SDK_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../resonance_sdk)
set(THIRD_PARTY_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../third_party)

# ── GLFW ────────────────────────────────────────────────────────────────────
set(GLFW_BUILD_DOCS OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_WAYLAND OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_X11 ON CACHE BOOL "" FORCE)
add_subdirectory(${THIRD_PARTY_DIR}/glfw glfw_build)

# ── Includes ────────────────────────────────────────────────────────────────
include_directories(include)
link_directories(lib)
include_directories(${SIM_DIR}/src)
include_directories(${SDK_DIR}/include)
include_directories(${THIRD_PARTY_DIR}/eigen)
include_directories(${THIRD_PARTY_DIR})
include_directories(${THIRD_PARTY_DIR}/glfw/include)
include_directories(${THIRD_PARTY_DIR}/imgui)
include_directories(${THIRD_PARTY_DIR}/imgui/backends)
include_directories(${THIRD_PARTY_DIR}/implot)

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

set(CORE_SOURCES
    ${SIM_DIR}/src/core/physics.cpp
    ${SIM_DIR}/src/core/analyzer.cpp
)

set(TUNER_SOURCES
    src/main.cpp
    src/gui/tuner_app.cpp
    src/gui/tuner_panels.cpp
    ${CORE_SOURCES}
    ${IMGUI_SOURCES}
    ${SDK_DIR}/src/mqdriver_tx.cpp
)

# ── Target ──────────────────────────────────────────────────────────────────
add_executable(resonance_tuner ${TUNER_SOURCES})

target_link_libraries(resonance_tuner
    glfw
    ${OPENGL_LIBRARIES}
    Threads::Threads
    zmq
    dl
)

# ── Compiler Settings ────────────────────────────────────────────────────────
if(MSVC)
    target_compile_options(resonance_tuner PRIVATE /W4)
else()
    target_compile_options(resonance_tuner PRIVATE -Wall -Wextra -Wpedantic -O3)
endif()
