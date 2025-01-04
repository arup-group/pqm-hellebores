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


DELAY_LINE_LENGTH = 64

def from_twos_complement_hex(w):
    v = int(w, base=16)
    return -(v & 0x8000) | (v & 0x7fff)

def set_current_channel():
    global current_channel
    if st.current_sensor == 'low':
        current_channel = 1
    else:
        current_channel = 2

def set_uncalibrated_constants():
    global offsets, gains, delays
    offsets = [0, 0, 0, 0]
    gains   = st.scale_factors
    delays  = [-1, -1, -1, -1]

def set_calibrated_constants():
    global offsets, gains, delays
    try:
        offsets = st.cal_offsets
        gains   = [ s*g for s,g in zip(st.scale_factors, st.cal_gains) ]
        delays  = []
        for skew_time in st.cal_skew_times:
            delay_shift = int(-1 - skew_time // st.interval)
            # catch conditions where the requested delay is outside of the range of the delay line
            if delay_shift < -(DELAY_LINE_LENGTH-1) or delay_shift > -1:
                raise ValueError
            delays.append(delay_shift)
    except (NameError, ZeroDivisionError, TypeError, ValueError):
        print('scaler.py, get_factors(): Error in setting calibration constants, '
              'switching to uncalibrated.', file=sys.stderr)
        set_uncalibrated_constants()

def scale_readings(cs):
    """cs contains channel readings in integers"""
    global offsets, gains
    #return [ (cs + o) * g for cs, o, g in zip(cs, offsets, gains) ]
    return [ (cs[i] + offsets[i]) * gains[i] for i in [0,1,2,3] ]


def main():
    global st

    # check for uncalibrated mode
    if len(sys.argv) == 2 and sys.argv[1] == '--uncalibrated':
        run_calibrated = False
    else:
        run_calibrated = True

    # NB set_current_channel() function will be called automatically when
    # settings are changed
    st = Settings(lambda: set_current_channel())

    # the delay line allows timing skew between channels to be corrected
    delay_line = [ [0, 0, 0, 0] for i in range(DELAY_LINE_LENGTH) ]

    i = 0   # sample index
    set_current_channel()
    set_calibrated_constants() if run_calibrated else set_uncalibrated_constants()
    # delay_lookup contains the appropriate array offsets for delay in each channel
    delay_lookup = list(zip([0,1,2,3], delays))

    # now loop over all the lines of data from stdin
    for line in sys.stdin:
        line = line.rstrip()
        try:
            # calculate time axis position
            t = st.interval*i
            # split channel values into an integer array, removing the index field
            new_sample = [ from_twos_complement_hex(w) for w in line.split()[1:] ]
            delay_line = delay_line[1:]
            delay_line.append(new_sample)
            # use the delay line to correct for channel timing skew
            # and apply calibration and scale factors to readings
            scaled = scale_readings([ delay_line[delay][ch] for (ch, delay) in delay_lookup ])
            # now pick out the individual readings ready for output
            voltage = scaled[3]
            # if st.current_axis_per_division is less than or equal to 0.1 A/div,
            # we use channel 1 for current measurements. If it is more than 0.1 A/div,
            # we use channel 2.
            current = scaled[current_channel]
            power = voltage * current
            leakage_current = scaled[0]
            print(f'{t:12.4f} {voltage:10.3f} {current:10.5f} {power:10.3f} {leakage_current:12.7f}')
            i = i + 1

        except ValueError:
            print(f'scaler.py, main(): Failed to read "{line}".', file=sys.stderr)


if __name__ == '__main__':
    main()


