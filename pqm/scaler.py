#!/usr/bin/env python3


#                _                       
#  ___  ___ __ _| | ___ _ __ _ __  _   _ 
# / __|/ __/ _` | |/ _ \ '__| '_ \| | | |
# \__ \ (_| (_| | |  __/ | _| |_) | |_| |
# |___/\___\__,_|_|\___|_|(_) .__/ \__, |
#                           |_|    |___/ 
# 
# Convert incoming integer samples to floating point and apply scaling factors 

import sys
import signal

# local
from settings import Settings


def from_twos_complement(v):
    return -(v & 0x8000) | (v & 0x7fff)

def get_factors(run_calibrated=True):
    global st, offsets, gains
    if run_calibrated == True:
        offsets = st.cal_offsets
        gains   = [ s*g for s,g in zip(st.scale_factors, st.cal_gains) ]
    # we support running in 'uncalibrated' mode when we want to calibrate the device
    else:
        offsets = [0, 0, 0, 0]
        gains   = st.scale_factors
   

def scale_readings(cs):
    """cs contains channel readings in integers"""
    global offsets, gains
    return [ (from_twos_complement(cs[i]) + offsets[i]) * gains[i] for i in [0,1,2,3] ]


def main():
    global st

    # check for uncalibrated mode
    if len(sys.argv) == 2 and sys.argv[1] == '--uncalibrated':
        run_calibrated = False
    else:
        run_calibrated = True

    # NB get_factors() function will be called automatically when settings are changed
    st = Settings(lambda run_calibrated=run_calibrated: get_factors(run_calibrated))
    i = 0   # sample index
    get_factors(run_calibrated)

    # now loop over all the lines of data from stdin
    for line in sys.stdin:
        line = line.rstrip()
        try:
            # calculate time axis position
            t = st.interval*i
            # split channel values into an integer array, removing the index field
            cs = [ int(w.strip(), base=16) for w in line.split() ][1:]
            # scale the readings
            scaled = scale_readings(cs)
            # calculate floating point values, with appropriate calibration factors
            voltage = scaled[3]
            # if st.current_axis_per_division is less than or equal to 0.1 A/div,
            # we use channel 1 for current measurements. If it is more than 0.1 A/div,
            # we use channel 2.
            if st.current_sensor == 'low':
                current = scaled[1]
            else:
                current = scaled[2]
            power = voltage * current
            leakage_current = scaled[0]
            print(f'{t:12.4f} {voltage:10.3f} {current:10.5f} {power:10.3f} {leakage_current:12.7f}')
            i = i + 1

        except ValueError:
            print(f'scaler.py, main(): Failed to read "{line}".', file=sys.stderr)


if __name__ == '__main__':
    main()


