#!/usr/bin/env python3

# Convert incoming integer samples to floating point and apply scaling factors 

import sys
import signal

# local
from settings import Settings

  

def from_twos_complement(v):
    return -(v & 0x8000) | (v & 0x7fff)


def main():
    st = Settings()

    i = 0   # sample index
    for line in sys.stdin:
        line = line.rstrip()
        try:
            # calculate time axis position
            t = st.interval*i
            # get channel values as integer array, removing the index field
            cs = [ int(w.strip(), base=16) for w in line.split() ][1:]
            # calculate floating point values, using appropriate scaling factors
            voltage = ((from_twos_complement(cs[3]) + st.cal_offsets[3]) 
                       * st.scale_factors[3]
                       * st.cal_gains[3])
            # if st.current_axis_per_division is less than or equal to 0.1 A/div,
            # we use channel 1 for current measurements. If it is more than 0.1 A/div,
            # we use channel 2.
            if st.current_axis_per_division <= 0.1:
                current = ((from_twos_complement(cs[1]) + st.cal_offsets[1]) 
                           * st.scale_factors[1]
                           * st.cal_gains[1])
            else:
                current = ((from_twos_complement(cs[2]) + st.cal_offsets[2]) 
                           * st.scale_factors[2]
                           * st.cal_gains[2])
            power = voltage * current
            leakage_current = ((from_twos_complement(cs[0]) + st.cal_offsets[0])
                               * st.scale_factors[0]
                               * st.cal_gains[0])
            print(
                f'{t :12.4f} '
                f'{voltage :10.3f} '
                f'{current :10.5f} '
                f'{power :10.3f} '
                f'{leakage_current :12.7f}')
            i = i + 1

        except ValueError:
            print(
                f'scaler.py, main(): Failed to read {line}.',
                file=sys.stderr)


if __name__ == '__main__':
    main()


