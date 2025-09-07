// settings.c: C translation of settings.py
// Requires cJSON library for JSON parsing
// gcc -o settings settings.c -lcjson

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include "cjson/cJSON.h"

#define SETTINGS_PATH "../configuration/settings.json"
#define DEFAULT_SETTINGS_JSON "{\n\"analysis_max_min_reset\": 0,\n\"analysis_accumulators_reset\": 0,\n\"sample_rate\": 7812.5,\n\"time_axis_divisions\": 10,\n\"time_axis_pre_trigger_divisions\": 5,\n\"vertical_axis_divisions\": 8,\n\"horizontal_pixels_per_division\": 70,\n\"vertical_pixels_per_division\": 60,\n\"time_display_ranges\": [1,2,4,10,20,40,100],\n\"time_display_index\": 3,\n\"voltage_display_ranges\": [50,100,200,500],\n\"voltage_display_index\": 3,\n\"voltage_display_status\": true,\n\"current_sensor\": \"full\",\n\"current_display_ranges\": [0.001,0.002,0.005,0.01,0.02,0.05,0.1,0.2,0.5,1.0,2.0,5.0],\n\"current_display_index\": 10,\n\"current_display_status\": true,\n\"power_display_ranges\": [0.1,0.2,0.5,1.0,2.0,5.0,10.0,20.0,50.0,100.0,200.0,500.0,1000.0],\n\"power_display_index\": 11,\n\"power_display_status\": false,\n\"earth_leakage_current_display_ranges\": [0.0001,0.0002,0.0005,0.001,0.002],\n\"earth_leakage_current_display_index\": 4,\n\"earth_leakage_current_display_status\": false,\n\"trigger_slope\": \"rising\",\n\"inrush_trigger_level\": 0.2,\n\"trigger_position\": 5,\n\"trigger_mode\": \"sync\",\n\"run_mode\": \"running\"}"

struct Settings {
    double analysis_max_min_reset;
    double analysis_accumulators_reset;
    double sample_rate;
    double time_axis_divisions;
    double time_axis_pre_trigger_divisions;
    double vertical_axis_divisions;
    double horizontal_pixels_per_division;
    double vertical_pixels_per_division;
    int time_display_ranges[7];
    int time_display_index;
    int voltage_display_ranges[4];
    int voltage_display_index;
    int voltage_display_status;
    char current_sensor[16];
    double current_display_ranges[12];
    int current_display_index;
    int current_display_status;
    double power_display_ranges[13];
    int power_display_index;
    int power_display_status;
    double earth_leakage_current_display_ranges[5];
    int earth_leakage_current_display_index;
    int earth_leakage_current_display_status;
    char trigger_slope[16];
    double inrush_trigger_level;
    int trigger_position;
    char trigger_mode[16];
    char run_mode[16];
    // Derived settings
    double interval;
    // Callback
    void (*callback_fn)(void);
};

struct Settings settings;

void set_derived_settings(struct Settings *st) {
    st->interval = 1000.0 / st->sample_rate;
}

void default_callback() {
    printf("Callback: settings updated\n");
}

void set_callback_fn(struct Settings *st, void (*fn)(void)) {
    st->callback_fn = fn;
}

