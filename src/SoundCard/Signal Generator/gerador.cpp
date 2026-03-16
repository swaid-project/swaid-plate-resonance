#include <iostream>
#include <cmath>
#include <portaudio.h>

// Configurações de tempo real
#define SAMPLE_RATE 44100
#define FRAMES_PER_BUFFER 64 // UM VALOR BAIXO AQUI É O SEGREDO DA BAIXA LATÊNCIA! 
                             // (64 ou 128 são excelentes. Se o som "engasgar", sobe para 256)

// Estrutura para guardar os dados da nossa onda sonora
struct AudioData {
    float phase;
};

// ESTA É A FUNÇÃO MAIS IMPORTANTE (O CALLBACK)
// O sistema de som vai chamar esta função dezenas de vezes por segundo para pedir mais áudio.
// Como o FRAMES_PER_BUFFER é pequeno, o áudio sai quase instantaneamente.
static int audioCallback(const void *inputBuffer, void *outputBuffer,
                         unsigned long framesPerBuffer,
                         const PaStreamCallbackTimeInfo* timeInfo,
                         PaStreamCallbackFlags statusFlags,
                         void *userData) {
    
    AudioData *data = (AudioData*)userData;
    float *out = (float*)outputBuffer;

    // Gerar o som (preencher o buffer)
    for(unsigned int i = 0; i < framesPerBuffer; i++) {
        // Gera o som matemático (onda sinusoidal)
        float sample = 0.5f * sin(data->phase); 
        
        *out++ = sample;  // Envia para o Canal Esquerdo
        *out++ = sample;  // Envia para o Canal Direito

        // Aumentar a fase para criar o tom (aprox. 440Hz, nota Lá)
        data->phase += 0.05f; 
        if (data->phase > 3.14159265f * 2.0f) data->phase -= 3.14159265f * 2.0f;
    }
    
    return paContinue; // Diz ao PortAudio para continuar a pedir som
}

int main() {
    PaError err;
    AudioData data = {0.0f};

    // 1. Iniciar o motor de áudio
    err = Pa_Initialize();
    if(err != paNoError) goto error;

    std::cout << "A iniciar áudio em tempo real. Pressiona ENTER para parar..." << std::endl;

    PaStream *stream;
    
    // 2. Abrir o canal de áudio com as nossas configurações
    err = Pa_OpenDefaultStream(&stream,
                               0,          // Canais de entrada (nenhum, só queremos emitir som)
                               2,          // Canais de saída (2 = Stereo)
                               paFloat32,  // Formato do som (Qualidade alta)
                               SAMPLE_RATE,
                               FRAMES_PER_BUFFER,
                               audioCallback,
                               &data);
    if(err != paNoError) goto error;

    // 3. Começar a tocar (Baixa latência a funcionar a partir daqui!)
    err = Pa_StartStream(stream);
    if(err != paNoError) goto error;

    // Fica a tocar até o utilizador carregar no ENTER
    std::cin.get();

    // 4. Parar e limpar tudo
    err = Pa_StopStream(stream);
    if(err != paNoError) goto error;

    err = Pa_CloseStream(stream);
    if(err != paNoError) goto error;

    Pa_Terminate();
    return 0;

error:
    std::cerr << "Erro no PortAudio: " << Pa_GetErrorText(err) << std::endl;
    Pa_Terminate();
    return -1;
}