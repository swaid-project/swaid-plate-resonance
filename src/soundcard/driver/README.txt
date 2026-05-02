This folder contains the signal generator intended to be deployed

The imgui/ folder contains src code extracted from https://github.com/ocornut/imgui 

- git clone https://github.com/ocornut/imgui

To install the dependencies one shall run install-dependencies.sh 

To compile, run, and clean all resulting files from this software, a makefile is present:

- make -> To compile all the files
- make run-rx -> To run the receiver and sound generator
- make run-hi -> To run the testbench 
- make run-stack -> To run both the receiver and testbench
- make clean -> To eliminate the executables

