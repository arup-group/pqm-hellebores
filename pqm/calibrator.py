#!/usr/bin/env python3

import subprocess
import settings
import sys


READINGS=10
ADC_SAMPLES = 78125

def from_twos_complement(v):
    return -(v & 0x8000) | (v & 0x7fff)

def average_offsets():
    print('')
    print('******      Offset calibration        *******')
    print('ADC integer readings will be received from all channels')
    print('and averaged over 10 seconds.')
    print('ENSURE NO LOADS ARE CONNECTED TO THE METER.')
    print('')
    print('Enter to start, (q) to quit: ', end='')
    choice = input() 
    if choice == 'q':
        return
    print('Receiving', end='')
    # receive the measurements
    process = subprocess.Popen('./rain_chooser.py',
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

    # now average the offsets
    accumulators = [0,0,0,0]
    for l in lines:
        output_words = l.decode('utf-8').strip().split()
        output_numbers = [ from_twos_complement(int(w, base=16)) for w in output_words[1:] ] 
        # print(output_numbers)
        accumulators = [ a+n for a,n in zip(accumulators, output_numbers) ]
    averages = [ round(-n/ADC_SAMPLES) for n in accumulators ]
    labels = ['o0: Earth leakage current', 'o1: Current (low)', 'o2: Current (full)', 'o3: Voltage']
    units = ['adc counts', 'adc counts', 'adc counts', 'adc counts']

    # present the results
    print('Required offset calibration:')
    results = [ f'{l:28} : {a:12} {u}' for l,a,u in zip(labels, averages, units) ]
    print('\n'.join(results))
    print()





def average_amplitudes():
    print('')
    print('******       Gain calibration         *******')
    print('RMS calculated measurements will be received from all channels')
    print('and averaged over 10 seconds.')
    print('CONNECT THE APPROPRIATE LOAD TO THE PQM AND A CALIBRATED COMPARISON METER.')
    print('')
    print('Enter to start, or (q) to quit: ', end='')
    choice = input() 
    if choice == 'q':
        return
    print('Receiving', end='')
    # receive the measurements
    process = subprocess.Popen('./rain_chooser.py | ./scaler.py --uncalibrated | ./analyser.py',
                               stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL,
                               shell=True)
    accumulators = [0,0,0,0]
    for i in range(READINGS):
        output_words = process.stdout.readline().decode('utf-8').strip().split()
        output_numbers = [ float(w) for w in output_words[1:] ] 
        accumulators = [ a+n for a,n in zip(accumulators, output_numbers) ]
        sys.stdout.write('.')
        sys.stdout.flush()
    process.terminate()
    print('done.\n')
    # calculate the average for each channel
    averages = [ n/READINGS for n in accumulators ]
    averages[0] = averages[0]*1000  # for convenience, convert leakage current to mA
    labels = ['r0: Earth leakage current', 'r1: Current (low)', 'r2: Current (full)', 'r3: Voltage']
    units = ['mA', 'A', 'A', 'V']
    # present the results
    print('Results:')
    results = [ f'{l:28} : {a:28} {u}' for l,a,u in zip(labels, averages, units) ]
    print('\n'.join(results))
    print()
    print('To determine the gain calibration')
    print('factor, divide the average multimeter reading by the measurement')
    print('result above, eg g0 = m0/r0.')
    print()



if __name__ == '__main__':
    print('****** Power quality meter calibrator *******')
    print('(o) offset calibration, (g) gain calibration, (q) to quit: ', end='')
    choice = input()
    if choice == 'o':
        average_offsets()
    elif choice == 'g':
        average_amplitudes()
    else:
        pass 



