cmake_minimum_required(VERSION 3.10)
project(ResonanceCore CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Project Structure ────────────────────────────────────────────────────────

include_directories(include)

set(THIRD_PARTY_DIR ${CMAKE_CURRENT_SOURCE_DIR}/third_party)
include_directories(${THIRD_PARTY_DIR})

file(GLOB_RECURSE CORE_SOURCES "src/*.cpp")

set(ALL_SOURCES
    main.cpp
    ${CORE_SOURCES}
)

add_executable(resonance_core ${ALL_SOURCES})

# ── Compiler Settings ────────────────────────────────────────────────────────

if(MSVC)
    target_compile_options(resonance_core PRIVATE /W4)
else()
    target_compile_options(resonance_core PRIVATE -Wall -Wextra -Wpedantic -O3)
endif()
