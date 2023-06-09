#!/usr/bin/env python3

import sys
import os
import signal
import json
import psutil
import time


class Settings():
    sfile = 'settings.json'

    def set_derived_settings(self):
        self.interval                   = 1000.0 / self.sample_rate
        self.time_axis_per_division     = self.time_display_ranges[self.time_display_index]
        self.voltage_axis_per_division  = self.voltage_display_ranges[self.voltage_display_index]
        self.current_axis_per_division  = self.current_display_ranges[self.current_display_index]
        self.power_axis_per_division    = self.power_display_ranges[self.power_display_index]
        self.earth_leakage_current_axis_per_division  = \
            self.earth_leakage_current_display_ranges[self.earth_leakage_current_display_index]
        self.pre_trigger_time           = self.time_axis_pre_trigger_divisions * self.time_axis_per_division
        self.post_trigger_time          = self.time_axis_divisions * self.time_axis_per_division - self.pre_trigger_time
        self.post_trigger_samples       = int(self.post_trigger_time / self.interval)
        self.pre_trigger_samples        = int(self.pre_trigger_time / self.interval)
        # sometimes rounding errors give us 1 too many samples, so reduce by 1.
        self.frame_samples              = self.pre_trigger_samples + self.post_trigger_samples - 1
        # we set a hold-off threshold (minimum number of samples to next trigger) to be slightly less
        # (2ms) than one full screenful of data, and minimum time of 10ms.
        self.holdoff_samples            = max(int(0.010 * self.sample_rate), self.frame_samples - int(0.002 * self.sample_rate))
        self.time_shift                 = self.time_axis_pre_trigger_divisions * self.time_axis_per_division
        self.x_pixels                   = self.time_axis_divisions * self.horizontal_pixels_per_division
        self.y_pixels                   = self.vertical_axis_divisions * self.vertical_pixels_per_division
        self.half_y_pixels              = self.y_pixels // 2
 

    def set_settings(self, js):
        self.frequency                                 = js['frequency']
        self.sample_rate                               = js['sample_rate']
        self.time_axis_divisions                       = js['time_axis_divisions']
        self.time_axis_pre_trigger_divisions           = js['time_axis_pre_trigger_divisions']
        self.vertical_axis_divisions                   = js['vertical_axis_divisions']
        self.horizontal_pixels_per_division            = js['horizontal_pixels_per_division']
        self.vertical_pixels_per_division              = js['vertical_pixels_per_division']
        self.time_display_ranges                       = js['time_display_ranges']
        self.time_display_index                        = js['time_display_index']
        self.voltage_display_ranges                    = js['voltage_display_ranges']
        self.voltage_display_index                     = js['voltage_display_index'] 
        self.voltage_display_status                    = js['voltage_display_status']
        self.current_display_ranges                    = js['current_display_ranges']
        self.current_display_index                     = js['current_display_index']
        self.current_display_status                    = js['current_display_status']
        self.power_display_ranges                      = js['power_display_ranges']
        self.power_display_index                       = js['power_display_index']
        self.power_display_status                      = js['power_display_status']
        self.earth_leakage_current_display_ranges      = js['earth_leakage_current_display_ranges']
        self.earth_leakage_current_display_index       = js['earth_leakage_current_display_index']
        self.earth_leakage_current_display_status      = js['earth_leakage_current_display_status']
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
        self.trigger_slope                             = js['trigger_slope']
        self.trigger_level                             = js['trigger_level']
        self.trigger_position                          = js['trigger_position']
        self.trigger_mode                              = js['trigger_mode']
        # now settings that are derived from the above
        self.set_derived_settings()


    def make_json(self):
        js = {}
        js['frequency']                                = self.frequency
        js['sample_rate']                              = self.sample_rate
        js['time_axis_divisions']                      = self.time_axis_divisions
        js['time_axis_pre_trigger_divisions']          = self.time_axis_pre_trigger_divisions
        js['vertical_axis_divisions']                  = self.vertical_axis_divisions
        js['horizontal_pixels_per_division']           = self.horizontal_pixels_per_division
        js['vertical_pixels_per_division']             = self.vertical_pixels_per_division
        js['time_display_ranges']                      = self.time_display_ranges
        js['time_display_index']                       = self.time_display_index
        js['voltage_display_ranges']                   = self.voltage_display_ranges
        js['voltage_display_index']                    = self.voltage_display_index
        js['voltage_display_status']                   = self.voltage_display_status
        js['current_display_ranges']                   = self.current_display_ranges
        js['current_display_index']                    = self.current_display_index
        js['current_display_status']                   = self.current_display_status 
        js['power_display_ranges']                     = self.power_display_ranges
        js['power_display_index']                      = self.power_display_index
        js['power_display_status']                     = self.power_display_status
        js['earth_leakage_current_display_ranges']     = self.earth_leakage_current_display_ranges
        js['earth_leakage_current_display_index']      = self.earth_leakage_current_display_index
        js['earth_leakage_current_display_status']     = self.earth_leakage_current_display_status
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
        js['trigger_slope']                            = self.trigger_slope
        js['trigger_level']                            = self.trigger_level
        js['trigger_position']                         = self.trigger_position
        js['trigger_mode']                             = self.trigger_mode
        # return the resulting json dictionary 
        return js 
 
 
    def load_settings(self):
        try:
            f = open(self.sfile, 'r')
            js = json.loads(f.read())
            f.close()
        except:
            print("settings.py, get_settings(): couldn't read settings.json, regenerating...", file=sys.stderr)
            js = json.loads(default_settings)
            self.save_settings()
        return js


    def save_settings(self):
        try:
            f = open(self.sfile, 'w')
            f.write(json.dumps(self.make_json(), indent=4))
            f.close()
        except:
            print("settings.py, save_settings(): couldn't write settings.json.", file=sys.stderr)


    def signal_handler(self, signum, frame):
        self.set_settings(self.load_settings())
        self.callback_fn()

    # settings objects are created in each running program.
    # The send_to_all function allows one program (hellebores.py) to inform all the others that settings
    # have been changed. When they receive this signal, they will re-load the settings from file.
    def _send_to_all(self):
        self.set_derived_settings()
        self.save_settings()
        for pid in self.pids:
            os.kill(pid, signal.SIGUSR1)
 

    def get_program_pids(self, other_programs):
        # we use the psutils module to find the other programs
        pids = {}
        for p in psutil.process_iter():
            try:
                # we check for python to avoid sending signals to the shell
                # and we also check to avoid sending signals to ourself
                pcmd = ' '.join(p.cmdline())
                for program in other_programs:
                    if program in pcmd:
                        pids[p.pid] = pcmd
            except:
                # p.cmdline() generates permission errors on some system processes
                pass 
        return pids.keys()


    def __init__(self, callback_fn = lambda: None, other_programs=[]):
        # load initial settings
        self.set_settings(self.load_settings())

        # set a callback function if provided. This will be called
        # every time a signal is received just after settings have been updated
        self.callback_fn = callback_fn

        # if we receive 'SIGUSR1' signal (on linux/unix) set things up so that updated settings will
        # be read from settings.json via the signal_handler function
        if os.name == 'posix':
            # for faster update performance, and to reduce SD card wear, we save the settings.json
            # file to RAM disk in /tmp, and we'll use the temporary version from now on
            if os.system(f'[ -d /tmp/pqm-hellebores ] || mkdir /tmp/pqm-hellebores') == 0:
                # (NB 0 means the command succeeded, the directory exists)
                self.sfile = f'/tmp/pqm-hellebores/{self.sfile}'
                self.save_settings()
            # wait a moment before gathering process pids, to make sure all the programs have started
            time.sleep(0.5)
            self.pids = self.get_program_pids(other_programs)
            # link to the send_to_all function and set up a signal handler
            self.send_to_all = self._send_to_all
            signal.signal(signal.SIGUSR1, self.signal_handler)
        else: 
            self.send_to_all = lambda: print(f"settings.py: send_to_all() function hasn't been implemented on {sys.platform}.", file=sys.stderr)


