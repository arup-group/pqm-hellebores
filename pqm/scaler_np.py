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
import numpy as np

# local
from settings import Settings


CACHE_SIZE = 128


class Scaler:
     
    def __init__(self, size, run_calibrated=True):
        self.add_f = [ 0.0, 0.0, 0.0, 0.0, 0.0 ]
        self.multiply_f = [ 1.0, 1.0, 1.0, 1.0, 1.0 ]
        self.current_channel = 2
        self.size = size
        self.st = None       # set this reference as soon as the settings object is created
        self.iterator = 0
        self.run_calibrated = run_calibrated
        self.buffer = np.full((size, 5), 0.0)

    def from_twos_complement(self, v):
        return -(v & 0x8000) | (v & 0x7fff)

    def put(self, line):
        """Store a line in the cache and increment the front pointer."""
        ptr = self.iterator % self.size
        try:
            adc_values = [ self.from_twos_complement(int(v, base=16)) for v in line.split()[1:] ]   
            t = self.iterator * self.st.interval
            self.buffer[ptr,:] = [ self.iterator,                        # time
                                   adc_values[3],                        # voltage
                                   adc_values[self.current_channel],     # current
                                   0.0,                                  # power (placeholder)
                                   adc_values[0] ]                       # earth leakage
        except ValueError:
            print(f'scaler.py, Scaler.put(): Failed to read "{line}".', file=sys.stderr)
            # empty input lines etc
            self.buffer[ptr,:] = [0.0, 0.0, 0.0, 0.0, 0.0] 
        self.iterator += 1
        return ptr

    def scale(self):
        """Apply array operations to offset and scale cache efficiently."""
        # apply calibration and standard scaling factors to the buffer
        np.add(self.buffer, self.add_f, out=self.buffer)
        np.multiply(self.buffer, self.multiply_f, out=self.buffer)
        # calculate instantaneous power
        np.multiply(self.buffer[:,1], self.buffer[:,2], out=self.buffer[:,3])

    def get_factors(self):
        """Retrieve settings from settings object. This method is automatically called
        by the settings object."""
        if self.st.current_sensor == 'low':
            self.current_channel = 1
        else:
            self.current_channel = 2       
        if self.run_calibrated == True:
            off = self.st.cal_offsets
            gain = [ s*g for s,g in zip(self.st.scale_factors, self.st.cal_gains) ]
        # we support running in 'uncalibrated' mode when we want to calibrate the device
        else:
            off = [ 0.0, 0.0, 0.0, 0.0, 0.0]
            gain = self.st.scale_factors
        self.add_f        = [ 0.0, off[3], off[self.current_channel], 0.0, off[0] ]
        self.multiply_f   = [ self.st.interval, gain[3], gain[self.current_channel], 1.0, gain[0] ] 
   
    def out(self):
        """Output to string."""
        np.savetxt(sys.stdout, self.buffer, fmt='%12.4f %10.3f %10.5f %10.3f %12.7f') 


def main():

    # check for uncalibrated mode
    if len(sys.argv) == 2 and sys.argv[1] == '--uncalibrated':
        run_calibrated = False
    else:
        run_calibrated = True

    # NB get_factors() function will be called automatically when settings are changed
    scaler = Scaler(CACHE_SIZE, run_calibrated)
    st = Settings(lambda: scaler.get_factors())
    scaler.st = st
    scaler.get_factors()

    # now loop over all the lines of data from stdin
    # scaler.put() returns the current cache pointer
    # therefore every CACHE_SIZE lines, the buffer is scaled and printed to stdout
    for line in sys.stdin:
        if scaler.put(line) == CACHE_SIZE - 1:
            scaler.scale()
            scaler.out()



if __name__ == '__main__':
    main()


