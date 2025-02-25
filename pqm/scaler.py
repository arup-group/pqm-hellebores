#!/usr/bin/env python3


#                _                       
#  ___  ___ __ _| | ___ _ __ _ __  _   _ 
# / __|/ __/ _` | |/ _ \ '__| '_ \| | | |
# \__ \ (_| (_| | |  __/ | _| |_) | |_| |
# |___/\___\__,_|_|\___|_|(_) .__/ \__, |
#                           |_|    |___/ 
# 
# Convert incoming integer samples to floating point and apply scaling
# and calibration factors

import sys
import signal

# local
from settings import Settings

# scale factors are for the following:
# ch0 = earth leakage, ch1 = low range, ch2 = full range, ch3 = voltage
HARDWARE_SCALE_FACTORS = [ 4.07e-07, 2.44e-05, 0.00122, 0.0489 ]
DELAY_LINE_LENGTH = 64


def from_twos_complement_hex(w):
    """Bit arithmetic on a two's complement, 16 bit number to convert to
    a python signed integer."""
    v = int(w, base=16)
    return -(v & 0x8000) | (v & 0x7fff)

def set_current_channel():
    """If st.current_axis_per_division is less than or equal to 0.1 A/div,
    we use channel 1 for current measurements. If it is more than 0.1 A/div,
    we use channel 2."""
    global current_channel
    if st.current_sensor == 'low':
        current_channel = 1
    else:
        current_channel = 2

def uncalibrated_constants():
    """Standard scaling constants without calibration adjustment."""
    offsets = [0, 0, 0, 0]
    gains   = HARDWARE_SCALE_FACTORS
    # delays are measured in sample periods (integer)
    # where -1 is latest sample in the delay line
    delays  = [-1, -1, -1, -1]
    return (offsets, gains, delays)

def calibrated_constants():
    """Calculate scaling constants including calibration constants."""
    try:
        offsets = st.cal_offsets
        gains   = [ h*g for h,g in zip(HARDWARE_SCALE_FACTORS, st.cal_gains) ]
        delays = [ int(-1 - t // st.interval) for t in st.cal_skew_times ]
        for d in delays:
            if d < -(DELAY_LINE_LENGTH-1) or d > -1:
                raise ValueError
        return (offsets, gains, delays)
    except (NameError, ZeroDivisionError, TypeError, ValueError):
        print('scaler.py, get_factors(): Error in setting calibration constants, '
              'switching to uncalibrated.', file=sys.stderr)
        return uncalibrated_constants()

def scale_readings(cs, offsets, gains):
    """cs contains channel readings in integers"""
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
    offsets, gains, delays = calibrated_constants() if run_calibrated else uncalibrated_constants()
    delay_lookup = list(zip([0,1,2,3], delays))

    # now loop over all the lines of data from stdin
    for line in sys.stdin:
        line = line.rstrip()
        try:
            # calculate time axis position
            t = st.interval*i
            # split channel values into an integer array, removing the index field
            new_sample = [ from_twos_complement_hex(w) for w in line.split() ]
            delay_line = delay_line[1:]
            delay_line.append(new_sample)
            # use the delay line to correct for channel timing skew
            # and apply calibration and scale factors to readings
            scaled = scale_readings([ delay_line[delay][ch] for ch, delay in delay_lookup ],
                                    offsets, gains)
            # now pick out the individual readings ready for output
            voltage = scaled[3]
            current = scaled[current_channel]
            power = voltage * current
            leakage_current = scaled[0]
            print(f'{t:12.4f} {voltage:10.3f} {current:10.5f} {power:10.3f} {leakage_current:12.7f}')
            i += 1

        except ValueError:
            print(f'scaler.py, main(): Failed to read "{line}".', file=sys.stderr)


if __name__ == '__main__':
    main()


