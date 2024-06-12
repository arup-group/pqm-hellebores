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
import time

ROOT2 = math.sqrt(2)

class Analyser:
    """Create an instance with the sample rate, then call load_data_frame, calculate,
    get_results in that order.""" 

    def __init__(self, st):
        self.st = st
        self.sample_rate = st.sample_rate
        self.data_frame = None
        self.size = 0
        self.fft_window = np.blackman(0)  # empty to begin with
        self.results = {}
        self.reset_accumulators()

    def reset_accumulators(self):
        """set integer accumulators to zero: time in milliseconds, and energy transfer in
        milli-watt-seconds etc."""
        self.accumulated_time = 0
        self.mws = 0
        self.mvas = 0
        self.mvars = 0

    def check_updated_settings(self):
        if self.st.analysis_start_time == 0:
            # reset analysis accumulators
            self.reset_accumulators()
            self.st.analysis_start_time = time.time()
            self.st.send_to_all()

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
                file=sys.stderr)
            fft_window = self.create_fft_window(n_points)
        return fft_window

    def apply_filters(self):
        """Filter the multi-column data frame into single column array slices of the data."""
        self.timestamps = self.data_frame[:,0]
        self.voltages = self.data_frame[:,1]
        self.currents = self.data_frame[:,2]
        self.powers = self.data_frame[:,3]
        self.leakage_currents = self.data_frame[:,4]
   
    def harmonic_frequency_magnitudes(self, base_frequency, samples):
        """Returns a list of tuples of (harmonic frequency, magnitude) starting from h0 (DC),
        up to h50. Automatically adapts to signals of different h1 (base) frequency."""
        fft_size = samples.shape[0]
        # Regenerate the window function if it is the wrong size for the current data frame.
        # All the amplitude cooefficients need to be adjusted for the window
        # average amplitude and root2. The root2 term is actually a reduction of
        # 2/root2, the '2' required to account for the energy in the negative
        # frequency part of the fft, not included in the rfft, and the /root2 to
        # account for the fact that we want to display rms amplitudes, not peak
        # amplitudes
        if self.fft_window.shape[0] != fft_size:
            self.fft_window = self.create_fft_window(fft_size)
            # Bin size = sample rate / fft length.
            # Nyquist frequency = sample rate /2 
            # eg for fft_size = 7812, self.sample_rate = 7812.5, the bins are
            # approximately 1Hz apart and the Nyquist frequency is 3906.25 Hz.
            self.bins = np.round(np.fft.rfftfreq(fft_size, 1/self.sample_rate),0)
            self.magnitude_scale_factor = ROOT2 / np.mean(self.fft_window)
            
        # calculate the fft coefficients
        fft_out = np.fft.rfft(np.multiply(samples, self.fft_window), norm='forward')
        mags = np.abs(fft_out) * self.magnitude_scale_factor

        # The dc cooefficient does not need the 2/root2 term, because it has energy from
        # both positive and negative frequency. So we correct for that...
        mags[0] = mags[0] / ROOT2 

        # Phases not currently used for anything, but here's how to get them if required!
        # phases = np.angle(fft_out)

        # rounds harmonic frequencies to the nearest 1.0Hz
        harmonic_frequencies = [ round(base_frequency*h) for h in range(0,51) ]

        # Filter mags for just harmonic magnitudes, using numpy integer indexing
        harmonic_magnitudes = mags[ np.nonzero([1 if f in harmonic_frequencies else 0 for f in self.bins]) ] 
        return harmonic_magnitudes

    def rms(self, df):
        """Determine the RMS average of the array."""
        rms = math.sqrt(np.mean(np.square(df)))
        # catch zero length input arrays
        if math.isnan(rms):
            rms = 0.0        
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
        """Round values to reduce length of output strings. NaN input values are coerced to zero."""
        if math.isnan(value):
            result = 0.0
        else:
            shift = 10**decimal_places
            result = round(value*shift)/shift 
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
        self.results['crest_factor_voltage']         = self.round_to(maxabs_v / rms_v, 3)
        self.results['crest_factor_current']         = self.round_to(maxabs_i / rms_i, 3)
        self.results['power_factor']                 = self.round_to(mean_p / mean_va, 3)

    def power_quality(self):
        """Power quality calcuation relies on other results: call after averages and frequency."""
        n_samples = math.floor(self.sample_rate)
        base_frequency = self.results['frequency']
        try:
            if self.voltages.shape[0] < n_samples or self.currents.shape[0] < n_samples:
                raise IndexError

            # returns harmonic magnitudes from h0 to h50, as a list
            fft_voltages = self.harmonic_frequency_magnitudes(base_frequency, self.voltages[-n_samples:])
            fft_currents = self.harmonic_frequency_magnitudes(base_frequency, self.currents[-n_samples:])

            # convert harmonic voltages to % of RMS value, and calculate THD(v)
            thdv = math.sqrt(np.sum(np.square(fft_voltages[2:]))) / fft_voltages[1]
            self.results['total_harmonic_distortion_voltage_percentage'] = self.round_to(thdv*100, 1)
            sf = 100/self.results['rms_voltage']
            self.results['harmonic_voltage_percentages'] = np.round(fft_voltages*sf, 1).tolist()

            # convert harmonic currents to % of RMS value, and calculate THD(i)
            thdi = math.sqrt(np.sum(np.square(fft_currents[2:]))) / fft_currents[1]
            self.results['total_harmonic_distortion_current_percentage'] = self.round_to(thdi*100, 1) 
            sf = 100/self.results['rms_current']
            self.results['harmonic_current_percentages'] = np.round(fft_currents*sf, 1).tolist()

        except (ZeroDivisionError, OverflowError, ValueError, IndexError):
            self.results['total_harmonic_distortion_voltage_percentage'] = 0.0
            self.results['harmonic_voltage_percentages'] = [0.0 for m in fft_voltages ]
            self.results['total_harmonic_distortion_current_percentage'] = 0.0
            self.results['harmonic_current_percentages'] = [0.0 for m in fft_currents ]

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
        self.input_array = np.zeros((size,5))
        self.output_array = np.zeros((size,5))
        self.size = size
        self.front_ptr = 0
        
    def put(self, line):
        """Increment the pointer and store a line in the cache."""
        self.front_ptr = (self.front_ptr + 1) % self.size
        try:
            self.input_array[self.front_ptr] = line.split()
        except ValueError:
            # empty input lines etc
            self.input_array[self.front_ptr] = (0.0,0.0,0.0,0.0,0.0) 

    def get_output_array(self):
        """Convert the circular input cache into an output array ordered from rear_ptr to front_ptr."""
        self.rear_ptr = (self.front_ptr + 1) % self.size
        np.concatenate((self.input_array[self.rear_ptr:], self.input_array[:self.rear_ptr]), out=self.output_array)
        return self.output_array

