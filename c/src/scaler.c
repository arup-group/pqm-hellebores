// scaler.c: C translation of scaler.py with signal and callback logic
// Requires cJSON library for JSON parsing
// gcc -o scaler scaler.c -lcjson -lm

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <math.h>
#include "cjson/cJSON.h"

#define DELAY_LINE_LENGTH 64
#define SETTINGS_PATH "../configuration/settings.json"
#define CALIBRATIONS_PATH "../configuration/calibrations.json"
#define IDENTITY_PATH "../configuration/identity"

// Constants from constants.py
const float HARDWARE_SCALE_FACTORS[4] = { 4.07e-07, 2.44e-05, 0.00122, 0.0489 };

// Settings struct
struct Settings {
    double interval;
    char current_sensor[16];
    float cal_offsets[4];
    float cal_gains[4];
    float cal_skew_times[4];
};

struct Settings settings;
int current_channel = 2;

void set_current_channel() {
    if (strcmp(settings.current_sensor, "low") == 0) {
        current_channel = 1;
    } else {
        current_channel = 2;
    }
}

void default_callback() {
    set_current_channel();
    printf("Callback: settings updated, current_channel=%d\n", current_channel);
}

void set_callback_fn(void (*fn)(void));
void (*callback_fn)(void) = default_callback;

void signal_handler(int signum) {
    printf("Signal received: %d\n", signum);
    // Reload settings (simulate)
    // In a full implementation, reload from file
    set_current_channel();
    if (callback_fn) callback_fn();
}

int from_twos_complement_hex(const char *w) {
    int v = (int)strtol(w, NULL, 16);
    return -(v & 0x8000) | (v & 0x7fff);
}

void uncalibrated_constants(float *offsets, float *gains, int *delays) {
    for (int i = 0; i < 4; ++i) {
        offsets[i] = 0.0;
        gains[i] = HARDWARE_SCALE_FACTORS[i];
        delays[i] = -1;
    }
}

void calibrated_constants(float *offsets, float *gains, int *delays) {
    for (int i = 0; i < 4; ++i) {
        offsets[i] = settings.cal_offsets[i];
        gains[i] = HARDWARE_SCALE_FACTORS[i] * settings.cal_gains[i];
        delays[i] = (int)(-1 - settings.cal_skew_times[i] / settings.interval);
        if (delays[i] < -(DELAY_LINE_LENGTH-1) || delays[i] > -1) {
            uncalibrated_constants(offsets, gains, delays);
            return;
        }
    }
}

void scale_readings(int *cs, float *offsets, float *gains, float *out) {
    for (int i = 0; i < 4; ++i) {
        out[i] = (cs[i] + offsets[i]) * gains[i];
    }
}

void set_callback_fn(void (*fn)(void)) {
    callback_fn = fn;
}

int main(int argc, char *argv[]) {
    // Setup signal handler for SIGUSR1
    signal(SIGUSR1, signal_handler);
    set_callback_fn(default_callback);

    // Simulate loading settings
    settings.interval = 0.128;
    strcpy(settings.current_sensor, "full");
    for (int i = 0; i < 4; ++i) {
        settings.cal_offsets[i] = 0.0;
        settings.cal_gains[i] = 1.0;
        settings.cal_skew_times[i] = 0.0;
    }
    set_current_channel();

    int run_calibrated = 1;
    if (argc == 2 && strcmp(argv[1], "--uncalibrated") == 0) {
        run_calibrated = 0;
    }

    int delay_line[DELAY_LINE_LENGTH][4] = {0};
    int i = 0;
    float offsets[4], gains[4];
    int delays[4];
    if (run_calibrated) {
        calibrated_constants(offsets, gains, delays);
    } else {
        uncalibrated_constants(offsets, gains, delays);
    }

    int delay_lookup[4];
    for (int k = 0; k < 4; ++k) delay_lookup[k] = delays[k];

    char line[128];
    while (fgets(line, sizeof(line), stdin)) {
        char *token;
        int new_sample[4];
        int idx = 0;
        token = strtok(line, " \n");
        while (token && idx < 4) {
            new_sample[idx++] = from_twos_complement_hex(token);
            token = strtok(NULL, " \n");
        }
        for (int d = 1; d < DELAY_LINE_LENGTH; ++d) {
            memcpy(delay_line[d-1], delay_line[d], 4 * sizeof(int));
        }
        memcpy(delay_line[DELAY_LINE_LENGTH-1], new_sample, 4 * sizeof(int));
        float scaled[4];
        int corrected[4];
        for (int k = 0; k < 4; ++k) {
            corrected[k] = delay_line[DELAY_LINE_LENGTH + delay_lookup[k]] [k];
        }
        scale_readings(corrected, offsets, gains, scaled);
        float voltage = scaled[3];
        float current = scaled[current_channel];
        float power = voltage * current;
        float leakage_current = scaled[0];
        double t = settings.interval * i;
        printf("%12.4f %10.3f %10.5f %10.3f %12.7f\n", t, voltage, current, power, leakage_current);
        i++;
    }
    return 0;
}
