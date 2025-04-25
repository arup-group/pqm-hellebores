#!/usr/bin/env python3

import subprocess
import sys
import os
import math

# local
from constants import *
from settings import Settings


ONE_MINUTE_OF_SAMPLES     = 468750
TWO_SECONDS_OF_SAMPLES    = 15625
READER                    = 'reader.py'
READER_TEST               = 'rain_chooser.py'    # use this for testing

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


def get_lines_from_reader(number_of_lines):
    pyth = sys.executable
    if is_raspberry_pi():
        reader = resolve_path('.', READER)
    else:
        reader = resolve_path('.', READER_TEST)
    print('Receiving', end='')
    # receive the measurements
    try:
        process = subprocess.Popen(f'{pyth} {reader}',
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL,
                                   shell=True)
        # read some dummy lines, to get beyond pygame library startup lines
        for i in range(5):
            process.stdout.readline()
        # read the correct number of lines
        lines = []
        for i in range(number_of_lines):
            if i % 2000 == 0:
                sys.stdout.write('.')
                sys.stdout.flush()
            line = process.stdout.readline()
            # check if readline() returned empty bytestring: indicates subprocess terminated
            if line == b'':
                print('')   
                raise EOFError
            else:
                lines.append(line)
        print(f' {len(lines)} samples, done.\n')
    except EOFError:
        print(f'{os.path.basename(__file__)}, get_lines_from_reader(): Reader program terminated.', file=sys.stderr)
        raise ValueError    # bump the error to caller, we need to exit.
    finally:
        process.terminate()
    return lines


def lines_to_samples(lines):

    def from_twos_complement(v):
        return -(v & 0x8000) | (v & 0x7fff)

    def line_to_sample(line):
        ws = line.decode('utf-8').strip().split()
        sample = [ from_twos_complement(int(w, base=16)) for w in ws ]
        return sample

    # samples is a list containing lists of 4 numbers (sample per channel in numeric form)
    samples = [ line_to_sample(line) for line in lines ]
    return samples 


def scaled(samples):
    scaled_samples = []
    for ns in samples:
        scaled_samples.append([ h*g*(n+o) for h,g,o,n
            in zip(HARDWARE_SCALE_FACTORS, st.cal_gains, st.cal_offsets, ns) ])
    return scaled_samples


def samples_to_rms(samples):
    number_of_samples = len(samples)
    scaled_samples = scaled(samples)
    sum_of_squares = [0,0,0,0]
    for ns in scaled_samples:
        sum_of_squares = [ n*n + s for n,s in zip(ns, sum_of_squares) ] 
    mean_squares = [ n/number_of_samples for n in sum_of_squares ]
    rmses = [ math.sqrt(n) for n in mean_squares ]
    return rmses


def samples_to_offsets(samples):
    number_of_samples = len(samples)
    accumulators = [0,0,0,0]
    for ns in samples:
        accumulators = [ a+n for a,n in zip(accumulators, ns) ]
    offsets = [ round(-n/number_of_samples) for n in accumulators ]
    return offsets


def get_choice():
    print(f'''

******   CALIBRATOR UTILITY   *******
The scaling transformations between ADC channels and output measurements are as
follows:
    m0 = (adc0 + O0) * H0 * G0
    m1 = (adc1 + O1) * H1 * G1
    m2 = (adc2 + O2) * H2 * G2
    m3 = (adc3 + O3) * H3 * G3

If 'N' is the channel number, then:
    mN    is the scaled measurement reading (eg Amps or Volts)
    adcN  is the raw ADC channel reading (expressed as a signed integer)
    ON    is a device-specific dc calibration offset
    HN    is a hardware scaling factor, fixed in the design
    GN    is a device-specific gain calibration factor.

The hardware scale factors H[0-3] are {HARDWARE_SCALE_FACTORS}.
This program helps to determine the device specific calibration constants
O[0-3] and G[0-3].

Currently configured settings are:
Device identity: {st.identity}
O[0-3]:          {st.cal_offsets}
H[0-3]:          {HARDWARE_SCALE_FACTORS}
G[0-3]:          {st.cal_gains}

Proceed with the calibration in the following sequence: it is essential
that offset calibration is completed first and entered into calibration.json
before proceeding to determine any gain calibration.

VERIFY THE SETTINGS THAT YOU SEE ABOVE.

Select option, or 'q' to quit:
1. O0, O1, O2, O3 dc offset calibration
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


def offset_calibration():
    # offset report
    samples = lines_to_samples(get_lines_from_reader(ONE_MINUTE_OF_SAMPLES))
    offsets = samples_to_offsets(samples)
    print(f'Calculated O[0-3] = {offsets}')

def voltage_calibration():
    while 1:
        choice = input("'h' to increase, 'l' to lower, 'Enter' to repeat, 'q' to quit. ")
        if choice == 'q':
            break
        samples = lines_to_samples(get_lines_from_reader(TWO_SECONDS_OF_SAMPLES))
        rmses = samples_to_rms(samples)
        print(f'Voltage with O3 = {st.cal_offsets[3]}, G3 = {st.cal_gains[3]}: {rmses[3]}')

def current_full_calibration():
    pass

def current_low_calibration():
    pass

def current_earthleakage_calibration():
    pass


def main():
    global st
    st = Settings()
    index = get_choice() - 1
    calibration_functions = [ offset_calibration, voltage_calibration, \
                              current_full_calibration, current_low_calibration, \
                              current_earthleakage_calibration ]
    calibration_functions[index]()


if __name__ == '__main__':
    main() 
