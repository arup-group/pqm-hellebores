#!/usr/bin/env python3

import sys
import os
import signal
import json
import psutil
import time
import glob

CONFIGURATION_PATH = '../configuration'
SETTINGS_FILE = 'settings.json'        # NB settings file is later cached in /tmp
IDENTITY_FILE = 'identity'
CALIBRATIONS_FILE = 'calibrations.json'

class Settings():

    def get_identity(self):
        try:
            with open(os.path.join(CONFIGURATION_PATH, IDENTITY_FILE), 'r') as f:
                identity = f.read().rstrip()
        except:
            print('settings.py: using default identity', file=sys.stderr)
            identity = 'PQM-0'
        return identity

    def get_calibration(self, identity):
        try:
            with open(os.path.join(CONFIGURATION_PATH, CALIBRATIONS_FILE), 'r') as f:
                js = json.loads(f.read())
                cal = js[identity]
        except:
            print('settings.py: using default calibration', file=sys.stderr)
            cal = { 'offsets': [0.0, 0.0, 0.0, 0.0], \
                      'gains': [1.0, 1.0, 1.0, 1.0] }          
        return cal
 

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
 

    def set_settings(self, js, cal):
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
        self.adc_offset_trims                          = cal['offsets']
        self.adc_gain_trims                            = cal['gains']
        self.scale_factors                             = js['scale_factors']
        self.trigger_channel                           = js['trigger_channel']
        self.trigger_slope                             = js['trigger_slope']
        self.trigger_level                             = js['trigger_level']
        self.trigger_position                          = js['trigger_position']
        self.trigger_mode                              = js['trigger_mode']
        # now settings that are derived from the above
        self.set_derived_settings()


    def make_json(self):
        js = {}
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
        js['scale_factors']                            = self.scale_factors
        js['trigger_channel']                          = self.trigger_channel
        js['trigger_slope']                            = self.trigger_slope
        js['trigger_level']                            = self.trigger_level
        js['trigger_position']                         = self.trigger_position
        js['trigger_mode']                             = self.trigger_mode
        # return the resulting json dictionary 
        return js 
 
 
    def load_settings(self):
        try:
            with open(os.path.join(self.working_path, self.sfile), 'r') as f:
                js = json.loads(f.read())
        except:
            print(
                "settings.py, get_settings(): couldn't read settings.json, regenerating...",
                file=sys.stderr)
            js = json.loads(default_settings)
            self.save_settings()
        return js


    def save_settings(self):
        try:
            with open(os.path.join(self.working_path, self.sfile), 'w') as f:
                f.write(json.dumps(self.make_json(), indent=4))
        except:
            print(
                "settings.py, save_settings(): couldn't write settings.json.",
                file=sys.stderr)


    # settings objects are created in each running program.
    # The send_to_all function allows one program (hellebores.py) to inform all the others that settings
    # have been changed. When they receive this signal, they will re-load the settings from file.

    # On Raspberry Pi OS/ Ubuntu/ Mac (posix), we user defined signal SIGUSR1 is sent to only the
    # processes we want to signal, so the handling of this case is simpler.

    # On windows, signalling facilities are very limited:
    # 1. We can't pick individual programs, we have to send the signal to the whole process
    # group on the current console.
    # 2. In python we can only trap CTRL_C_EVENT signals (which arrive as SIGINT), all other signals cause
    # process termination. We use an environment variable to configure each program/instance
    # to behave in the way we want, including ignoring the signal when we are de-bugging and hellebores
    # is not running.

    def signal_handler(self, signum, frame):
        # for de-bugging on Windows, let the program quit if the environment variable hasn't been set
        if os.name == 'nt' and not ('CATCH_SIGINT' in os.environ):
            # default CTRL-C behaviour in python is to raise KeyError
            raise KeyError 
        if self.reload_on_signal == True:
            self.set_settings(self.load_settings(), self.cal)
            self.callback_fn()


    def send_to_all(self):
        self.set_derived_settings()
        self.save_settings()
        # On Posix, we send a signal to selected programs via process ID.
        if os.name == 'posix':
            for pid in self.get_program_pids(self.other_programs):
                os.kill(pid, signal.SIGUSR1)
        # On Windows, we have to send the signal to all programs in the current process group
        # ie programs that are running within the current console.
        elif os.name == 'nt':
            os.kill(0, signal.CTRL_C_EVENT)
        else:
            print(f"Don't know how to send signals on {os.name} platform.", file=sys.stderr)


    def get_program_pids(self, other_programs):
        # we use a function in the psutil module to find the PIDs of the other programs
        pids = {}
        if other_programs != []:
            for p in psutil.process_iter():
                try:
                    pcmd = ' '.join(p.cmdline())
                    for program in other_programs:
                        if program in pcmd:
                            # print(f'Collected PID {p.pid} for {pcmd}', file=sys.stderr)
                            pids[p.pid] = pcmd
                except:
                    # p.cmdline() generates permission errors on some system processes, so
                    # we ignore them and continue
                    pass 
        return pids.keys()


    def __init__(self, callback_fn = lambda: None, other_programs=[], reload_on_signal=True):
        self.other_programs = other_programs
        self.reload_on_signal = reload_on_signal

        # establish MAC address, identity and calibration factors
        self.identity = self.get_identity()
        self.cal = self.get_calibration(self.identity)

        # load initial settings
        self.sfile = SETTINGS_FILE
        self.working_path = CONFIGURATION_PATH
        self.set_settings(self.load_settings(), self.cal)

        # set a callback function if provided. This will be called
        # every time a signal is received just after settings have been updated
        self.callback_fn = callback_fn

        # if we receive 'UPDATE_SIGNAL' signal set things up so that updated settings will
        # be read from settings.json via the signal_handler function
        # for faster update performance, and to reduce SD card wear, if TEMP_DIR is set to RAM disk,
        # we change our working path so that we save updates to the settings.json file there.
        temp_dir = os.getenv('TEMP_DIR')
        if temp_dir != None:
            self.working_path = temp_dir

        # configure the signal handler
        if os.name == 'posix':
            signal.signal(signal.SIGUSR1, self.signal_handler)
        elif os.name == 'nt':
            signal.signal(signal.SIGINT, self.signal_handler)
        else:
            print(f"Don't know how to set up signals on {os.name} platform.", file=sys.stderr)


    def show_settings(self):
        print('Identity:')
        print(f'  {s.identity}')
        print('Calibration:')
        for i in s.cal:
            print(f'  {i:40s} {s.cal[i]}')
        print('Working path:')
        print(f'  {s.working_path}')
        print('Settings:')
        st = s.make_json()
        for i in st:
            print(f'  {i:40s} {st[i]}')


 

if __name__ == '__main__':
    s = Settings()
    s.show_settings()



default_settings = '''
{
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
    "time_display_index": 6,
    "voltage_display_ranges": [
        50,
        100,
        200,
        500,
        1000
    ],
    "voltage_display_index": 3,
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
        2.0,
        5.0
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
        500.0,
        1000.0
    ],
    "power_display_index": 8,
    "power_display_status": false,
    "earth_leakage_current_display_ranges": [
        0.0001,
        0.0002,
        0.0005,
        0.001,
        0.002,
        0.005,
        0.01,
        0.02
    ],
    "earth_leakage_current_display_index": 7,
    "earth_leakage_current_display_status": false,
    "scale_factors": [
        -4.07e-07,
        2.44e-05,
        0.00122,
        0.0489
    ],
    "trigger_channel": 0,
    "trigger_slope": "rising",
    "trigger_level": 0.0,
    "trigger_position": 5,
    "trigger_mode": "sync"
}
'''


