cmake_minimum_required(VERSION 3.10)
project(Soundcard CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Project Structure ────────────────────────────────────────────────────────

include_directories(include)

set(THIRD_PARTY_DIR ${CMAKE_CURRENT_SOURCE_DIR}/third_party)
include_directories(${THIRD_PARTY_DIR})

# Sources
set(RX_SOURCES
    rx_driver.cpp
)

add_executable(rx_driver ${RX_SOURCES})

# ── Compiler Settings ────────────────────────────────────────────────────────

if(MSVC)
    target_compile_options(rx_driver PRIVATE /W4)
else()
    target_compile_options(rx_driver PRIVATE -Wall -Wextra -Wpedantic -O3)
endif()
