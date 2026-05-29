cmake_minimum_required(VERSION 3.10)
project(ChladniSim CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Dependencies ─────────────────────────────────────────────────────────────

# OpenGL
find_package(OpenGL REQUIRED)

# Threads
find_package(Threads REQUIRED)

# Global Defines for OpenGL Loading (Linux/X11)
add_definitions(-DGL_GLEXT_PROTOTYPES)

# ── Third Party ──────────────────────────────────────────────────────────────

set(THIRD_PARTY_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../third_party)

# Eigen3 (Header only)
include_directories(${THIRD_PARTY_DIR}/eigen)

# GLFW
set(GLFW_BUILD_DOCS OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_WAYLAND OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_X11 ON CACHE BOOL "" FORCE)

add_subdirectory(${THIRD_PARTY_DIR}/glfw glfw_build)
include_directories(${THIRD_PARTY_DIR}/glfw/include)

# ImGui & ImPlot
include_directories(${THIRD_PARTY_DIR}/imgui)
include_directories(${THIRD_PARTY_DIR}/imgui/backends)
include_directories(${THIRD_PARTY_DIR}/implot)
include_directories(${THIRD_PARTY_DIR}/stb)
include_directories(${THIRD_PARTY_DIR}) # for nlohmann/json.hpp

set(IMGUI_SOURCES
    ${THIRD_PARTY_DIR}/imgui/imgui.cpp
    ${THIRD_PARTY_DIR}/imgui/imgui_draw.cpp
    ${THIRD_PARTY_DIR}/imgui/imgui_tables.cpp
    ${THIRD_PARTY_DIR}/imgui/imgui_widgets.cpp
    ${THIRD_PARTY_DIR}/imgui/backends/imgui_impl_glfw.cpp
    ${THIRD_PARTY_DIR}/imgui/backends/imgui_impl_opengl3.cpp
)

set(IMPLOT_SOURCES
    ${THIRD_PARTY_DIR}/implot/implot.cpp
    ${THIRD_PARTY_DIR}/implot/implot_items.cpp
)

# ── Project Structure ────────────────────────────────────────────────────────

include_directories(src)

set(CORE_SOURCES
    src/core/physics.cpp
    src/core/analyzer.cpp
)

add_library(simulator_core STATIC ${CORE_SOURCES})

set(GUI_SOURCES
    src/gui/application.cpp
    src/gui/panels.cpp
)

set(ALL_SOURCES
    src/main.cpp
    ${GUI_SOURCES}
    ${IMGUI_SOURCES}
    ${IMPLOT_SOURCES}
)

add_executable(chladni_sim ${ALL_SOURCES})

target_link_libraries(chladni_sim
    simulator_core
    glfw
    ${OPENGL_LIBRARIES}
    Threads::Threads
    dl
)

# ── Compiler Settings ────────────────────────────────────────────────────────

if(MSVC)
    target_compile_options(chladni_sim PRIVATE /W4)
else()
    target_compile_options(chladni_sim PRIVATE -Wall -Wextra -Wpedantic -O3)
endif()
