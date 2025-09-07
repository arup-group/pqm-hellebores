// framer.c: C translation of framer.py
// Requires cJSON for settings loading
// gcc -o framer framer.c -lcjson -lm

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <signal.h>
#include <unistd.h>
#include "cjson/cJSON.h"

#define BUFFER_SIZE 65536
#define MAX_FORWARD_READ 8192
#define SHORT_DOTS "................................"
#define LONG_DOTS "................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................"
#define Y_MAX 479
#define Y_MIN 0
#define VOLTAGE_INDEX 0
#define CURRENT_INDEX 1
#define POWER_INDEX 2
#define EARTH_LEAKAGE_INDEX 3

struct Settings {
    double interval;
    int time_axis_pre_trigger_divisions;
    int horizontal_pixels_per_division;
    int time_axis_per_division;
    int vertical_pixels_per_division;
    int voltage_axis_per_division;
    int current_axis_per_division;
    int power_axis_per_division;
    int earth_leakage_current_axis_per_division;
    char run_mode[16];
    char trigger_mode[16];
    char trigger_slope[16];
    double inrush_trigger_level;
    double sample_rate;
};

struct Mapper {
    int x_zero;
    int y_zero;
    struct Settings *st;
    int output_format; // 0: pixels, 1: values
};

void configure_mapper(struct Mapper *mapper) {
    mapper->x_zero = mapper->st->time_axis_pre_trigger_divisions * mapper->st->horizontal_pixels_per_division;
    mapper->y_zero = Y_MAX / 2;
}

void pixels_out(struct Mapper *mapper, double timestamp, double *sample, char *out) {
    int x = (int)(timestamp * mapper->st->horizontal_pixels_per_division / mapper->st->time_axis_per_division) + mapper->x_zero;
    int y0 = fmin(fmax(Y_MIN, (int)(-sample[0] * mapper->st->vertical_pixels_per_division / mapper->st->voltage_axis_per_division) + mapper->y_zero), Y_MAX);
    int y1 = fmin(fmax(Y_MIN, (int)(-sample[1] * mapper->st->vertical_pixels_per_division / mapper->st->current_axis_per_division) + mapper->y_zero), Y_MAX);
    int y2 = fmin(fmax(Y_MIN, (int)(-sample[2] * mapper->st->vertical_pixels_per_division / mapper->st->power_axis_per_division) + mapper->y_zero), Y_MAX);
    int y3 = fmin(fmax(Y_MIN, (int)(-sample[3] * mapper->st->vertical_pixels_per_division / mapper->st->earth_leakage_current_axis_per_division) + mapper->y_zero), Y_MAX);
    sprintf(out, "%4d %4d %4d %4d %4d", x, y0, y1, y2, y3);
}

void values_out(double timestamp, double *sample, char *out) {
    sprintf(out, "%12.4f %10.3f %10.5f %10.3f %12.7f", timestamp, sample[0], sample[1], sample[2], sample[3]);
}

struct Buffer {
    double buf[BUFFER_SIZE][4];
    int frame_startp, frame_endp, sp, tp;
    int sync_holdoff_counter, inrush_holdoff_counter;
    int frame_samples, pre_trigger_samples, post_trigger_samples, sync_holdoff_samples;
    double interpolation_fraction;
    int frame_triggered, inrush_triggered, stop_flag, reframed;
    struct Settings *st;
};

void clear_buffer(struct Buffer *buffer) {
    for (int i = 0; i < BUFFER_SIZE; ++i) {
        for (int j = 0; j < 4; ++j) buffer->buf[i][j] = 0.0;
    }
}

void store_line(struct Buffer *buffer, const char *line) {
    buffer->sp++;
    double vals[4] = {0.0, 0.0, 0.0, 0.0};
    sscanf(line, "%lf %lf %lf %lf", &vals[0], &vals[1], &vals[2], &vals[3]);
    for (int i = 0; i < 4; ++i) buffer->buf[buffer->sp % BUFFER_SIZE][i] = vals[i];
}

void update_frame_markers(struct Buffer *buffer) {
    if (buffer->interpolation_fraction < 0.5)
        buffer->frame_startp = buffer->tp - buffer->pre_trigger_samples - 1;
    else
        buffer->frame_startp = buffer->tp - buffer->pre_trigger_samples;
    buffer->frame_endp = buffer->frame_startp + buffer->frame_samples;
    buffer->reframed = 1;
}

void output_frame(struct Buffer *buffer, struct Mapper *mapper) {
    double precise_trigger_position = buffer->tp - 1 + buffer->interpolation_fraction;
    char out[128];
    for (int s = buffer->frame_startp; s < buffer->frame_endp; ++s) {
        double timestamp = buffer->st->interval * (s - precise_trigger_position);
        double *sample = buffer->buf[s % BUFFER_SIZE];
        if (mapper->output_format == 0)
            pixels_out(mapper, timestamp, sample, out);
        else
            values_out(timestamp, sample, out);
        printf("%s\n", out);
    }
    if (strcmp(buffer->st->run_mode, "stopped") == 0 || buffer->stop_flag)
        printf("%s\n", LONG_DOTS);
    else
        printf("%s\n", SHORT_DOTS);
}

int main(int argc, char *argv[]) {
    // Minimal settings loading (expand as needed)
    struct Settings st = {
        .interval = 0.128,
        .time_axis_pre_trigger_divisions = 5,
        .horizontal_pixels_per_division = 70,
        .time_axis_per_division = 10,
        .vertical_pixels_per_division = 60,
        .voltage_axis_per_division = 500,
        .current_axis_per_division = 1,
        .power_axis_per_division = 1000,
        .earth_leakage_current_axis_per_division = 0.002,
        .run_mode = "running",
        .trigger_mode = "sync",
        .trigger_slope = "rising",
        .inrush_trigger_level = 0.2,
        .sample_rate = 7812.5
    };
    int output_format = 0;
    if (argc > 1 && strcmp(argv[1], "--unmapped") == 0) output_format = 1;
    struct Mapper mapper = { .st = &st, .output_format = output_format };
    configure_mapper(&mapper);
    struct Buffer buffer = { .st = &st };
    clear_buffer(&buffer);
    // Main loop: read lines, store, and output frames
    char line[128];
    while (fgets(line, sizeof(line), stdin)) {
        store_line(&buffer, line);
        // ... trigger logic and frame management would go here ...
        // For demonstration, just output the frame for each line
        output_frame(&buffer, &mapper);
    }
    return 0;
}
