#!/bin/bash
# SWAID Soundcard Dependency Setup

mkdir -p build
mkdir -p third_party

# Note: This module requires the following system dependencies:
echo "[*] Installing the Soundcard dependencies."
sudo apt install portaudio19-dev libglfw3-dev libzmq3-dev cppzmq-dev libjsoncpp-dev

echo "Soundcard: Directories initialized."
