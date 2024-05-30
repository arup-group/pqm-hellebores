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
import json

class Analyser:
    """Create an instance with the sample rate, then call load_data_frame, calculate,
    get_results in that order.""" 

    def __init__(self, sample_rate):
        self.sample_rate = sample_rate
        self.data_frame = None
        self.size = 0
        self.fft_window = np.blackman(0)  # empty to begin with
        self.results = {}
        # set integer accumulators to zero: time in milliseconds, and energy transfer in
        # milli-watt-seconds etc
        self.accumulated_time = 0
        self.mws = 0
        self.mvas = 0
        self.mvars = 0

    def create_fft_window(self, n_points, window_type='flattop'):
        # window_type = 'blackman', 'flattop' or 'rectangular'
        # Blackman is compromise, mitigates spectral leakage however doesn't have the
        # best amplitude accuracy.
        # Flattop maintains amplitude accuracy the best, but suffers from spectral
        # leakage introduced near DC (although 0 Hz bin itself is accurate).
        # Rectangular is simple but has poor accuracy as soon as frequency drifts from
        # non-integer number of cycles per frame.
        if window_type == 'blackman':
            fft_window = np.blackman(n_points)
        elif window_type == 'flattop':
            a0 = 0.21557895
            a1 = 0.41663158
            a2 = 0.277263158
            a3 = 0.083578947
            a4 = 0.006947368
            fft_window = np.array([ a0 - a1*math.cos(2*math.pi*n/n_points)
                + a2*math.cos(4*math.pi*n/n_points) - a3*math.cos(6*math.pi*n/n_points)
                + a4*math.cos(8*math.pi*n/n_points) for n in range(n_points) ])
        elif window_type == 'rectangular':
            fft_window = np.array([ 1.0 for n in range(n_points) ])
        else:
            print('Analyser: create_fft_window() window_type not known, using default.',
                file=sys.stederr)
            fft_window = self.create_fft_window(n_points)
        return fft_window

    def apply_filters(self):
        self.timestamps = self.data_frame[:,0]
        self.voltages = self.data_frame[:,1]
        self.currents = self.data_frame[:,2]
        self.powers = self.data_frame[:,3]
        self.leakage_currents = self.data_frame[:,4]
    
    def fft(self, samples):
        """Returns a list of tuples of (harmonic frequency, magnitude) starting from h0 (DC),
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
    
        # All the amplitude cooefficients need to be adjusted for the window
        # average amplitude and root2. The root2 term is actually a reduction of
        # 2/root2, the '2' required to account for the energy in the negative
        # frequency part of the fft, not included in the rfft, and the /root2 to
        # account for the fact that we want to display rms amplitudes, not peak
        # amplitudes
        mags = [ v * root2 / self.fft_window_average for v in np.abs(fft_out) ]
        # The dc cooefficient does not need the 2/root2 term, because it has energy from
        # both positive and negative frequency. So we correct for that...
        mags[0] = mags[0] / root2
        # Phases not currently used for anything, but here's how to get them if required!
        # phases = np.angle(fft_out)
        # Filter for bins that are harmonics of the fundamental frequency of the signal
        base_frequency = self.results['frequency']
        harmonic_frequencies = [ round(base_frequency*h*2)/2 for h in range(0,51) ]
        harmonic_tuples = [ (f,m) for f,m in zip(bins, mags) if f in harmonic_frequencies ]
        return harmonic_tuples

    def rms(self, df):
        """Determine the RMS average of the array."""
        sum_of_squares = np.sum(np.square(df))
        number_of_samples = df.shape[0]
        rms = math.sqrt(sum_of_squares / number_of_samples)
        return rms

    def frequency(self):
        """Determines the fundamental frequency in Hz to three decimal places."""
        try:
            # look for instances where voltage crosses from negative to positive
            # and count how many occurred.
            crossover_instances = [ i for i in np.arange(0, self.size-1) \
                if self.voltages[i] < 0.0 and self.voltages[i+1] >= 0.0 ]
            n = len(crossover_instances) - 1
            # Now determine the exact time when the first and last crossovers
            # occurred, interpolating between adjacent time samples at those instances
            # to further increase the time resolution.
            c0 = crossover_instances[0]
            cn = crossover_instances[-1]
            # The 1000.0 factor is because the timestamps are in milliseconds, but the
            # sample rate is /second
            t0 = self.timestamps[c0] + (1000.0 * self.voltages[c0]
                                        / (self.voltages[c0]-self.voltages[c0+1])
                                        / self.sample_rate)
            tn = self.timestamps[cn] + (1000.0 * self.voltages[cn]
                                        / (self.voltages[cn]-self.voltages[cn+1])
                                        / self.sample_rate)
            # The overall time period divided by the number of cycles gives us the
            # period and frequency of the signal.
            period = (tn-t0) / 1000.0 / n
            frequency = 1.0 / period
        except (IndexError, ZeroDivisionError):
            frequency = 0.0
        self.results['frequency'] = self.round_to(frequency, 3)

    def round_to(self, value, decimal_places):
        """Round values to reduce length of output strings.
        Zero decimal places is not implemented."""
        try:
            shift = 10**decimal_places
            result = round(value*shift)/shift 
        except (OverflowError, ValueError):
            result = value
        return result

    def averages(self):
        """Calculate average and RMS values of the dataset."""
        rms_v                                        = self.rms(self.voltages)
        self.results['rms_voltage']                  = self.round_to(rms_v, 3)
        maxabs_v                                     = np.max(np.abs(self.voltages))
        self.results['max_abs_voltage']              = self.round_to(maxabs_v, 3)
        rms_i                                        = self.rms(self.currents)
        self.results['rms_current']                  = self.round_to(rms_i, 5)
        maxabs_i                                     = np.max(np.abs(self.currents))
        self.results['max_abs_current']              = self.round_to(maxabs_i, 5)
        self.results['rms_leakage_current']          = self.round_to(self.rms(self.leakage_currents), 7)
        self.results['max_abs_leakage_current']      = self.round_to(np.max(np.abs(self.leakage_currents)), 7)
        mean_p                                       = np.mean(self.powers)
        self.results['mean_power']                   = self.round_to(mean_p, 3)
        self.results['max_abs_power']                = self.round_to(np.max(np.abs(self.powers)), 3)
        mean_va                                      = self.round_to(rms_v * rms_i, 3)
        self.results['mean_volt_ampere']             = mean_va
        try:
            mean_var                                 = math.sqrt(mean_va**2 - mean_p**2)
        except ValueError:
            mean_var                                 = 0.0
        self.results['mean_volt_ampere_reactive']    = self.round_to(mean_var, 3)
        try:
            self.results['crest_factor_voltage']     = self.round_to(maxabs_v / rms_v, 3)
        except ZeroDivisionError:
            self.results['crest_factor_voltage']     = 0.0
        try:
            self.results['crest_factor_current']     = self.round_to(maxabs_i / rms_i, 3)
        except ZeroDivisionError:
            self.results['crest_factor_current']     = 0.0
        try:
            self.results['power_factor']             = self.round_to(mean_p / mean_va, 3)
        except ZeroDivisionError:
            self.results['power_factor']             = 0.0

    def power_quality(self):
        """Power quality calcuation relies on other results: call after averages and frequency."""
        fft_voltages = self.fft(self.voltages)
        fft_currents = self.fft(self.currents)
        try:
            # convert harmonic voltages to % of RMS value, and calculate THD(v)
            ms = [ m for f,m in fft_voltages ]
            thdv = math.sqrt(sum([ m*m for m in ms[2:] ])) / ms[1]
            self.results['total_harmonic_distortion_voltage_percentage'] = self.round_to(thdv*100, 1)
            self.results['harmonic_voltage_percentages'] = \
                    [ self.round_to(m/self.results['rms_voltage']*100, 1) for m in ms ] 
        except (ZeroDivisionError, OverflowError, ValueError, IndexError):
            self.results['total_harmonic_distortion_voltage_percentage'] = 0.0
            self.results['harmonic_voltage_percentages'] = [0.0]
        try:
            # convert harmonic currents to % of RMS value, and calculate THD(i)
            ms = [ m for f,m in fft_currents ]
            thdi = math.sqrt(sum([ m*m for m in ms[2:] ])) / ms[1]
            self.results['total_harmonic_distortion_current_percentage'] = self.round_to(thdi*100, 1) 
            self.results['harmonic_current_percentages'] = \
                    [ self.round_to(m/self.results['rms_current']*100, 1) for m in ms ] 
        except (ZeroDivisionError, OverflowError, ValueError, IndexError):
            self.results['total_harmonic_distortion_current_percentage'] = 0.0
            self.results['harmonic_current_percentages'] = [0.0]

    def accumulators(self):
        """Wh, VARh and VAh accumulators."""
        # delta_t in milliseconds
        # divide by two because the sample data overlaps each calculation (ie each sample participates
        # twice, so we add half of the contribution each time)
        delta_t = int(self.size / self.sample_rate / 2 * 1000)
        self.accumulated_time += delta_t
        # Keep the accumulators in high resolution integer form, ie 'milliwatt-seconds'.
        self.mws += round(self.results['mean_power'] * delta_t)
        self.mvas += round(self.results['mean_volt_ampere'] * delta_t)
        self.mvars += round(self.results['mean_volt_ampere_reactive'] * delta_t)
        # For display purposes, convert to 'Watt-hours'
        self.results['watt_hour'] = self.round_to(self.mws / 1000 / 3600, 3)
        self.results['volt_ampere_hour'] = self.round_to(self.mvas / 1000 / 3600, 3)
        self.results['volt_ampere_reactive_hour'] = self.round_to(self.mvars / 1000 / 3600, 3)
        self.results['hours'] = self.round_to(self.accumulated_time / 1000 / 3600, 3)

    def calculate(self):
        """Perform analysis on a pre-loaded data frame."""
        self.averages()
        self.frequency()
        self.power_quality()
        self.accumulators()

    def load_data_frame(self, data_frame):
        """Load a data frame into memory, and slice into separate sets for voltage, current
        etc."""
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
    # We will output new calculations once per second.
    output_interval = int(st.sample_rate)
    # However, our calculation buffer is 2 seconds in length to increase accuracy.
    cache_size = int(st.sample_rate*2)
    # The cache is a circular buffer, we can keep pushing data into it.
    cache = Sample_cache(cache_size)
    analyser = Analyser(st.sample_rate)
    # Before actually analysing, seed the cache with data
    for i in range(cache_size):
        line = sys.stdin.readline()
        cache.put(line.rstrip())
    # Now start the analysis loop
    i = 0 
    while True:
        line = sys.stdin.readline()
        cache.put(line.rstrip())
        # iterator is reset to zero every output interval
        if i == 0:
            # Retrieve the buffer and push it into the analyser instance.
            df = cache.as_numpy_array()
            analyser.load_data_frame(df)
            analyser.calculate()
            results = json.dumps(analyser.get_results())
            print(results)
            sys.stdout.flush()
        # circulate line iterator to zero every output interval (1 second)
        i = (i + 1) % output_interval
    print('Finished calculations.', file=sys.stderr)

if __name__ == '__main__':
    main()


