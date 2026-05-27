cmake_minimum_required(VERSION 3.10)
project(Soundcard CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Dependencies ─────────────────────────────────────────────────────────────
find_package(OpenGL REQUIRED)
find_package(Threads REQUIRED)
add_definitions(-DGL_GLEXT_PROTOTYPES)

# ── Paths ───────────────────────────────────────────────────────────────────
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
include_directories(${THIRD_PARTY_DIR})
include_directories(${THIRD_PARTY_DIR}/glfw/include)
include_directories(${THIRD_PARTY_DIR}/imgui)
include_directories(${THIRD_PARTY_DIR}/imgui/backends)

# ── Sources ─────────────────────────────────────────────────────────────────
set(IMGUI_SOURCES
    ${THIRD_PARTY_DIR}/imgui/imgui.cpp
    ${THIRD_PARTY_DIR}/imgui/imgui_draw.cpp
    ${THIRD_PARTY_DIR}/imgui/imgui_tables.cpp
    ${THIRD_PARTY_DIR}/imgui/imgui_widgets.cpp
    ${THIRD_PARTY_DIR}/imgui/backends/imgui_impl_glfw.cpp
    ${THIRD_PARTY_DIR}/imgui/backends/imgui_impl_opengl3.cpp
)

set(RX_SOURCES
    rx_driver.cpp
    ${IMGUI_SOURCES}
)

add_executable(rx_driver ${RX_SOURCES})

# ── Linking ──────────────────────────────────────────────────────────────────
target_link_libraries(rx_driver
    glfw
    ${OPENGL_LIBRARIES}
    Threads::Threads
    portaudio
    zmq
    jsoncpp
    dl
)

# ── Compiler Settings ────────────────────────────────────────────────────────

if(MSVC)
    target_compile_options(rx_driver PRIVATE /W4)
else()
    target_compile_options(rx_driver PRIVATE -Wall -Wextra -Wpedantic -O3)
endif()
