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
#define DEFAULT_SETTINGS_JSON "{\"analysis_max_min_reset\": 0,\"analysis_accumulators_reset\": 0,\"sample_rate\": 7812.5,\"time_axis_divisions\": 10,\"time_axis_pre_trigger_divisions\": 5,\"vertical_axis_divisions\": 8,\"horizontal_pixels_per_division\": 70,\"vertical_pixels_per_division\": 60,\"time_display_ranges\": [1,2,4,10,20,40,100],\"time_display_index\": 3,\"voltage_display_ranges\": [50,100,200,500],\"voltage_display_index\": 3,\"voltage_display_status\": true,\"current_sensor\": \"full\",\"current_display_ranges\": [0.001,0.002,0.005,0.01,0.02,0.05,0.1,0.2,0.5,1.0,2.0,5.0],\"current_display_index\": 10,\"current_display_status\": true,\"power_display_ranges\": [0.1,0.2,0.5,1.0,2.0,5.0,10.0,20.0,50.0,100.0,200.0,500.0,1000.0],\"power_display_index\": 11,\"power_display_status\": false,\"earth_leakage_current_display_ranges\": [0.0001,0.0002,0.0005,0.001,0.002],\"earth_leakage_current_display_index\": 4,\"earth_leakage_current_display_status\": false,\"trigger_slope\": \"rising\",\"inrush_trigger_level\": 0.2,\"trigger_position\": 5,\"trigger_mode\": \"sync\",\"run_mode\": \"running\"}"

struct Settings {
    double analysis_max_min_reset;
    double analysis_accumulators_reset;
    double sample_rate;
    int time_axis_divisions;
    int time_axis_pre_trigger_divisions;
    int vertical_axis_divisions;
    int horizontal_pixels_per_division;
    int vertical_pixels_per_division;
    double time_display_ranges[7];
    int time_display_index;
    double voltage_display_ranges[4];
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
        // check if the whole file was read
        if (fread(data, 1, len, f) != len) return -1;
        data[len] = '\0';
        fclose(f);
    }
    json = cJSON_Parse(data);
    free(data);
    // check for JSON parsing errors
    if (!json) return -1;
    // Parse fields (minimal, for brevity)
    st->analysis_max_min_reset = cJSON_GetObjectItem(json, "analysis_max_min_reset")->valuedouble;
    st->analysis_accumulators_reset = cJSON_GetObjectItem(json, "analysis_accumulators_reset")->valuedouble;
    st->sample_rate = cJSON_GetObjectItem(json, "sample_rate")->valuedouble;
    st->time_axis_divisions = cJSON_GetObjectItem(json, "time_axis_divisions")->valueint;
    st->time_axis_pre_trigger_divisions = cJSON_GetObjectItem(json, "time_axis_pre_trigger_divisions")->valueint;
    st->vertical_axis_divisions = cJSON_GetObjectItem(json, "vertical_axis_divisions")->valueint;
    st->horizontal_pixels_per_division = cJSON_GetObjectItem(json, "horizontal_pixels_per_division")->valueint;
    st->vertical_pixels_per_division = cJSON_GetObjectItem(json, "vertical_pixels_per_division")->valueint;
    cJSON *arr = cJSON_GetObjectItem(json, "time_display_ranges");
    for (int i = 0; i < 7; i++) st->time_display_ranges[i] = cJSON_GetArrayItem(arr, i)->valuedouble;
    st->time_display_index = cJSON_GetObjectItem(json, "time_display_index")->valueint;
    arr = cJSON_GetObjectItem(json, "voltage_display_ranges");
    for (int i = 0; i < 4; i++) st->voltage_display_ranges[i] = cJSON_GetArrayItem(arr, i)->valuedouble;
    st->voltage_display_index = cJSON_GetObjectItem(json, "voltage_display_index")->valueint;
    st->voltage_display_status = cJSON_GetObjectItem(json, "voltage_display_status")->valueint;
    strcpy(st->current_sensor, cJSON_GetObjectItem(json, "current_sensor")->valuestring);
    arr = cJSON_GetObjectItem(json, "current_display_ranges");
    for (int i = 0; i < 12; i++) st->current_display_ranges[i] = cJSON_GetArrayItem(arr, i)->valuedouble;
    st->current_display_index = cJSON_GetObjectItem(json, "current_display_index")->valueint;
    st->current_display_status = cJSON_GetObjectItem(json, "current_display_status")->valueint;
    arr = cJSON_GetObjectItem(json, "power_display_ranges");
    for (int i = 0; i < 13; i++) st->power_display_ranges[i] = cJSON_GetArrayItem(arr, i)->valuedouble;
    st->power_display_index = cJSON_GetObjectItem(json, "power_display_index")->valueint;
    st->power_display_status = cJSON_GetObjectItem(json, "power_display_status")->valueint;
    arr = cJSON_GetObjectItem(json, "earth_leakage_current_display_ranges");
    for (int i = 0; i < 5; i++) st->earth_leakage_current_display_ranges[i] = cJSON_GetArrayItem(arr, i)->valuedouble;
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

