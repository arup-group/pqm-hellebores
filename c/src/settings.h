// settings.h: C translation of settings.py

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
    float cal_offsets[4];
    float cal_gains[4];
    float cal_skew_times[4];
    // Derived settings
    double interval;
    int current_channel;
    // Callback
    void (*callback_fn) (void);
};

void set_derived_settings(struct Settings *st);

void default_callback();

void set_callback_fn(struct Settings *st, void (*fn) (void));

int load_settings(struct Settings *st);

char *stringify_array_of_doubles(const double *double_array, int double_array_length);

char *stringify_array_of_ints(const int int_array[], int int_array_length);

void show_settings(struct Settings *st);

void signal_handler(int signum);

int setup();
