#!/usr/bin/env python3

import sys
import signal
import json



class Settings():

    def get_derived_settings(self):
            self.interval                = 1000.0 / self.sample_rate
            self.pre_trigger_time        = self.time_axis_pre_trigger_divisions * self.time_axis_per_division 
            self.post_trigger_time       = self.time_axis_divisions * self.time_axis_per_division - self.pre_trigger_time
            self.post_trigger_samples    = int(self.post_trigger_time / self.interval)
            self.pre_trigger_samples     = int(self.pre_trigger_time / self.interval)
            self.frame_samples           = self.pre_trigger_samples + self.post_trigger_samples
            # we set a hold-off threshold (minimum number of samples to next trigger) to be slightly less
            # (2ms) than one full screenful of data
            self.holdoff_samples         = self.frame_samples - int(0.002 * self.sample_rate)
            if self.trigger_direction == 'rising':
                self.trigger_hysteresis = 'LLLLLHHHHH'
            elif self.trigger_direction == 'falling':
                self.trigger_hysteresis = 'HHHHHLLLLL'
            self.trigger_gate_length = len(self.trigger_hysteresis)
            for i in range(self.trigger_gate_length):
                if self.trigger_hysteresis[i] != self.trigger_hysteresis[0]:
                    self.trigger_gate_transition = i
                    break
            self.time_shift              = self.time_axis_pre_trigger_divisions * self.time_axis_per_division
            self.x_pixels                = self.time_axis_divisions * self.horizontal_pixels_per_division
            self.y_pixels                = self.vertical_axis_divisions * self.vertical_pixels_per_division
            self.half_y_pixels           = self.y_pixels // 2
 

    def get_default_settings(self):
        self.frequency                                 = 50.0
        self.sample_rate                               = 7812.5
        self.time_axis_per_division                    = 4.0        # milliseconds
        self.time_axis_divisions                       = 10
        self.time_axis_pre_trigger_divisions           = 1
        self.voltage_axis_per_division                 = 100.0      # volts
        self.current_axis_per_division                 = 1.0        # amps
        self.power_axis_per_division                   = 10.0       # watts 
        self.earth_leakage_current_axis_per_division   = 0.0001     # amps
        self.vertical_axis_divisions                   = 8
        self.adc_offset_trim_c0                        = 23
        self.adc_offset_trim_c1                        = 0
        self.adc_offset_trim_c2                        = 0
        self.adc_offset_trim_c3                        = 0
        self.adc_amplifier_gain_c0                     = 32
        self.adc_amplifier_gain_c1                     = 1
        self.adc_amplifier_gain_c2                     = 1
        self.adc_amplifier_gain_c3                     = 1
        self.scale_c0                                  = 0.002
        self.scale_c1                                  = 0.03
        self.scale_c2                                  = 0.05
        self.scale_c3                                  = 0.05
        self.trigger_channel                           = 3
        self.trigger_direction                         = 'rising'
        self.trigger_threshold                         = 0.0
        self.horizontal_pixels_per_division            = 70
        self.vertical_pixels_per_division              = 60

 
    def get_settings(self):
        try:
            f = open("settings.json", "r")
            js = json.loads(f.read())
            f.close()
            self.frequency                                 = js['frequency']
            self.sample_rate                               = js['sample_rate']
            self.time_axis_per_division                    = js['time_axis_per_division']
            self.time_axis_divisions                       = js['time_axis_divisions']
            self.time_axis_pre_trigger_divisions           = js['time_axis_pre_trigger_divisions']
            self.voltage_axis_per_division                 = js['voltage_axis_per_division']
            self.current_axis_per_division                 = js['current_axis_per_division']
            self.power_axis_per_division                   = js['power_axis_per_division']
            self.earth_leakage_current_axis_per_division   = js['earth_leakage_current_axis_per_division']
            self.vertical_axis_divisions                   = js['vertical_axis_divisions']
            self.adc_offset_trim_c0                        = js['adc_offset_trim_c0']
            self.adc_offset_trim_c1                        = js['adc_offset_trim_c1']
            self.adc_offset_trim_c2                        = js['adc_offset_trim_c2']
            self.adc_offset_trim_c3                        = js['adc_offset_trim_c3']
            self.adc_amplifier_gain_c0                     = js['adc_amplifier_gain_c0']
            self.adc_amplifier_gain_c1                     = js['adc_amplifier_gain_c1']
            self.adc_amplifier_gain_c2                     = js['adc_amplifier_gain_c2']
            self.adc_amplifier_gain_c3                     = js['adc_amplifier_gain_c3']
            self.scale_c0                                  = js['scale_c0']
            self.scale_c1                                  = js['scale_c1']
            self.scale_c2                                  = js['scale_c2']
            self.scale_c3                                  = js['scale_c3']
            self.trigger_channel                           = js['trigger_channel']
            self.trigger_direction                         = js['trigger_direction']
            self.trigger_threshold                         = js['trigger_threshold']
            self.horizontal_pixels_per_division            = js['horizontal_pixels_per_division']
            self.vertical_pixels_per_division              = js['vertical_pixels_per_division']
        except:
            print("settings.py, get_settings(): couldn't read settings.json.", file=sys.stderr)
            self.get_default_settings()
        self.get_derived_settings()


    def save_settings(self):
        js = {}
        try:
            f = open('settings.json', 'w')
            js['frequency']                                = self.frequency
            js['sample_rate']                              = self.sample_rate
            js['time_axis_per_division']                   = self.time_axis_per_division
            js['time_axis_divisions']                      = self.time_axis_divisions
            js['time_axis_pre_trigger_divisions']          = self.time_axis_pre_trigger_divisions
            js['voltage_axis_per_division']                = self.voltage_axis_per_division
            js['current_axis_per_division']                = self.current_axis_per_division
            js['power_axis_per_division']                  = self.power_axis_per_division
            js['earth_leakage_current_axis_per_division']  = self.earth_leakage_current_axis_per_division
            js['vertical_axis_divisions']                  = self.vertical_axis_divisions
            js['adc_offset_trim_c0']                       = self.adc_offset_trim_c0
            js['adc_offset_trim_c1']                       = self.adc_offset_trim_c1
            js['adc_offset_trim_c2']                       = self.adc_offset_trim_c2
            js['adc_offset_trim_c3']                       = self.adc_offset_trim_c3
            js['adc_amplifier_gain_c0']                    = self.adc_amplifier_gain_c0
            js['adc_amplifier_gain_c1']                    = self.adc_amplifier_gain_c1
            js['adc_amplifier_gain_c2']                    = self.adc_amplifier_gain_c2
            js['adc_amplifier_gain_c3']                    = self.adc_amplifier_gain_c3
            js['scale_c0']                                 = self.scale_c0
            js['scale_c1']                                 = self.scale_c1
            js['scale_c2']                                 = self.scale_c2
            js['scale_c3']                                 = self.scale_c3
            js['trigger_channel']                          = self.trigger_channel
            js['trigger_direction']                        = self.trigger_direction
            js['trigger_threshold']                        = self.trigger_threshold
            js['horizontal_pixels_per_division']           = self.horizontal_pixels_per_division
            js['vertical_pixels_per_division']             = self.vertical_pixels_per_division
            f.write(json.dumps(js, indent=4))
            f.close()
        except:
            print("settings.py, save_settings(): couldn't write settings.json.", file=sys.stderr)


    def signal_handler(self, signum, frame):
        self.get_settings()
        self.callback_fn()


    def __init__(self, callback_fn):
        self.get_settings()
        self.callback_fn = callback_fn
        # if we receive 'SIGUSR1' signal (on linux) updated settings will be read from settings.json
        # via the signal_handler function
        if sys.platform == 'linux':
            signal.signal(signal.SIGUSR1, self.signal_handler)


