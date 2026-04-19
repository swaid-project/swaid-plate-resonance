This folder contains the signal generator intended to be deployed

The imgui/ folder contains src code extracted from https://github.com/ocornut/imgui 

- git clone https://github.com/ocornut/imgui

The commands to install the dependencies, for a Debian-based distro, are the following:

- sudo apt install portaudio19-dev
- sudo apt install libglfw3-dev

To compile, run, and clean all resulting files from this software, a makefile is present:

- make -> To compile the files
- make run -> To compile and then execute the driver process
- make run-json -> To compile and then execute the JSON-RX
- make clean -> To eliminate the resulting files from compiling and running

