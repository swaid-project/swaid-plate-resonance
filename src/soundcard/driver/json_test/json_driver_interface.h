#pragma once
#include <cstdint>
#include <semaphore.h>

#define SHM_NAME    "/chladni_shm"
#define NUM_TRANSDUCERS 4

struct TransducerState {
    float freq;
    float amp;
    float phaseDeg;
};

struct SharedBlock {
    sem_t       mutex;                          // protects the block
    uint32_t    generation;                     // incremented on every write — reader detects change
    TransducerState transducers[NUM_TRANSDUCERS];
};

// AI made 
