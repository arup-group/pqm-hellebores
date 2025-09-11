// analyser.c: C translation of analyser.py using KissFFT for FFT
// Install KissFFT libraries with libkissfft-dev package
// Compile with: gcc -o analyser analyser.c -lkissfft-double -lm
// Compile with: gcc -o analyser analyser.c -lkissfft-float -lm
// Usage: ./analyser < input.txt

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "kissfft/kiss_fft.h"
#include "kissfft/kiss_fftr.h"

#define MAX_SIZE 16384
#define CHANNELS 5

// Sample cache (circular buffer)
typedef struct {
    double input_array[MAX_SIZE][CHANNELS];
    int size;
    int front_ptr;
} SampleCache;

void cache_init(SampleCache *cache, int size) {
    cache->size = size;
    cache->front_ptr = 0;
    for (int i = 0; i < size; ++i)
        for (int j = 0; j < CHANNELS; ++j)
            cache->input_array[i][j] = 0.0;
}

void cache_put(SampleCache *cache, const char *line) {
    cache->front_ptr = (cache->front_ptr + 1) % cache->size;
    double vals[CHANNELS] = {0};
    sscanf(line, "%lf %lf %lf %lf %lf", &vals[0], &vals[1], &vals[2], &vals[3], &vals[4]);
    for (int j = 0; j < CHANNELS; ++j)
        cache->input_array[cache->front_ptr][j] = vals[j];
}

void cache_get_output_array(SampleCache *cache, double out[MAX_SIZE][CHANNELS]) {
    int rear_ptr = (cache->front_ptr + 1) % cache->size;
    int idx = 0;
    for (int i = rear_ptr; i < cache->size; ++i, ++idx)
        for (int j = 0; j < CHANNELS; ++j)
            out[idx][j] = cache->input_array[i][j];
    for (int i = 0; i < rear_ptr; ++i, ++idx)
        for (int j = 0; j < CHANNELS; ++j)
            out[idx][j] = cache->input_array[i][j];
}

double rms(const double *arr, int n) {
    double sum = 0.0;
    for (int i = 0; i < n; ++i) sum += arr[i] * arr[i];
    return n > 0 ? sqrt(sum / n) : 0.0;
}

double max_abs(const double *arr, int n) {
    double maxv = 0.0;
    for (int i = 0; i < n; ++i) {
        double v = fabs(arr[i]);
        if (v > maxv) maxv = v;
    }
    return maxv;
}

void harmonic_magnitudes(const double *samples, int n, double sample_rate, double *out, int harmonics) {
    kiss_fftr_cfg cfg = kiss_fftr_alloc(n, 0, NULL, NULL);
    kiss_fft_scalar *in = malloc(sizeof(kiss_fft_scalar) * n);
    kiss_fft_cpx *freqs = malloc(sizeof(kiss_fft_cpx) * (n/2+1));
    for (int i = 0; i < n; ++i) in[i] = samples[i];
    kiss_fftr(cfg, in, freqs);
    for (int h = 0; h < harmonics; ++h) {
        int bin = (int)round((sample_rate * h) / n);
        if (bin < n/2+1)
            out[h] = sqrt(freqs[bin].r * freqs[bin].r + freqs[bin].i * freqs[bin].i);
        else
            out[h] = 0.0;
    }
    free(in); free(freqs); free(cfg);
}

int read_lines(int n, SampleCache *cache) {
    char line[256] = "";
    for (int i = 0; i < n; ++i) {
        if (!fgets(line, sizeof(line), stdin)) return 0;
        line[strcspn(line, "\n")] = 0;
        cache_put(cache, line);
    }
    return 1;
}

int main() {
    int sample_rate = 7812;
    int output_interval = sample_rate;
    int cache_size = sample_rate * 2;
    SampleCache cache;
    cache_init(&cache, cache_size);
    double data[MAX_SIZE][CHANNELS];
    // Seed cache
    read_lines(cache_size, &cache);
    while (read_lines(output_interval, &cache)) {
        cache_get_output_array(&cache, data);
        // Analysis
        double *voltages = &data[0][1];
        double *currents = &data[0][2];
        double *powers = &data[0][3];
        double *leakage = &data[0][4];
        double rms_v = rms(voltages, cache_size);
        double rms_i = rms(currents, cache_size);
        double rms_leakage = rms(leakage, cache_size);
        double max_v = max_abs(voltages, cache_size);
        double max_i = max_abs(currents, cache_size);
        double max_leakage = max_abs(leakage, cache_size);
        double mean_p = 0.0;
        for (int i = 0; i < cache_size; ++i) mean_p += powers[i];
        mean_p /= cache_size;
        // Harmonics
        double harmonics_v[51] = {0}, harmonics_i[51] = {0};
        harmonic_magnitudes(voltages, cache_size, sample_rate, harmonics_v, 51);
        harmonic_magnitudes(currents, cache_size, sample_rate, harmonics_i, 51);
        // Output (minimal JSON)
        printf("{\"rms_voltage\":%.3f,\"rms_current\":%.5f,\"rms_leakage\":%.5f,\"max_abs_voltage\":%.3f,\"max_abs_current\":%.5f,\"max_abs_leakage\":%.5f,\"mean_power\":%.3f,\"voltage_h1\":%.3f,\"current_h1\":%.5f}\n",
            rms_v, rms_i, rms_leakage, max_v, max_i, max_leakage, mean_p, harmonics_v[1], harmonics_i[1]);
        fflush(stdout);
    }
    return 0;
}
