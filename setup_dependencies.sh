#!/bin/bash

# SWAID - Centralized Dependency Setup Script
# This script populates the global third_party directory with required libraries.

set -e

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
THIRD_PARTY_DIR="$SCRIPT_DIR/code/third_party"

echo "Centralizing dependencies in: $THIRD_PARTY_DIR"
mkdir -p "$THIRD_PARTY_DIR"

# 0. System Dependencies
echo "[*] Installing system dependencies..."
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sudo apt update
    sudo apt install -y portaudio19-dev libglfw3-dev libzmq3-dev cppzmq-dev libjsoncpp-dev curl git build-essential cmake
elif [[ "$OSTYPE" == "darwin"* ]]; then
    brew install portaudio glfw zeromq nlohmann-json eigen
fi

# 1. GLFW
echo "[*] Fetching GLFW..."
if [ ! -d "$THIRD_PARTY_DIR/glfw" ]; then
    git clone --depth 1 https://github.com/glfw/glfw.git "$THIRD_PARTY_DIR/glfw"
else
    echo "GLFW already exists, skipping clone."
fi

# 2. Dear ImGui (Docking Branch)
echo "[*] Fetching Dear ImGui (docking branch)..."
if [ ! -d "$THIRD_PARTY_DIR/imgui" ]; then
    git clone --depth 1 -b docking https://github.com/ocornut/imgui.git "$THIRD_PARTY_DIR/imgui_repo"
    mkdir -p "$THIRD_PARTY_DIR/imgui"
    cp "$THIRD_PARTY_DIR/imgui_repo"/*.cpp "$THIRD_PARTY_DIR/imgui/"
    cp "$THIRD_PARTY_DIR/imgui_repo"/*.h "$THIRD_PARTY_DIR/imgui/"
    mkdir -p "$THIRD_PARTY_DIR/imgui/backends"
    cp "$THIRD_PARTY_DIR/imgui_repo/backends/imgui_impl_glfw.cpp" "$THIRD_PARTY_DIR/imgui/backends/"
    cp "$THIRD_PARTY_DIR/imgui_repo/backends/imgui_impl_glfw.h" "$THIRD_PARTY_DIR/imgui/backends/"
    cp "$THIRD_PARTY_DIR/imgui_repo/backends/imgui_impl_opengl3.cpp" "$THIRD_PARTY_DIR/imgui/backends/"
    cp "$THIRD_PARTY_DIR/imgui_repo/backends/imgui_impl_opengl3.h" "$THIRD_PARTY_DIR/imgui/backends/"
    cp "$THIRD_PARTY_DIR/imgui_repo/backends/imgui_impl_opengl3_loader.h" "$THIRD_PARTY_DIR/imgui/backends/"
    rm -rf "$THIRD_PARTY_DIR/imgui_repo"
else
    echo "ImGui already exists, skipping."
fi

# 3. ImPlot
echo "[*] Fetching ImPlot..."
if [ ! -d "$THIRD_PARTY_DIR/implot" ]; then
    git clone --depth 1 https://github.com/epezent/implot.git "$THIRD_PARTY_DIR/implot_repo"
    mkdir -p "$THIRD_PARTY_DIR/implot"
    cp "$THIRD_PARTY_DIR/implot_repo"/*.cpp "$THIRD_PARTY_DIR/implot/"
    cp "$THIRD_PARTY_DIR/implot_repo"/*.h "$THIRD_PARTY_DIR/implot/"
    rm -rf "$THIRD_PARTY_DIR/implot_repo"
else
    echo "ImPlot already exists, skipping."
fi

# 4. STB Headers
echo "[*] Fetching STB headers..."
mkdir -p "$THIRD_PARTY_DIR/stb"
if [ ! -f "$THIRD_PARTY_DIR/stb/stb_image.h" ]; then
    curl -L https://raw.githubusercontent.com/nothings/stb/master/stb_image.h -o "$THIRD_PARTY_DIR/stb/stb_image.h"
fi
if [ ! -f "$THIRD_PARTY_DIR/stb/stb_image_write.h" ]; then
    curl -L https://raw.githubusercontent.com/nothings/stb/master/stb_image_write.h -o "$THIRD_PARTY_DIR/stb/stb_image_write.h"
fi

# 5. Nlohmann JSON
echo "[*] Fetching Nlohmann JSON..."
mkdir -p "$THIRD_PARTY_DIR/nlohmann"
if [ ! -f "$THIRD_PARTY_DIR/nlohmann/json.hpp" ]; then
    curl -L https://github.com/nlohmann/json/releases/download/v3.11.3/json.hpp -o "$THIRD_PARTY_DIR/nlohmann/json.hpp"
else
    echo "Nlohmann JSON already exists, skipping download."
fi

# 6. Eigen3
echo "[*] Fetching Eigen3..."
if [ ! -d "$THIRD_PARTY_DIR/eigen" ]; then
    git clone --depth 1 -b 3.4.0 https://gitlab.com/libeigen/eigen.git "$THIRD_PARTY_DIR/eigen"
else
    echo "Eigen already exists, skipping clone."
fi

echo "--------------------------------------------------"
echo "Global dependency setup complete!"
echo "--------------------------------------------------"