default_settings = '''
{
    "frequency": 51.0,
    "sample_rate": 7812.5,
    "time_axis_divisions": 10,
    "time_axis_pre_trigger_divisions": 5,
    "vertical_axis_divisions": 8,
    "horizontal_pixels_per_division": 70,
    "vertical_pixels_per_division": 60,
    "time_display_ranges": [
        0.1,
        0.2,
        0.4,
        1,
        2,
        4,
        10,
        20,
        40,
        100
    ],
    "time_display_index": 5,
    "voltage_display_ranges": [
        50,
        100,
        200,
        500
    ],
    "voltage_display_index": 2,
    "voltage_display_status": true,
    "current_display_ranges": [
        0.001,
        0.002,
        0.005,
        0.01,
        0.02,
        0.05,
        0.1,
        0.2,
        0.5,
        1.0,
        2.0
    ],
    "current_display_index": 8,
    "current_display_status": true,
    "power_display_ranges": [
        0.1,
        0.2,
        0.5,
        1.0,
        2.0,
        5.0,
        10.0,
        20.0,
        50.0,
        100.0,
        200.0,
        500.0
    ],
    "power_display_index": 8,
    "power_display_status": true,
    "earth_leakage_current_display_ranges": [
        0.0001,
        0.0002,
        0.0005,
        0.001,
        0.002,
        0.005,
        0.01
    ],
    "earth_leakage_current_display_index": 4,
    "earth_leakage_current_display_status": true,
    "adc_offset_trim_c0": -30,
    "adc_offset_trim_c1": -36,
    "adc_offset_trim_c2": -30,
    "adc_offset_trim_c3": 0,
    "adc_amplifier_gain_c0": 32,
    "adc_amplifier_gain_c1": 2,
    "adc_amplifier_gain_c2": 2,
    "adc_amplifier_gain_c3": 1,
    "scale_c0": -4.08e-07,
    "scale_c1": 2.44e-05,
    "scale_c2": 0.001017,
    "scale_c3": 0.0489,
    "trigger_channel": 0,
    "trigger_slope": "rising",
    "trigger_level": 0.0,
    "trigger_position": 5,
    "trigger_mode": "sync"
}
'''


