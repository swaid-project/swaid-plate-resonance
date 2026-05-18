cmake_minimum_required(VERSION 3.10)
project(ResonanceSDK CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Project Structure ────────────────────────────────────────────────────────

include_directories(include)

set(THIRD_PARTY_DIR ${CMAKE_CURRENT_SOURCE_DIR}/third_party)
include_directories(${THIRD_PARTY_DIR})

file(GLOB_RECURSE SDK_SOURCES "src/*.cpp")

add_library(resonance_sdk STATIC ${SDK_SOURCES})

# ── Compiler Settings ────────────────────────────────────────────────────────

if(MSVC)
    target_compile_options(resonance_sdk PRIVATE /W4)
else()
    target_compile_options(resonance_sdk PRIVATE -Wall -Wextra -Wpedantic -O3)
endif()
