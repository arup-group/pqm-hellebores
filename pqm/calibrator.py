#!/usr/bin/env python3

import subprocess
import sys
import os
import math
import json
import re
import select

# local
from constants import *
from settings import Settings


ONE_MINUTE_OF_SAMPLES     = 468750
TWO_SECONDS_OF_SAMPLES    = 15625
TEN_SECONDS_OF_SAMPLES    = 78125
DISCARD_SAMPLES           = 5000
READER                    = 'reader.py'
READER_TEST               = 'rain_chooser.py'    # use this for testing
WIP_FILE                  = 'calibrator_wip.json'



class WIP:
    """work-in-progress calibration constants for channels 0-3.
    These local constants are cached in a file so that they can be accessed
    during successive runs of calibrator.py"""
    offsets = [ 0, 0, 0, 0 ]
    gains = [ 1.0, 1.0, 1.0, 1.0 ]
    skew_times = [ 0.0, 0.0, 0.0, 0.0 ]
    identity = 'PQM-0'

    def __init__(self):
        st = Settings()
        self.offsets = st.cal_offsets
        self.gains = st.cal_gains
        self.skew_times = st.cal_skew_times
        self.identity = st.identity
        self.read()

    def write(self):
        try:
            with open(WIP_FILE, 'w') as f:
                f.write(json.dumps({'offsets':self.offsets, 'gains':self.gains,
                    'skew_times':self.skew_times}))
                f.write('\n')
            print(f"calibrator.py: work-in-progress file {WIP_FILE} written.")
        except:
            print(f"calibrator.py, WIP.write(): Couldn't write "
                f"to cache file {WIP_FILE}.", file=sys.stderr)

    def read(self):
        status = False
        try:
            with open(WIP_FILE, 'r') as f:
                wip_file = json.loads(f.read())
                self.offsets, self.gains, self.skew_times = wip_file.values()
            status = True
        except:
            print(f"calibrator.py: no work-in-progress found.")
        return status

    def set(self, channel, text):
        try:
            value = float(text)
            # keep the setting truncated to 3dp
            self.gains[channel] = round(value * 1000) / 1000.0
        except ValueError:
            print(f"calibrator.py, WIP.set(): Value entered wasn't recognised.", file=sys.stderr)


def is_raspberry_pi():
    try:
        with open('/sys/firmware/devicetree/base/model', 'r') as model:
            is_pi = True if 'raspberry' in model.read().lower() else False
    except (FileNotFoundError, IOError):
        is_pi = False
    return is_pi


def resolve_path(path, file):
    file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), path, file)
    return os.path.abspath(file_path)


def get_reading_from_multimeter_pipe(fd):
    f = os.fdopen(fd)
    # only read data if there is something waiting
    if select.select( [f], [], [], 0)[0] != []:
        return f.readline()
    else:
        return None


def get_lines_from_reader(number_of_lines):
    """Retrieves a specific number of sample lines from the reader program, which is
    run as a sub-process."""
    pyth = sys.executable
    if is_raspberry_pi():
        reader = resolve_path('.', READER)
    else:
        reader = resolve_path('.', READER_TEST)
    # receive the measurements
    try:
        process = subprocess.Popen(f'{pyth} {reader}',
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL,
                                   shell=True)
        # discard some lines to clear pipeline buffers
        for i in range(DISCARD_SAMPLES):
            process.stdout.readline()
        # read the correct number of lines
        lines = []
        for i in range(number_of_lines):
            if i % 2000 == 0:
                sys.stdout.write('-')
                sys.stdout.flush()
            line = process.stdout.readline()
            # check if readline() returned empty bytestring: indicates subprocess terminated
            if line == b'':
                print('')   
                raise EOFError
            else:
                lines.append(line)
        sys.stdout.write('>')
    except EOFError:
        print(f'{os.path.basename(__file__)}, get_lines_from_reader(): Reader program terminated.', file=sys.stderr)
        raise ValueError    # bump the error to caller, we need to exit.
    finally:
        process.terminate()
    return lines


def lines_to_samples(lines):
    """Converts from two's complement hex words to real number integer values"""
    def from_twos_complement(v):
        return -(v & 0x8000) | (v & 0x7fff)

    def line_to_sample(line):
        ws = line.decode('utf-8').strip().split()
        sample = [ from_twos_complement(int(w, base=16)) for w in ws ]
        return sample

    # samples is a list containing lists of 4 numbers (sample per channel in numeric form)
    samples = [ line_to_sample(line) for line in lines ]
    return samples 


