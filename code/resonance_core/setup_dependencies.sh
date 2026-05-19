#!/bin/bash
# SWAID Resonance Core Dependency Setup

mkdir -p build
mkdir -p third_party

if [ $1 == "DEBUG" ]; then
    echo "[*] Installing GUI dependencies"
    cd third_party
    git clone https://github.com/ocornut/imgui
    cd ..
fi

echo "Resonance Core: Directories initialized."
