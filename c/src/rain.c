// rain.c: C translation of rain.py
// Requires cJSON library for JSON parsing
// Install cJSON with libcjson-dev package
// gcc -o rain rain.c -lcjson -lm

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <math.h>
#include <time.h>
#include <string.h>
#include <unistd.h>
#include "cjson/cJSON.h"

#define SETTINGS_PATH1 "../configuration/settings.json"
#define SETTINGS_PATH2 "../../configuration/settings.json"

// Constants from constants.py
const float HARDWARE_SCALE_FACTORS[4] = { 4.07e-07, 2.44e-05, 0.00122, 0.0489 };
const float AMPLITUDES[4] = { 0.000100, 0.4, 0.4, 230.0 };
const float NOISE[4] = { 0.05, 0.05, 0.05, 0.0 };
const double FREQUENCY = 50.2;
const double TPF = 2 * M_PI * FREQUENCY;

// This will hold signal amplitudes, taking scaling factors into account
float SIGNAL[4];

// Settings struct
struct Settings {
    double interval; // ms per sample
};

// Read settings.json and extract interval
int read_settings(struct Settings *st) {
    FILE *f = fopen(SETTINGS_PATH1, "r");
    // Second attempt, working from deeper directory (eg build directory)
    if (!f) {
        f = fopen(SETTINGS_PATH2, "r");
        if (!f) return -1;
    } 
    fseek(f, 0, SEEK_END);
    long len = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *data = malloc(len + 1);
    // Check if the whole file was read
    if (fread(data, 1, len, f) != len) return -2;
    data[len] = '\0';
    fclose(f);
    cJSON *json = cJSON_Parse(data);
    free(data);
    // Check for JSON parsing errors
    if (!json) return -2;
    cJSON *sample_rate = cJSON_GetObjectItem(json, "sample_rate");
    // Check for sample_rate key
    if (!sample_rate || !cJSON_IsNumber(sample_rate)) {
        cJSON_Delete(json);
        return -3;
    }
    st->interval = 1000.0 / sample_rate->valuedouble;
    cJSON_Delete(json);
    return 0;
}

// Generate one sample per channel, as two's complement 16 bit integer
void get_sample(double t, uint16_t *out) {
    // cast to float only after we have processed time
    float wt = (float) TPF * t / 1000.0;
    // the signal values are cast to unsigned 16 bit which applies two's complement
    // conversion to the calculated integer.
    out[0] = (uint16_t) SIGNAL[0] * (sin(wt) + NOISE[0] * ((float) rand()/RAND_MAX - 0.5));
    out[1] = (uint16_t) SIGNAL[1] * (sin(wt) + NOISE[1] * ((float) rand()/RAND_MAX - 0.5));
    out[2] = (uint16_t) SIGNAL[2] * (sin(wt) + NOISE[2] * ((float) rand()/RAND_MAX - 0.5));
    out[3] = (uint16_t) SIGNAL[3] * (sin(wt) + NOISE[2] * ((float) rand()/RAND_MAX - 0.5));
}

int main() {
    srand(time(NULL));
    // calculate amplitudes taking account of hardware scaling factors
    for (int i = 0; i < 4; ++i) {
        SIGNAL[i] = sqrt(2) * AMPLITUDES[i] / HARDWARE_SCALE_FACTORS[i];
    }
    struct Settings st;
    if (read_settings(&st) != 0) {
        fprintf(stderr, "rain: Failed to read settings.json\n");
        return 1;
    }
    struct timespec t_start, t_now;
    clock_gettime(CLOCK_MONOTONIC, &t_start);
    int c = 0;
    while (1) {
        clock_gettime(CLOCK_MONOTONIC, &t_now);
        // get elapsed time in milliseconds
        double elapsed = (t_now.tv_sec - t_start.tv_sec) * 1000 + (t_now.tv_nsec - t_start.tv_nsec) / 1.0e6;
        // convert to number of samples, less those already emitted
        // 32 bit integer is sufficient for 49.7 days
        int n = (int) (elapsed / st.interval) - c;
        for (int i = 0; i < n; ++i) {
            uint16_t out[4];
            get_sample(c * st.interval, out);
            printf("%04x %04x %04x %04x\n", out[0], out[1], out[2], out[3]);
            c++;
        }
        usleep(20000); // sleep 20ms
    }
    return 0;
}
