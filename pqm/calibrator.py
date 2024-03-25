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
    try:
        with open('/sys/firmware/devicetree/base/model', 'r') as model:
            if 'raspberry' in model.read().lower():
                return True
    except Exception:
        pass
    return False


def resolve_path(path, file):
    file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), path, file)
    resolved_path = os.path.abspath(file_path)
    return resolved_path


def from_twos_complement(v):
    return -(v & 0x8000) | (v & 0x7fff)


def get_lines_from_reader():
    pyth = sys.executable
    if is_raspberry_pi():
        reader = resolve_path('.', READER)
    else:
        reader = resolve_path('.', READER_TEST)


    print('Receiving', end='')
    # receive the measurements
    process = subprocess.Popen(f'{pyth} {reader}',
                               stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL,
                               shell=True)

    # read some dummy lines, to get beyond pygame library startup lines
    for i in range(5):
        process.stdout.readline()
    # read the correct number of lines
    lines = []
    for i in range(ADC_SAMPLES):
        if i % 1000 == 0:
            sys.stdout.write('.')
            sys.stdout.flush()
        lines.append(process.stdout.readline())    
    process.terminate()
    print(f' {len(lines)} samples, done.\n')
    return lines


def lines_to_numbers(lines):
    def line_to_numbers(line):
        ws = line.decode('utf-8').strip().split()
        ns = [ from_twos_complement(int(w, base=16)) for w in ws[1:] ]  
        return ns

    # numbers is a list of 4-tuples (sample per channel in numeric form)
    numbers = [ line_to_numbers(line) for line in lines ]
    return numbers 


def scaled(numbers, offsets):
    global st
    scaled_numbers = []
    for ns in numbers:
        scaled_numbers.append([ sf*(n+o) for sf,n,o in zip(st.scale_factors, ns, offsets) ])
    return scaled_numbers


def numbers_to_rms(numbers, offsets):
    scaled_numbers = scaled(numbers, offsets)
    sum_of_squares = [0,0,0,0]
    for ns in scaled_numbers:
        sum_of_squares = [ n*n + s for n,s in zip(ns, sum_of_squares) ] 
    mean_squares = [ n/ADC_SAMPLES for n in sum_of_squares ]
    rmses = [ math.sqrt(n) for n in mean_squares ]
    return rmses


def numbers_to_offsets(numbers):
    accumulators = [0,0,0,0]
    for ns in numbers:
        accumulators = [ a+n for a,n in zip(accumulators, ns) ]
    offsets = [ round(-n/ADC_SAMPLES) for n in accumulators ]
    return offsets


def calibrate():
    print('')
    print('******   CALIBRATOR UTILITY   *******')
    print('ADC integer readings will be received from all channels')
    print('and collected over 10 seconds.')
    print('')
    print('Enter to start, (q) to quit: ', end='')
    choice = input() 
    if choice == 'q':
        return
    numbers = lines_to_numbers(get_lines_from_reader())
    # now average the offsets
    offsets = numbers_to_offsets(numbers)
    # calculate the rms values, applying necessary offsets
    measurements = numbers_to_rms(numbers, offsets)
    # for convenience, convert channel 0 into mA
    measurements[0] = measurements[0] * 1000

    # present the results
    labels = ['o0: Earth leakage current', 'o1: Current (low)', 'o2: Current (full)', 'o3: Voltage']
    units = ['adc counts', 'adc counts', 'adc counts', 'adc counts']
    
    print('NB CHANNEL 1 CALIBRATION RESULTS ARE ONLY VALID FOR CURRENTS UP TO APPROX 0.5A')
    print('Required offset calibration:')
    results = [ f'{l:28} : {a:6} {u}' for l,a,u in zip(labels, offsets, units) ]
    print('\n'.join(results))
    print()
    labels = ['r0: Earth leakage current', 'r1: Current (low)', 'r2: Current (full)', 'r3: Voltage']
    units = ['mA', 'A', 'A', 'V']
    g_factor = ['g0=multimeter/r0', 'g1=multimeter/r1', 'g2=multimeter/r2', 'g3=multimeter/r3']
    print('Uncalibrated meter readings, with offsets applied:')
    results = [ f'{l:28} : {a:12.4f} {u:4} :    {g}' for l,a,u,g in zip(labels, measurements, units, g_factor) ]
    print('\n'.join(results))
    print()


if __name__ == '__main__':
    global st
    st = Settings()
    calibrate()



