#!/usr/bin/env python3

#                    _                                 
#   __ _ _ __   __ _| |_   _ ___  ___ _ __ _ __  _   _ 
#  / _` | '_ \ / _` | | | | / __|/ _ \ '__| '_ \| | | |
# | (_| | | | | (_| | | |_| \__ \  __/ | _| |_) | |_| |
#  \__,_|_| |_|\__,_|_|\__, |___/\___|_|(_) .__/ \__, |
#                      |___/              |_|    |___/ 
# 

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
        self.fft_window = np.blackman(0)  # empty to begin with
        self.results = {}

    def create_fft_window(self, n_points):
        # Blackman, Flattop or Rectangular
        # Blackman is compromise, minimises spectral leakage however doesn't have the
        # best amplitude accuracy.
        # Flattop maintains amplitude accuracy the best, but suffers from spectral
        # leakage introduced near DC (although 0 Hz bin itself is accurate). Solution
        # -- set near DC frequency bins to zero.
        # Rectangular is simple but has poor accuracy as soon as frequency drifts from
        # non-integer number of cycles per frame.
        window = 'flattop'
        if window == 'blackman':
            fft_window = np.blackman(n_points)
        elif window == 'flattop':
            a0 = 0.21557895
            a1 = 0.41663158
            a2 = 0.277263158
            a3 = 0.083578947
            a4 = 0.006947368
            fft_window = np.array([ a0 - a1*math.cos(2*math.pi*n/n_points)
                + a2*math.cos(4*math.pi*n/n_points) - a3*math.cos(6*math.pi*n/n_points)
                + a4*math.cos(8*math.pi*n/n_points) for n in range(n_points) ])
        else:
            fft_window = np.array([ 1.0 for n in range(n_points) ])
        return fft_window

    def apply_filters(self):
        self.timestamps = self.data_frame[:,0]
        self.voltages = self.data_frame[:,1]
        self.currents = self.data_frame[:,2]
        self.powers = self.data_frame[:,3]
        self.leakage_currents = self.data_frame[:,4]
    
    def fft(self, samples):
        """Returns a list of tupes of (harmonic frequency, magnitude) starting from h0 (DC),
        up to h50. Automatically adapts to signals of different fundamental frequency."""
        fft_size = samples.shape[0]
        root2 = math.sqrt(2)
        # regenerate the window function if it is the wrong size for the current data
        # frame
        if self.fft_window.shape != fft_size:
            self.fft_window = self.create_fft_window(fft_size)
            self.fft_window_average = np.mean(self.fft_window)

        # calculate the fft coefficients
        fft_out = np.fft.rfft(np.multiply(samples, self.fft_window), norm='forward')
    
        # determine a list of the frequencies of the fft bins
        bins = np.fft.rfftfreq(fft_size, 1/self.sample_rate)
    
        # all the amplitude cooefficients need to be adjusted for the window
        # average amplitude and root2. The root2 term is actually a reduction of
        # 2/root2, the '2' required to account for the energy in the negative
        # frequency part of the fft, not included in the rfft, and the /root2 to
        # account for the fact that we want to display rms amplitudes, not peak
        # amplitudes
        mags = [ v * root2 / self.fft_window_average for v in np.abs(fft_out) ]
        # We've found that the magnitude coefficients near to DC are erroneous when the flattop
        # window function is used, so we set them to zero here.
        for i in [1,2,3,4]:
            mags[i] = 0.0
        # Note that we didn't zero the DC (0 Hz) coefficient. However, the dc cooefficient does
        # not need the 2/root2 term, because it has energy from both positive and negative frequency.
        # So we correct for that...
        mags[0] = mags[0] / root2
        # phases not currently used for anything, but here's how to get them if required!
        # phases = np.angle(fft_out)
        # filter for bins that are harmonics of the fundamental frequency of the signal
        base_frequency = self.results['frequency']
        harmonic_frequencies = [ round(base_frequency*h*2)/2 for h in range(0,51) ]
        harmonic_tuples = [ (f,m) for f,m in zip(bins, mags) if f in harmonic_frequencies ]
        return harmonic_tuples

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
        self.results['rms_voltage']                  = self.round_to(self.rms(self.voltages), 3)
        self.results['max_abs_voltage']              = self.round_to(np.max(np.abs(self.voltages)), 3)
        self.results['rms_current']                  = self.round_to(self.rms(self.currents), 5)
        self.results['max_abs_current']              = self.round_to(np.max(np.abs(self.currents)), 5)
        self.results['rms_leakage_current']          = self.round_to(self.rms(self.leakage_currents), 7)
        self.results['max_abs_leakage_current']      = self.round_to(np.max(np.abs(self.leakage_currents)), 7)
        self.results['mean_power']                   = self.round_to(np.mean(self.powers), 3)
        self.results['max_abs_power']                = self.round_to(np.max(np.abs(self.powers)), 3)
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
        # The fft calculation initially contains every frequency component at the resolution of the
        # fft, not just the harmonic frequencies. Therefore we find the harmonic frequencies, and then
        # filter the fft result.
        fft_voltages = self.fft(self.voltages)
        fft_currents = self.fft(self.currents)
        try:
            # harmonic voltages
            hvs = [ m for f,m in fft_voltages ]
            thdv = math.sqrt(sum([ m*m for m in hvs[2:] ])) / hvs[1]
            self.results['total_harmonic_distortion_voltage_percentage'] = self.round_to(thdv*100, 1)
            self.results['harmonic_voltage_percentages'] = \
                    [ self.round_to(m/self.results['rms_voltage']*100, 1) for m in hvs ] 
        except (ZeroDivisionError, OverflowError, ValueError, IndexError):
            self.results['total_harmonic_distortion_voltage_percentage'] = 0.0
            self.results['harmonic_voltage_percentages'] = [0.0]
        try:
            # harmonic currents
            his = [ m for f,m in fft_currents ]
            thdi = math.sqrt(sum([ m*m for m in his[2:] ])) / his[1]
            self.results['total_harmonic_distortion_current_percentage'] = self.round_to(thdi*100, 1) 
            self.results['harmonic_current_percentages'] = \
                    [ self.round_to(m/self.results['rms_current']*100, 1) for m in his ] 
        except (ZeroDivisionError, OverflowError, ValueError, IndexError):
            self.results['total_harmonic_distortion_current_percentage'] = 0.0
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


