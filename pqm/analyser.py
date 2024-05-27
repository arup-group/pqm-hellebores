#!/usr/bin/env python3

import math
import numpy as np
import settings
import sys


class Analyser:
    """Create an instance with the sample rate, then call load_data_frame, calculate,
    get_results in that order.""" 

    def __init__(self, sample_rate):
        self.sample_rate = sample_rate
        self.data_frame = None
        self.size = 0
        self.blackman_window = np.blackman(0)  # empty to begin with
        self.results = {}

    def apply_filters(self):
        self.timestamps = self.data_frame[:,0]
        self.voltages = self.data_frame[:,1]
        self.currents = self.data_frame[:,2]
        self.powers = self.data_frame[:,3]
        self.leakage_currents = self.data_frame[:,4]
    
    def fft(self, samples):
        fft_size = samples.shape[0]
        root2 = math.sqrt(2)
        # regenerate the blackman window if it is the wrong size for the current data
        # frame
        if self.blackman_window.shape != fft_size:
            self.blackman_window = np.blackman(fft_size)
            self.blackman_window_average = np.mean(self.blackman_window)

        # calculate the fft coefficients
        fft_out = np.fft.rfft(np.multiply(samples, self.blackman_window), norm='forward')
    
        # extract a list of the frequencies of the fft bins
        bins = np.fft.rfftfreq(fft_size, 1/self.sample_rate)
    
        # all the amplitude cooefficients need to be adjusted for the window
        # average amplitude and root2. The root2 term is actually a reduction of
        # 2/root2, the '2' required to account for the energy in the negative
        # frequency part of the fft, not included in the rfft, and the /root2 to
        # account for the fact that we want to display rms amplitudes, not peak
        # amplitudes
        mags = [ v * root2 / self.blackman_window_average for v in np.abs(fft_out) ]
        # however, the dc cooefficient does not need the 2/root2 term, so we
        # remove that here
        mags[0] = mags[0] / root2
        # phases not currently used for anything!
        phases = np.angle(fft_out)
        # filter for integer frequency bins only
        harmonics = [ (round(f), m) for f, m in zip(bins, mags) if (frac := f % 1) <0.1 or frac>0.9 ]
        return harmonics

    def rms(self, df):
        sum_of_squares = np.sum(np.square(df))
        number_of_samples = df.shape[0]
        rms = math.sqrt(sum_of_squares / number_of_samples)
        return rms

    def period_and_frequency(self):
        # look for rising edge of voltage, and count the number of periods
        crossover_times = [ self.timestamps[i] for i in np.arange(0, self.size-1) \
                if self.voltages[i] < 0.0 and self.voltages[i+1] >= 0.0 ]
        n = len(crossover_times) - 1
        try:
            # work out the time for one period
            period = (crossover_times[-1] - crossover_times[0]) / 1000.0 / n
            frequency = 1.0 / period
        except (IndexError, ZeroDivisionError):
            frequency = 0.0
        self.results['frequency'] = self.round_to(frequency, 3)

    def round_to(self, value, decimal_places):
        # round values to reduce length of output strings
        try:
            shift = 10**decimal_places
            result = round(value*shift)/shift 
        except (OverflowError, ValueError):
            result = 0
        return result

    def averages(self):
        self.results['mean_power']                   = self.round_to(np.mean(self.powers), 3)
        self.results['max_voltage']                  = self.round_to(np.max(self.voltages), 3)
        self.results['max_current']                  = self.round_to(np.max(self.currents), 5)
        self.results['max_power']                    = self.round_to(np.max(self.powers), 3)
        self.results['max_leakage_current']          = self.round_to(np.max(self.leakage_currents), 7)
        self.results['min_voltage']                  = self.round_to(np.min(self.voltages), 3)
        self.results['min_current']                  = self.round_to(np.min(self.currents), 5)
        self.results['min_power']                    = self.round_to(np.min(self.powers), 3)
        self.results['min_leakage_current']          = self.round_to(np.min(self.leakage_currents), 7)
        self.results['max_abs_voltage']              = self.round_to(np.max(np.abs(self.voltages)), 3)
        self.results['max_abs_current']              = self.round_to(np.max(np.abs(self.currents)), 5)
        self.results['max_abs_power']                = self.round_to(np.max(np.abs(self.powers)), 3)
        self.results['max_abs_leakage_current']      = self.round_to(np.max(np.abs(self.leakage_currents)), 7)
        self.results['rms_voltage']                  = self.round_to(self.rms(self.voltages), 3)
        self.results['rms_current']                  = self.round_to(self.rms(self.currents), 5)
        self.results['rms_leakage_current']          = self.round_to(self.rms(self.leakage_currents), 7)
        self.results['mean_volt_ampere']             = self.round_to(self.results['rms_voltage']
                                                              * self.results['rms_current'], 3)
        try:
            self.results['crest_factor_voltage']     = self.round_to(self.results['max_abs_voltage']
                                                              / self.results['rms_voltage'], 3)
            self.results['crest_factor_current']     = self.round_to(self.results['max_abs_current']
                                                              / self.results['rms_current'], 3)
            self.results['power_factor']             = self.round_to(self.results['mean_power']
                                                              / self.results['mean_volt_ampere'], 3)
        except ZeroDivisionError:
            self.results['crest_factor_voltage']     = 0.0
            self.results['crest_factor_current']     = 0.0
            self.results['power_factor']             = 0.0

    def power_quality(self):
        """Relies on other results: call after averages and period_and_frequency."""
        fft_voltages = self.fft(self.voltages)
        try:
            fft_currents = self.fft(self.currents)
        except:
            print('failed on fft currents')
        nominal_frequency = round(self.results['frequency'])
        harmonic_frequencies = [ nominal_frequency * h for h in range(0, 51) ]
        # save harmonic magnitudes as percentages of rms quantity to 1dp
        try:
            self.results['harmonic_voltage_percentages'] = [ self.round_to(m/self.results['rms_voltage']*100, 1) \
                for f,m in fft_voltages if f in harmonic_frequencies ]
        except (ZeroDivisionError, OverflowError, ValueError):
            self.results['harmonic_voltage_percentages'] = [0.0]
        try:
            self.results['harmonic_current_percentages'] = [ self.round_to(m/self.results['rms_current']*100, 1) \
                for f,m in fft_currents if f in harmonic_frequencies ]
        except (ZeroDivisionError, OverflowError, ValueError):
            self.results['harmonic_current_percentages'] = [0.0]

    def calculate(self):
            self.averages()
            self.period_and_frequency()
            self.power_quality()

    def load_data_frame(self, data_frame):
        self.data_frame = data_frame
        self.size = data_frame.shape[0]
        self.apply_filters()

    def get_results(self):
        return self.results


