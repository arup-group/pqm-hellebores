#!/usr/bin/env python3

import subprocess
import settings
import sys
import os
import math

# local
from settings import Settings


ONE_MINUTE_OF_SAMPLES     = 468750
READER                    = 'reader.py'
READER_TEST               = 'rain_chooser.py'    # use this for testing
HARDWARE_SCALE_FACTORS    = [ 4.07e-07, 2.44e-05, 0.00122, 0.0489 ]
OFFSET_CAL                = 1
VOLTAGE_CAL               = 2
CURRENT_FULL_CAL          = 3
CURRENT_LOW_CAL           = 4
CURRENT_EARTHLEAKAGE_CAL  = 5

def is_raspberry_pi():
    is_pi = False
    try:
        with open('/sys/firmware/devicetree/base/model', 'r') as model:
            if 'raspberry' in model.read().lower():
                is_pi = True
    except (FileNotFoundError, IOError):
        pass
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


def scaled(config, samples):
    scaled_samples = []
    for ns in samples:
        scaled_samples.append([ h*g*(n+o) for h,g,o,n in zip(config['scaling'], config['gains'], config['offsets'], ns) ])
    return scaled_samples


def samples_to_rms(config, samples):
    number_of_samples = len(samples)
    scaled_samples = scaled(config, samples)
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
    print('''

******   CALIBRATOR UTILITY   *******
The scaling transformations between ADC channels and output measurements are as
follows:
    m0 = (adc0 + O0) * H0 * G0
    m1 = (adc1 + O1) * H1 * G1
    m2 = (adc2 + O2) * H2 * G2
    m3 = (adc3 + O3) * H3 * G3

If 'n' is the channel number, then:
    mn    is the scaled measurement reading (eg Amps or Volts)
    adcn  is the raw ADC channel reading (expressed as a signed integer)
    On    is a device-specific dc calibration offset
    Hn    is a hardware scaling factor, fixed in the design
    Gn    is a device-specific gain calibration factor.

This program helps to determine the device specific calibration constants On and Gn.

Proceed to calibrate with each of the following procedures, in turn. It is essential
that offset calibration is completed first.

Select option, or 'q' to quit:
1. O0, O1, O2, O3 offset calibration
2. G3 voltage calibration
3. G2 current (full range) calibration
4. G1 current (low range) calibration
5. G0 current (earth leakage) calibration

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
    samples = lines_to_samples(get_lines_from_reader(ONE_MINUTE_OF_SAMPLES))
    # offset report
    labels = ['o0: Earth leakage current', 'o1: Current (low)', 'o2: Current (full)', 'o3: Voltage']
    print('OFFSET VALUES:')
    print('-'*80)
    print('Channel                      :       Existing :     Calculated :')
    print('                             :         offset :         offset :')
    print('                             :          value :          value :')
    print('                             :             oc :             oc :')
    print('-'*80)
    results = [ f'{l:28} : {o:14} : {co:14} :     adc counts' for l,o,co in zip(labels, c_config['offsets'], u_config['offsets']) ]
    print('\n'.join(results))
    print('-'*80)
    print()


def print_results(c_config, u_config, c_measurements, u_measurements):
    # measurement report
    labels = ['r0: Earth leakage current', 'r1: Current (low)', 'r2: Current (full)', 'r3: Voltage']
    units = ['mA', 'A', 'A', 'V']
    # for convenience, convert channel 0 into mA
    c_measurements[0] = c_measurements[0] * 1000
    u_measurements[0] = u_measurements[0] * 1000
    print('GAIN FACTORS:')
    print('-'*80)
    print('Channel                      :       Existing :    Measurement :    Measurement')
    print('                             :           gain :        #1 with :        #2 with')
    print('                             :         factor :       existing :     calculated')
    print('                             :             gc :         oc and :         oc and')
    print('                             :                :             gc :         gc = 1')
    print('-'*80)
    results = [ f'{l:28} : {g:14} : {m1:11.4f} {u:2} : {m2:11.4f} {u:2}' for l,g,m1,m2,u in zip(labels, c_config['gains'], c_measurements, u_measurements, units) ]
    print('\n'.join(results))
    print('-'*80)
    print('NB New calibration constant gc = multimeter reading/measurement #2')
    print()


def calibrate(samples):
    st = Settings()
    c_config = {
        'offsets': st.cal_offsets,
        'gains': st.cal_gains,
        'scaling': HARDWARE_SCALE_FACTORS
    }
    u_config = {
        'offsets': samples_to_offsets(samples),
        'gains': [1,1,1,1],
        'scaling': c_config['scaling']
    }
    # calculate the rms values of the samples, with both calibrated and uncalibrated configuration
    c_measurements = samples_to_rms(c_config, samples)
    u_measurements = samples_to_rms(u_config, samples)
    return(c_config, u_config, c_measurements, u_measurements)


def main():
    index = get_choice() - 1
    calibration_functions = [ offset_calibration, voltage_calibration, \
                              current_full_calibration, current_low_calibration, \
                              current_earthleakage_calibration ]
    calibration_functions[index]()


if __name__ == '__main__':
    main() 
