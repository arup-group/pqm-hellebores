#!/usr/bin/env python3

import sys
import os
import signal
import json
import psutil
import time
import glob

SETTINGS_FILE = 'settings.json'        # NB settings file is later cached in /tmp
IDENTITIES_FILE = 'identities.json'
CALIBRATIONS_FILE = 'calibrations.json'


class Settings():

    def get_mac_address(self):
        try:
            # note, we search for the mac address of the first wireless network
            # interface (which begins with 'w').
            with open(glob.glob('/sys/class/net/w*/address')[0], 'r') as f:
                mac = f.readline().strip()
        except:
            print('settings.py: using default MAC address', file=sys.stderr)
            mac = '00:00:00:00:00:00'
        return mac

    def get_identity(self, mac):
        try:
            with open(IDENTITIES_FILE, 'r') as f:
                js = json.loads(f.read())
                identity = js[mac]
        except:
            print('settings.py: using default identity', file=sys.stderr)
            identity = 'PQM-9999'
        return identity

    def get_calibration(self, identity):
        try:
            with open(CALIBRATIONS_FILE, 'r') as f:
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
        self.adc_offset_trim_c0                        = cal['offsets'][0]
        self.adc_offset_trim_c1                        = cal['offsets'][1]
        self.adc_offset_trim_c2                        = cal['offsets'][2]
        self.adc_offset_trim_c3                        = cal['offsets'][3]
        self.adc_gain_trim_c0                          = cal['gains'][0]
        self.adc_gain_trim_c1                          = cal['gains'][1]
        self.adc_gain_trim_c2                          = cal['gains'][2]
        self.adc_gain_trim_c3                          = cal['gains'][3]
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
            with open(self.sfile, 'r') as f:
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
            with open(self.sfile, 'w') as f:
                f.write(json.dumps(self.make_json(), indent=4))
        except:
            print(
                "settings.py, save_settings(): couldn't write settings.json.",
                file=sys.stderr)


    def signal_handler(self, signum, frame):
        self.set_settings(self.load_settings(), self.cal)
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


    def __init__(self, callback_fn = lambda: None, other_programs=[]):
        # establish MAC address, identity and calibration factors
        self.mac = self.get_mac_address()
        self.identity = self.get_identity(self.mac)
        self.cal = self.get_calibration(self.identity)

        # load initial settings
        self.sfile = SETTINGS_FILE
        self.set_settings(self.load_settings(), self.cal)

        # set a callback function if provided. This will be called
        # every time a signal is received just after settings have been updated
        self.callback_fn = callback_fn

        # if we receive 'SIGUSR1' signal (on linux/unix) set things up so that updated settings will
        # be read from settings.json via the signal_handler function
        if os.name == 'posix':
            # for faster update performance, and to reduce SD card wear, if TEMP_DIR is set to RAM disk,
            # we'll save updates to the settings.json file there.
            temp_dir = os.getenv('TEMP_DIR')
            if temp_dir:
                self.sfile = f'{temp_dir}/{self.sfile}'
                self.save_settings()
            self.pids = self.get_program_pids(other_programs)
            # link to the send_to_all function and set up a signal handler
            self.send_to_all = self._send_to_all
            signal.signal(signal.SIGUSR1, self.signal_handler)
        else: 
            self.send_to_all = \
                lambda: print(
                    f"settings.py: send_to_all() function hasn't been implemented on {sys.platform}.",
                    file=sys.stderr)


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
    "scale_c0": -4.07e-07,
    "scale_c1": 2.44e-05,
    "scale_c2": 0.00122,
    "scale_c3": 0.0489,
    "trigger_channel": 0,
    "trigger_slope": "rising",
    "trigger_level": 0.0,
    "trigger_position": 5,
    "trigger_mode": "sync"
}
'''