char *stringify_array_of_doubles(const double *double_array, int double_array_length) {
    static char array_as_string[128];
    char value_as_string[16];
    size_t ch = 0;
    snprintf(array_as_string + ch, 2, "[");
    ch++;
    for (int i = 0; i < double_array_length; i++) {
        snprintf(value_as_string, 16, "%.5g", double_array[i]);
        snprintf(array_as_string + ch, 128 - ch, "%s, ", value_as_string);
        ch = ch + strlen(value_as_string) + 2;
    }
    // overwrites final comma and space with a close bracket
    snprintf(array_as_string + ch - 2, 2, "]");
    return array_as_string;
}

char *stringify_array_of_ints(const int int_array[], int int_array_length) {
    static char array_as_string[128];
    char value_as_string[16];
    size_t ch = 0;
    snprintf(array_as_string + ch, 2, "[");
    for (int i = 0; i < int_array_length; i++) {
        snprintf(value_as_string, 16, "%d", int_array[i]);
        snprintf(array_as_string + ch, 128 - ch, "%s, ", value_as_string);
        ch = ch + strlen(value_as_string) + 2;
    }
    // overwrites final comma with a close bracket
    snprintf(array_as_string + ch - 2, 2, "]");
    return array_as_string;
}


void show_settings(const struct Settings *st) {
    printf("Settings:\n");
    printf("  other_programs                          : %s\n", "[don't know yet]");
//    printf("  identity: %s\n", st->identity);
//    printf("  cal_offsets: %s\n", stringify_array_of_ints(st->cal_offsets));
//    printf("  cal_gains: %s\n", stringify_array_of_ints(st->cal_gains);
//    printf("  cal_skew_times: %s\n", stringify_array_of_doubles(st->cal_skew_times));
    printf("  settings_file                           : %s\n", "don't know");
    printf("  sample_rate                             : %.2f\n", st->sample_rate);
    printf("  time_axis_divisions                     : %d\n", st->time_axis_divisions);
    printf("  time_axis_pre_trigger_divisions         : %d\n", st->time_axis_pre_trigger_divisions);
    printf("  vertical_axis_divisions                 : %d\n", st->vertical_axis_divisions);
    printf("  horizontal_pixels_per_division          : %d\n", st->horizontal_pixels_per_division);
    printf("  vertical_pixels_per_division            : %d\n", st->vertical_pixels_per_division);
    printf("  time_display_ranges                     : %s\n", stringify_array_of_doubles(st->time_display_ranges, 7));
    printf("  time_display_index                      : %d\n", st->time_display_index);
    printf("  voltage_display_ranges                  : %s\n", stringify_array_of_doubles(st->voltage_display_ranges, 4));
    printf("  voltage_display_index                   : %d\n", st->voltage_display_index);
    printf("  current_display_ranges                  : %s\n", stringify_array_of_doubles(st->current_display_ranges, 12));
    printf("  current_display_index                   : %d\n", st->current_display_index);
}

/*
  other_programs                          : []
  reload_on_signal                        : True
  identity                                : PQM-0
  cal_offsets                             : [0.0, 0.0, 0.0, 0.0]
  cal_gains                               : [1.0, 1.0, 1.0, 1.0]
  cal_skew_times                          : [0, 0, 0, 0]
  settings_file                           : /mnt/c/adam/code/python/pqm-hellebores/configuration/settings.json
  analysis_max_min_reset                  : 0
  analysis_accumulators_reset             : 0
  time_display_index                      : 3
  voltage_display_ranges                  : [50, 100, 200, 500]
  voltage_display_index                   : 3
  voltage_display_status                  : True
  current_sensor                          : full
  current_display_ranges                  : [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
  current_display_index                   : 10
  current_display_status                  : True
  power_display_ranges                    : [0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1000.0]
  power_display_index                     : 11
  power_display_status                    : False
  earth_leakage_current_display_ranges    : [0.0001, 0.0002, 0.0005, 0.001, 0.002]
  earth_leakage_current_display_index     : 4
  earth_leakage_current_display_status    : False
  trigger_slope                           : rising
  inrush_trigger_level                    : 0.2
  trigger_position                        : 5
  trigger_mode                            : sync
  run_mode                                : running
  interval                                : 0.128
  time_axis_per_division                  : 10
  voltage_axis_per_division               : 500
  current_axis_per_division               : 2.0
  power_axis_per_division                 : 500.0
  earth_leakage_current_axis_per_division : 0.002
  callback_fn                             : <function Settings.<lambda> at 0x787d0d2d4280>
*/


void signal_handler(int signum) {
    printf("Signal received: %d\n", signum);
    load_settings(&settings);
    if (settings.callback_fn) settings.callback_fn();
}


int setup() {
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
