# Resonance SDK

The Software Development Kit for interacting with the SWAID Plate Resonance system.

## Repository Structure

- `include/`: API headers (`resonance_sdk.hpp`)
- `src/`: Implementation files (`resonance_sdk.cpp`, `tx_driver.cpp`)
- `test/`: Python-based testing scripts (`sdk_tester.py`)
- `third_party/`: Local dependencies managed by setup script
- `build/`: Compiled libraries and build artifacts

## Build Environment

### 1. Fetch Dependencies
Initialize the local environment by running the setup script:
```bash
./setup_dependencies.sh
```

### 2. Compilation
Compile the project using CMake:
```bash
cd build
cmake ..
make
```

The compiled library will be placed in the `build/` directory.
