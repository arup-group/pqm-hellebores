// fft_example.c
// Example FFT transformation using kissfft
// Compile with: gcc fft_example.c -o fft_example -lkissfft

#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "kissfft/kiss_fftr.h"

#define N_SAMPLES 7812
#define SAMPLES_PER_SECOND 7812.5

int main() {
    // Allocate input and output arrays
    float in[N_SAMPLES];
    kiss_fft_cpx out[N_SAMPLES];

    // Example: fill input with a sine wave + noise
    for (int i = 0; i < N_SAMPLES; ++i) {
        float t = (float)i / N_SAMPLES;
        float freq = 50.0f; // 50 Hz example
        in[i] = sinf(2 * M_PI * freq * t);
    }

    // Create FFT configuration
    // After the number of samples, the additional parameters are inverse fft switch, and
    // user-allocated memory which we are not using here.
    kiss_fftr_cfg cfg = kiss_fftr_alloc(N_SAMPLES, 0, NULL, NULL);
    if (!cfg) {
        fprintf(stderr, "Failed to allocate kissfft config\n");
        return 1;
    }

    // Perform FFT
    kiss_fftr(cfg, in, out);

    // Print first 20 frequency bins (magnitude)
    printf("Frequency bin magnitudes:\n");
    for (int i = 0; i < N_SAMPLES / 2; ++i) {
        float mag = sqrtf(out[i].r * out[i].r + out[i].i * out[i].i) / N_SAMPLES * 2 / sqrtf(2);
        printf("Frequency %.2f: %.4f\n", (float) i * SAMPLES_PER_SECOND / N_SAMPLES, mag);
    }

    free(cfg);
    return 0;
}
