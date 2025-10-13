// settings.h: C translation of settings.py

#ifndef settings__h
#define settings__h

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
    double time_axis_per_division;
    double voltage_display_ranges[4];
    int voltage_display_index;
    int voltage_display_status;
    double voltage_axis_per_division;
    char current_sensor[16];
    double current_display_ranges[12];
    int current_display_index;
    int current_display_status;
    double current_axis_per_division;
    double power_display_ranges[13];
    int power_display_index;
    int power_display_status;
    double power_axis_per_division;
    double earth_leakage_current_display_ranges[5];
    int earth_leakage_current_display_index;
    int earth_leakage_current_display_status;
    double earth_leakage_current_axis_per_division;
    char trigger_slope[16];
    double inrush_trigger_level;
    int trigger_position;
    char trigger_mode[16];
    char run_mode[16];
    float cal_offsets[4];
    float cal_gains[4];
    float cal_skew_times[4];
    // Derived settings
    double interval;
    int current_channel;
    // Callback
    void (*callback_fn) (void);
};


struct Settings *settings_setup();

void settings_set_callback_fn(struct Settings *st, void (*fn) (void));

void settings_set_derived_settings(struct Settings *st);

#endif
