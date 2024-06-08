#!/usr/bin/env python3

import subprocess
import settings
import sys
import os
import math

# local
from settings import Settings


ADC_SAMPLES = 78125
READER      = 'reader.py'
READER_TEST = 'rain_chooser.py'    # use this for testing


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
            if i % 1000 == 0:
                sys.stdout.write('.')
                sys.stdout.flush()
            line = process.stdout.readline()
            # check if readline() returned empty bytestring: indicates subprocess terminated
            if line == b'':
                print('')   
                raise EOFError
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
        sample = [ from_twos_complement(int(w, base=16)) for w in ws[1:] ]  
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


def ready_to_proceed():
    print('''

******   CALIBRATOR UTILITY   *******
The power quality monitor takes raw readings from the ADC channels and then passes them
through a scaling process. The scaling transformations between ADC channels and output
measurements are as follows:
    r0 = (adc0 + o0) * h0 * g0
    r1 = (adc1 + o1) * h1 * g1
    r2 = (adc2 + o2) * h2 * g2
    r3 = (adc3 + o3) * h3 * g3

If 'c' is the channel number, then:
    rc    is the scaled analogue channel reading (eg Amps or Volts)
    adcc  is the raw ADC channel reading (expressed as a signed integer)
    oc    is a device-specific dc calibration offset
    hc    is a hardware scaling factor, fixed in the design
    gc    is a device-specific gain calibration factor.

This calibration program helps to determine the oc and gc calibration constants that are
specific to each individual device.

Connect no load or a fixed load with external multimeter to correspond with the channel
that you want to calibrate.

Offset calibration values are automatically calculated, and assume that your test supply
and load have no DC currents (use an isolation transformer).

Gain calibration factors are calculated by hand using the multimeter and program output.

ADC integer readings will now be received from all channels and collected over a period
of 10 seconds.

NB CHANNEL 1 CALIBRATION RESULTS ARE ONLY VALID FOR CURRENTS UP TO APPROX 0.5A.
Enter to start, (q) to quit: ''', end='')
    choice = input() 
    if choice == 'q':
        return False
    else:
        return True


def print_results(c_config, u_config, c_measurements, u_measurements):
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
        'scaling': st.scale_factors
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
    if ready_to_proceed():
        samples = lines_to_samples(get_lines_from_reader(ADC_SAMPLES))
        print_results(*calibrate(samples))


if __name__ == '__main__':
    main() 