def check_updated_settings():
    global analyser
    analyser.check_updated_settings()

def read_lines(n, cache):
    """Reads n lines from stdin, and stores in the cache."""
    for i in range(n):
        line = sys.stdin.readline().rstrip()
        cache.put(line)
    # Test for end of input stream
    if line == '':
        raise SystemExit
    return i

def read_analyse_output(cache, analyser, output_interval):
    """Loop through analysis and output processes, interspersed with new data reading
    to avoid stalling the sample data pipeline at the input."""
    # Divide the frame of data for each output_interval into 6 blocks of roughly equal size:
    # the final block will be rounded up.
    block_size = output_interval // 6
    while True:
        interval_counter = 0
        # Retrieve a block of calculation data, and load it into the analyser
        analyser.load_data_frame(cache.get_output_array()) 
        interval_counter += read_lines(block_size, cache)
        # Analyse the data in steps
        calculation_tasks = [ analyser.averages,
                              analyser.frequency,
                              analyser.power_quality,
                              analyser.accumulators ]
        for task in calculation_tasks:
            task()
            interval_counter += read_lines(block_size, cache)
        # Generate the output
        print(json.dumps(analyser.get_results()))
        sys.stdout.flush()
        # Complete the frame of new data acquisition for the current interval
        # rounding up this block of data to make exactly one 'output_interval'.
        read_lines(output_interval - interval_counter, cache)

def main():
    global analyser
    st = settings.Settings(lambda: check_updated_settings())
    # We will output new calculations once per second.
    output_interval = int(st.sample_rate)
    # However, our calculation buffer is 2 seconds in length to increase accuracy.
    cache_size = int(st.sample_rate*2)
    # The cache is a circular buffer, we can keep pushing data into it.
    cache = Sample_cache(cache_size)
    analyser = Analyser(st)
    # Before actually analysing, seed the cache with data
    read_lines(cache.size, cache)
    # Read, analyse, output loop
    read_analyse_output(cache, analyser, output_interval)



if __name__ == '__main__':
    main()


