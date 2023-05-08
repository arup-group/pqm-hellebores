#!/usr/bin/env python3

# Convert incoming integer samples to floating point and apply scaling factors 

import sys
import signal
import settings

  

def from_twos_complement(v):
    return -(v & 0x8000) | (v & 0x7fff)


def main():
    st = settings.Settings(lambda: None)

    i = 0   # sample index
    for line in sys.stdin:
        line = line.rstrip()
        try:
            # calculate time axis position
            t = st.interval*i
            # get channel values as integer array
            cs = [int(w.strip(), base=16) for w in line.split()][1:]
            # calculate floating point values, using appropriate scaling factors
            voltage = (from_twos_complement(cs[3]) + st.adc_offset_trim_c3) * st.scale_c3
            # if st.current_axis_per_division is less than or equal to 0.1 A/div, we use channel 1 for
            # current measurements. If it is more than 0.1 A/div, we use channel 2.
            if st.current_axis_per_division <= 0.1:
                current = (from_twos_complement(cs[1]) + st.adc_offset_trim_c1) * st.scale_c1
            else:
                current = (from_twos_complement(cs[2]) + st.adc_offset_trim_c2) * st.scale_c2
            power = voltage * current
            leakage_current = (from_twos_complement(cs[0]) + st.adc_offset_trim_c0) * st.scale_c0 

        except ValueError:
            print('scaler.py, main(): Failed to read "' + line + '".', file=sys.stderr)
        print(f'{t :12.4f} {voltage :10.3f} {current :10.5f} {power :10.3f} {leakage_current :12.7f}')
        i = i + 1


if __name__ == '__main__':
    main()


