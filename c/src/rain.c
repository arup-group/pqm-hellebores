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
const double HARDWARE_SCALE_FACTORS[4] = { 4.07e-07, 2.44e-05, 0.00122, 0.0489 };
const double AMPLITUDES[4] = { 0.000100, 0.4, 0.4, 230.0 };
const double NOISE_AMPLITUDES[4] = { 0.05, 0.05, 0.05, 0.0 };
const double FREQUENCY = 50.2;
const double TPF = 2 * M_PI * FREQUENCY;

double SIGNAL[4];
double NOISE[4];

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
    fread(data, 1, len, f);
    data[len] = '\0';
    fclose(f);
    cJSON *json = cJSON_Parse(data);
    free(data);
    if (!json) return -2;
    cJSON *sample_rate = cJSON_GetObjectItem(json, "sample_rate");
    if (!sample_rate || !cJSON_IsNumber(sample_rate)) {
        cJSON_Delete(json);
        return -3;
    }
    st->interval = 1000.0 / sample_rate->valuedouble;
    cJSON_Delete(json);
    return 0;
}

// Generate one sample per channel
void get_sample(double t, uint16_t *out) {
    double wt = TPF * t / 1000.0;
    out[0] = (uint16_t)(SIGNAL[0] * sin(wt) + NOISE[0] * ((double)rand()/RAND_MAX - 0.5));
    out[1] = (uint16_t)(SIGNAL[1] * sin(wt) + NOISE[1] * ((double)rand()/RAND_MAX - 0.5));
    out[2] = (uint16_t)(SIGNAL[2] * sin(wt) + NOISE[2] * ((double)rand()/RAND_MAX - 0.5));
    out[3] = (uint16_t)(SIGNAL[3] * sin(wt) + NOISE[2] * ((double)rand()/RAND_MAX - 0.5));
}

int main() {
    srand(time(NULL));
    for (int i = 0; i < 4; ++i) {
        SIGNAL[i] = sqrt(2) * AMPLITUDES[i] / HARDWARE_SCALE_FACTORS[i];
        NOISE[i] = NOISE_AMPLITUDES[i] * SIGNAL[i];
    }
    struct Settings st;
    if (read_settings(&st) != 0) {
        fprintf(stderr, "Failed to read settings.json\n");
        return 1;
    }
    struct timespec ts_start, ts_now;
    clock_gettime(CLOCK_MONOTONIC, &ts_start);
    int c = 0;
    while (1) {
        clock_gettime(CLOCK_MONOTONIC, &ts_now);
        double elapsed = (ts_now.tv_sec - ts_start.tv_sec) * 1000.0 + (ts_now.tv_nsec - ts_start.tv_nsec) / 1e6;
        int n = (int)(elapsed / st.interval) - c;
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