def scaled(wip, samples):
    """Applies work-in-progress calibration constants to an array of samples."""
    scaled_samples = []
    for vs in samples:
        # The sample values in each line are first zipped into tuples with the appropriate
        # calibration contants and then an adjusted value calculated
        scaled_samples.append([ h*g*(v+o) for h,g,o,v
            in zip(HARDWARE_SCALE_FACTORS, wip.gains, wip.offsets, vs) ])
    return scaled_samples


def samples_to_rms(wip, samples):
    """Using a work-in-progress calibration object and list of samples, determines the RMS
    amplitude of the samples for each channel."""
    number_of_samples = len(samples)
    scaled_samples = scaled(wip, samples)
    sum_of_squares = [0,0,0,0]
    for ns in scaled_samples:
        sum_of_squares = [ n*n + s for n,s in zip(ns, sum_of_squares) ] 
    mean_squares = [ n/number_of_samples for n in sum_of_squares ]
    rmses = [ math.sqrt(n) for n in mean_squares ]
    return rmses


def samples_to_offsets(samples):
    """From an array of samples, calculates the average dc value and corrective offset
    required for the sum to be zero."""
    number_of_samples = len(samples)
    accumulators = [0,0,0,0]
    for ns in samples:
        accumulators = [ a+n for a,n in zip(accumulators, ns) ]
    offsets = [ round(-acc/number_of_samples) for acc in accumulators ]
    return offsets


def get_choice(wip):
    print(f'''

******   CALIBRATOR UTILITY   *******
If N is the channel number, the transformation between ADC channel
reading and measurement is as follows:
    mN = (adcN + ON) * HN * GN

where:
    mN    is the scaled measurement reading (eg Amps or Volts)
    adcN  is the raw ADC channel reading (expressed as a signed integer)
    ON    is a device-specific dc calibration offset
    HN    is a hardware scaling factor
    GN    is a device-specific gain calibration factor.

The hardware scale factors H[0-3] are fixed in the hardware design.
This program helps to determine the device specific calibration constants
O[0-3] and G[0-3].

Currently configured settings are:
Device identity: {wip.identity}
O[0-3]:          {wip.offsets}
H[0-3]:          {HARDWARE_SCALE_FACTORS}
G[0-3]:          {wip.gains}

Proceed with the calibration in sequence starting with dc offset
calibration.

VERIFY THE SETTINGS THAT YOU SEE ABOVE.

Select option, or 'q' to quit:
1. O3, O2, O1, O0 dc offset calibration
2. G3 voltage gain calibration
3. G2 current (full range) gain calibration
4. G1 current (low range) gain calibration
5. G0 current (earth leakage) gain calibration

''', end='')

    try:
        choice = int(input())
        if choice < 1 or choice > 5:
            raise ValueError
    except ValueError:
        print('Quitting.')
        sys.exit(0)
    return choice


def offset_calibration(wip):
    # offset report
    input(f'Offsets O[0-3] = {wip.offsets}. Press Enter to start.')
    samples = lines_to_samples(get_lines_from_reader(ONE_MINUTE_OF_SAMPLES))
    wip.offsets = samples_to_offsets(samples)
    print(f' New calculated offsets O[0-3] = {wip.offsets}')

def gain_calibration(wip, channel):
    input(f'O{channel} = {wip.offsets[channel]}, G{channel} = {wip.gains[channel]}. Press Enter to start.')
    while 1:
        print(f'O{channel} = {wip.offsets[channel]}, G{channel} = {wip.gains[channel]}: ', end='')
        samples = lines_to_samples(get_lines_from_reader(TEN_SECONDS_OF_SAMPLES))
        rmses = samples_to_rms(wip, samples)
        print(f' Adjusted reading = {rmses[channel]:5g}')
        choice = input(f"Enter a new value for G{channel} (empty to repeat) or 'q' to quit. ")
        if choice == 'q':
            break
        elif re.match(r'^[0-9]+\.[0-9]*$', choice):
            wip.set(channel, choice)

def voltage_calibration(wip):
    gain_calibration(wip, 3)

def current_full_calibration(wip):
    gain_calibration(wip, 2)

def current_low_calibration(wip):
    gain_calibration(wip, 1)

def current_earthleakage_calibration(wip):
    gain_calibration(wip, 0)


def main():
    wip = WIP()
    index = get_choice(wip) - 1
    calibration_functions = [ offset_calibration, voltage_calibration, \
                              current_full_calibration, current_low_calibration, \
                              current_earthleakage_calibration ]
    calibration_functions[index](wip)
    wip.write()
    print("When you are done with calibrating, transfer the values in calibrator_wip.json to "
          "configuration/calibrations.json and commit to repository.")

if __name__ == '__main__':
    main() 
