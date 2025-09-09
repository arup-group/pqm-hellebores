// analysis_to_csv.c: C translation of analysis_to_csv.py
// Compile with: gcc -o analysis_to_csv analysis_to_csv.c -lcjson
// Usage: ./analysis_to_csv < input.json > output.csv

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "cjson/cJSON.h"

const char *wanted_keys[] = {
    "rms_voltage","rms_current","mean_power","mean_volt_ampere_reactive",
    "mean_volt_ampere","watt_hour","volt_ampere_reactive_hour",
    "volt_ampere_hour","hours","power_factor","crest_factor_current",
    "frequency","rms_leakage_current","total_harmonic_distortion_voltage_percentage",
    "total_harmonic_distortion_current_percentage"
};
// this determines the number of elements in the array from the total size of the array divided by
// the element size, which is in this case a char * pointer of fixed size.
const int wanted_keys_count = sizeof(wanted_keys)/sizeof(wanted_keys[0]);

void print_csv_header() {
    printf("timestamp");
    for (int i = 0; i < wanted_keys_count; ++i) printf(",%s", wanted_keys[i]);
    printf("\n");
}

void print_csv_row(cJSON *json) {
    // Print timestamp
    time_t now = time(NULL);
    struct tm *tm_info = localtime(&now);
    char buf[32];
    strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", tm_info);
    printf("%s", buf);
    // Print wanted values
    for (int i = 0; i < wanted_keys_count; ++i) {
        cJSON *item = cJSON_GetObjectItem(json, wanted_keys[i]);
        if (item && (cJSON_IsNumber(item) || cJSON_IsString(item))) {
            if (cJSON_IsNumber(item)) printf(",%g", item->valuedouble);
            else printf(",%s", item->valuestring);
        } else {
            printf(",");
        }
    }
    printf("\n");
}

int main() {
    char line[4096];
    // Skip first two lines
    for (int i = 0; i < 2; ++i) if (!fgets(line, sizeof(line), stdin)) return 1;
    // Third line: print header and first row
    if (fgets(line, sizeof(line), stdin)) {
        cJSON *json = cJSON_Parse(line);
        if (json) {
            print_csv_header();
            print_csv_row(json);
            cJSON_Delete(json);
        }
    }
    // Remaining lines: print rows only
    while (fgets(line, sizeof(line), stdin)) {
        cJSON *json = cJSON_Parse(line);
        if (json) {
            print_csv_row(json);
            cJSON_Delete(json);
        }
    }
    return 0;
}