int load_settings(struct Settings *st) {
    FILE *f = fopen(SETTINGS_PATH, "r");
    char *data = NULL;
    cJSON *json = NULL;
    if (!f) {
        // fallback to default
        data = strdup(DEFAULT_SETTINGS_JSON);
    } else {
        fseek(f, 0, SEEK_END);
        long len = ftell(f);
        fseek(f, 0, SEEK_SET);
        data = malloc(len + 1);
        fread(data, 1, len, f);
        data[len] = '\0';
        fclose(f);
    }
    json = cJSON_Parse(data);
    free(data);
    if (!json) return -1;
    // Parse fields (minimal, for brevity)
    st->analysis_max_min_reset = cJSON_GetObjectItem(json, "analysis_max_min_reset")->valuedouble;
    st->analysis_accumulators_reset = cJSON_GetObjectItem(json, "analysis_accumulators_reset")->valuedouble;
    st->sample_rate = cJSON_GetObjectItem(json, "sample_rate")->valuedouble;
    st->time_axis_divisions = cJSON_GetObjectItem(json, "time_axis_divisions")->valuedouble;
    st->time_axis_pre_trigger_divisions = cJSON_GetObjectItem(json, "time_axis_pre_trigger_divisions")->valuedouble;
    st->vertical_axis_divisions = cJSON_GetObjectItem(json, "vertical_axis_divisions")->valuedouble;
    st->horizontal_pixels_per_division = cJSON_GetObjectItem(json, "horizontal_pixels_per_division")->valuedouble;
    st->vertical_pixels_per_division = cJSON_GetObjectItem(json, "vertical_pixels_per_division")->valuedouble;
    cJSON *arr = cJSON_GetObjectItem(json, "time_display_ranges");
    for (int i = 0; i < 7; ++i) st->time_display_ranges[i] = cJSON_GetArrayItem(arr, i)->valueint;
    st->time_display_index = cJSON_GetObjectItem(json, "time_display_index")->valueint;
    arr = cJSON_GetObjectItem(json, "voltage_display_ranges");
    for (int i = 0; i < 4; ++i) st->voltage_display_ranges[i] = cJSON_GetArrayItem(arr, i)->valueint;
    st->voltage_display_index = cJSON_GetObjectItem(json, "voltage_display_index")->valueint;
    st->voltage_display_status = cJSON_GetObjectItem(json, "voltage_display_status")->valueint;
    strcpy(st->current_sensor, cJSON_GetObjectItem(json, "current_sensor")->valuestring);
    arr = cJSON_GetObjectItem(json, "current_display_ranges");
    for (int i = 0; i < 12; ++i) st->current_display_ranges[i] = cJSON_GetArrayItem(arr, i)->valuedouble;
    st->current_display_index = cJSON_GetObjectItem(json, "current_display_index")->valueint;
    st->current_display_status = cJSON_GetObjectItem(json, "current_display_status")->valueint;
    arr = cJSON_GetObjectItem(json, "power_display_ranges");
    for (int i = 0; i < 13; ++i) st->power_display_ranges[i] = cJSON_GetArrayItem(arr, i)->valuedouble;
    st->power_display_index = cJSON_GetObjectItem(json, "power_display_index")->valueint;
    st->power_display_status = cJSON_GetObjectItem(json, "power_display_status")->valueint;
    arr = cJSON_GetObjectItem(json, "earth_leakage_current_display_ranges");
    for (int i = 0; i < 5; ++i) st->earth_leakage_current_display_ranges[i] = cJSON_GetArrayItem(arr, i)->valuedouble;
    st->earth_leakage_current_display_index = cJSON_GetObjectItem(json, "earth_leakage_current_display_index")->valueint;
    st->earth_leakage_current_display_status = cJSON_GetObjectItem(json, "earth_leakage_current_display_status")->valueint;
    strcpy(st->trigger_slope, cJSON_GetObjectItem(json, "trigger_slope")->valuestring);
    st->inrush_trigger_level = cJSON_GetObjectItem(json, "inrush_trigger_level")->valuedouble;
    st->trigger_position = cJSON_GetObjectItem(json, "trigger_position")->valueint;
    strcpy(st->trigger_mode, cJSON_GetObjectItem(json, "trigger_mode")->valuestring);
    strcpy(st->run_mode, cJSON_GetObjectItem(json, "run_mode")->valuestring);
    cJSON_Delete(json);
    set_derived_settings(st);
    return 0;
}

void show_settings(const struct Settings *st) {
    printf("Settings:\n");
    printf("  sample_rate: %.2f\n", st->sample_rate);
    printf("  interval: %.2f ms\n", st->interval);
    printf("  run_mode: %s\n", st->run_mode);
    // ... print other fields as needed ...
}

void signal_handler(int signum) {
    printf("Signal received: %d\n", signum);
    load_settings(&settings);
    if (settings.callback_fn) settings.callback_fn();
}

int main() {
    set_callback_fn(&settings, default_callback);
    if (load_settings(&settings) != 0) {
        fprintf(stderr, "Failed to load settings\n");
        return 1;
    }
    show_settings(&settings);
    // Setup signal handler for SIGUSR1
    signal(SIGUSR1, signal_handler);
    printf("Send SIGUSR1 to this process to reload settings and call callback.\n");
    while (1) {
        pause(); // Wait for signal
    }
    return 0;
}
