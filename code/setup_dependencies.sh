#!/bin/bash
# SWAID Plate Resonance - Unified Dependency Setup
set -e

MODULES=("resonance_sdk" "resonance_core" "resonance_tuner" "simulator" "soundcard" "led_driver")

echo "--- Cleaning Existing Build Folders ---"
for mod in "${MODULES[@]}"; do
    if [ -d "$mod/build" ]; then
        echo "Removing $mod/build..."
        rm -rf "$mod/build"
    fi
done

echo "--- Installing System Dependencies ---"
# GLFW dependencies + PortAudio + ZMQ
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    libxinerama-dev \
    libxcursor-dev \
    libxrandr-dev \
    libxi-dev \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    portaudio19-dev \
    libzmq3-dev \
    libasound2-dev \
    pkg-config

echo "--- Initializing Third Party Libraries ---"
mkdir -p third_party

# Populate simulator/third_party (used by tuner and simulator)
cd simulator
./setup_dependencies.sh
cd ..

# Ensure resonance_sdk has local headers (fallback for systems with missing dev packages)
mkdir -p resonance_sdk/include
curl -L https://raw.githubusercontent.com/zeromq/libzmq/master/include/zmq.h -o resonance_sdk/include/zmq.h
curl -L https://raw.githubusercontent.com/zeromq/cppzmq/master/zmq.hpp -o resonance_sdk/include/zmq.hpp

# Ensure resonance_core has portaudio fallback
mkdir -p resonance_core/include
curl -L https://raw.githubusercontent.com/PortAudio/portaudio/master/include/portaudio.h -o resonance_core/include/portaudio.h

echo "--- Creating Build Directories ---"
for mod in "${MODULES[@]}"; do
    if [ -d "$mod" ]; then
        echo "Initializing build folder for $mod..."
        mkdir -p "$mod/build"
    fi
done

echo "--------------------------------------------------"
echo "Setup Complete! You can now run 'make all' to build."
echo "--------------------------------------------------"
