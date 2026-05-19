#include "../include/core.hpp"
#include "../../soundcard/include/audio_driver.hpp"
#include "../../led_driver/include/embedded_sal.hpp"
#include "../../soundcard/include/audio_driver.hpp"


int main() {
    Pa_Initialize();
    PaStream *stream;
    
    int deviceIdx = selectAudioDevice();
    const PaDeviceInfo* deviceInfo = Pa_GetDeviceInfo(deviceIdx);
    
    PaStreamParameters outputParams;
    outputParams.device                    = deviceIdx;
    outputParams.channelCount              = NUM_CHANNELS;
    outputParams.sampleFormat              = paFloat32;
    outputParams.suggestedLatency          = deviceInfo->defaultLowOutputLatency;
    outputParams.hostApiSpecificStreamInfo = nullptr;
    Pa_OpenStream(&stream, nullptr, &outputParams, SAMPLE_RATE, FRAMES_PER_BUFFER, paNoFlag, audioCallback, nullptr);

    Pa_StartStream(stream);

    std::cout << "Select Mode:\n[1] GUI\n[2] TUI\nChoice: ";
    int choice; std::cin >> choice;

    if (choice == 1) runGUI();
    else runTUI();

    Pa_StopStream(stream);
    Pa_CloseStream(stream);
    Pa_Terminate();

    return 0;
}