class Sample_cache:

    def __init__ (self, size):
        """The size is the size of the cache"""
        # Initialise cache with zeros, so that the first calculation runs without errors
        self.cache = [ '0.0 0.0 0.0 0.0 0.0' for i in range(size) ]
        self.size = size
        self.ptr = 0
        
    def put(self, line):
        """Increment the pointer and store a line in the cache."""
        self.ptr = (self.ptr + 1) % self.size
        self.cache[self.ptr] = line
 
    def get(self, pointer_offset):
        """Retrieve the line at current pointer minus pointer_offset."""
        optr = (self.ptr - pointer_offset) % self.size
        return self.cache[optr]

    def as_numpy_array(self):
        """Convert the cache into a numpy array. The current self.ptr marks the
        front of the cache."""
        rear_ptr = (self.ptr + 1) % self.size
        wrapped_cache = self.cache[rear_ptr:] + self.cache[:rear_ptr]
        sample_array = np.loadtxt(wrapped_cache, encoding='utf-8')
        return sample_array


def main():
    st = settings.Settings()
    calculation_interval = int(st.sample_rate)
    cache_size = int(st.sample_rate*2)
    cache = Sample_cache(cache_size)
    analyser = Analyser(st.sample_rate)
    # line iterator
    i = 0
    for line in sys.stdin:
        # Cache every line, and output calculations every 1 second
        cache.put(line.rstrip())
        if i == 0:
            d = cache.as_numpy_array()
            analyser.load_data_frame(d)
            analyser.calculate()
            results = analyser.get_results()
            print(results)
            sys.stdout.flush()
        # circulate line iterator to zero every calculation interval (1 second)
        i = (i + 1) % calculation_interval
    print('Finished calculations.', file=sys.stderr)

if __name__ == '__main__':
    main()


