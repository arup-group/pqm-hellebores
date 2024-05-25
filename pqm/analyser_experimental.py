#!/usr/bin/env python3

import math
import numpy as np
import settings
import sys

MAX_LINE_LENGTH = 128

class Sample_cache:

    def __init__ (self, size):
        """The size is the size of the cache"""
        self.cache = [ '' for i in range(size) ]
        self.size = size
        self.ptr = 0
        
    def put(self, line):
        """Increment the pointer and store a line in the cache."""
        self.ptr = (self.ptr + 1) % self.size
        self.cache[self.ptr][:] = line
 
    def get(self, pointer_offset):
        """Retrieve the line at current pointer minus pointer_offset."""
        optr = (self.ptr - pointer_offset) % self.size
        return self.cache[optr]

    def as_numpy_array(self):
        """Convert the cache into a numpy array. The current self.ptr marks the
        front of the cache."""
        rear_ptr = (self.ptr + 1) % self.size
        front_np = np.loadtxt(self.cache[:rear_ptr], encoding='utf-8')
        rear_np = np.loadtxt(self.cache[rear_ptr:], encoding='utf-8') 
        complete_np = np.append(rear_np, front_np)
        return complete_np


def main():
    st = settings.Settings()
    samples_per_second = st.sample_rate
    calculation_interval = int(samples_per_second)
    cache = Sample_cache(int(samples_per_second*2))
    i = 0
    for line in sys.stdin:
        # Cache every line, and output calculations every 1 second
        cache.put(line.rstrip())
        if i == 0:
            print(cache.as_numpy_array()[:5])
            sys.stdout.flush()
        i = (i + 1) % calculation_interval
    print('Finished calculations.', file=sys.stderr)

if __name__ == '__main__':
    main()


def colab():
    
    TESTDATA = '../sample_files/test_data.out'
    with open(TESTDATA, 'r') as f:
        sampledata = f.read()
    
    alldata = np.loadtxt(sampledata.split('\n'), encoding='utf-8')
    print(alldata[0:5])
    
    """As before, we will truncate the data to the same 7812 samples, representing 1 second."""
    
    somedata = alldata[-7812:,:]
    n_samples = len(somedata)
    print(n_samples)
    print(somedata[0:3,:])
    
    """Numpy supports proper multidimensional arrays. To access individual elements, we can now do this:"""
    
    print(somedata[1,2])
    
    """Now that we have the data in a fast array, let's do some electrical calculations. Start with finding the mean value for all four channels:
    #Mean
    """
    
    timestamps = somedata[:,0]
    voltages = somedata[:,1]
    currents = somedata[:,2]
    powers = somedata[:,3]
    leakage_currents = somedata[:,4]
    means = [ np.mean(voltages), np.mean(currents), np.mean(powers), np.mean(leakage_currents) ]
    print('Mean: ', means)
    
    """
    #Max/min"""
    
    maxes = [ np.max(voltages), np.max(currents), np.max(powers), np.max(leakage_currents) ]
    mins =  [ np.min(voltages), np.min(currents), np.min(powers), np.min(leakage_currents) ]
    max_abs = [ np.max(np.abs(voltages)), np.max(np.abs(currents)), np.max(np.abs(powers)), np.max(np.abs(leakage_currents)) ]
    print('Maxima: ', maxes)
    print('Minima: ', mins)
    print('Max abs:', max_abs)
    
    """#RMS"""
    
    sum_of_squares = [ np.sum(np.square(voltages)), np.sum(np.square(currents)), np.sum(np.square(powers)), np.sum(np.square(leakage_currents)) ]
    rmses = [ math.sqrt(i/n_samples) for i in sum_of_squares ]
    print(sum_of_squares)
    print('RMS values:', rmses)
    
    """#Crest factors.
    The zip function combines two lists into one list of two-tuples. This allows us to iterate over two sets of data (peak and average) simultaneously:
    """
    
    # Calculate crest factor for voltage, current and leakage current
    # NB Crest factor is not defined for power quantities.
    crests = [ max/rms for max, rms in zip(max_abs, rmses) ]
    print('Crest factors: ', crests[0], crests[1], crests[3])
    
    """#Frequency"""
    
    # Find all rising slope zero crossings of voltage (column 0 is time and column 1 is voltage)
    ts = [ timestamps[i] for i in np.arange(0, 7811) if voltages[i] <= 0.0 and voltages[i+1] >= 0.0 ]
    # Count the number of them
    n = len(ts)
    print(n)
    # Find the timestamp of first and last zero crossing
    print(ts[0], ts[-1])
    # Divide the time taken by the number of zero crossings, to figure out the average period
    period = (ts[-1] - ts[0])/1000.0/n
    # Reciprocate the period to find the frequency.
    frequency = 1.0/period
    print(f'Period:    {period :10.5f} s')
    print(f'Frequency: {frequency :10.2f} Hz')
    
    """#Power, VA"""
    
    power = means[2]
    va = rmses[0] * rmses[1]
    print(f'Power: {power :10.3f}')
    print(f'VA:    {va: 10.3f}')
    
    """#Power factor"""
    
    pf = power/va
    print(f'pf: {pf :10.3f}')
    
    """#All together"""
    
    # dictionary of results
    results = {}
    results['rms_voltage'] = rmses[0]
    results['rms_current'] = rmses[1]
    results['rms_leakage_current'] = rmses[3]
    results['peak_voltage'] = max_abs[0]
    results['peak_current'] = max_abs[1]
    results['peak_power'] = max_abs[2]
    results['peak_leakage_current'] = max_abs[3]
    results['mean_power'] = means[2]
    results['mean_apparent_power'] = va
    results['power_factor'] = pf
    results['period'] = period
    results['frequency'] = frequency
    results['power'] = power
    results['crest_factor_voltage'] = crests[0]
    results['crest_factor_current'] = crests[1]
    results['crest_factor_leakage_current'] = crests[3]
    
    for k in results:
        print(f'{k :30}: {results[k] :10.5f}')
    
    """#Harmonic analysis:
    
    Harmonic magnitudes, phases
    The distance between frequency bins is equal to the sample rate divided by the number of samples.
    
    Therefore:
       with a sample rate of 7812.5 Sa/s, and 7812 samples, the bin size is 1.000064 Hz.
       with a sample rate of 7812.5 Sa/s, and 15625 samples, the bin size is 0.5Hz exactly.
    
    A window function is applied to prevent discontinuity in the time domain at the beginning and end of the sample range from causing spectral leakage (error in the fft result).
    
    """
    
    sample_rate = 7812.5
    root2 = math.sqrt(2)
    n_samples = 7812
    blackman_window = np.blackman(n_samples)
    blackman_window_average = np.mean(blackman_window)
    print(blackman_window_average)
    
    def fft(samples, sample_rate, n_samples):
        # apply blackman window to samples
        fft_out = np.fft.rfft(np.multiply(samples, blackman_window), norm='forward')
    
        # extract a list of the frequencies of the fft bins
        bins = np.fft.rfftfreq(n_samples, 1/sample_rate)
    
        # all the amplitude cooefficients need to be adjusted for the window
        # average amplitude and root2. The root2 term is actually a reduction of
        # 2/root2, the '2' required to account for the energy in the negative
        # frequency part of the fft, not included in the rfft, and the /root2 to
        # account for the fact that we want to display rms amplitudes, not peak
        # amplitudes
        mags = [ v * root2 / blackman_window_average for v in np.abs(fft_out) ]
        # however, the dc cooefficient does not need the 2/root2 term, so we
        # remove that here
        mags[0] = mags[0] / root2
    
        phases = np.angle(fft_out)
    
        return(bins, mags, phases)
    
    
    voltage_points = somedata[:,1]
    
    bins, mags, phases = fft(voltage_points, sample_rate, n_samples)
    
    frequency_vs_voltage = dict(zip(bins, mags))
    
    print(len(voltage_points))
    print(len(bins))
    print(frequency_vs_voltage)
    
    """Generate the FFT for the current data:"""
    
    current_points = somedata[:,2]
    
    bins, mags, phases = fft(current_points, sample_rate, n_samples)
    
    frequency_vs_current = dict(zip(bins, mags))
    
    print(len(current_points))
    print(len(bins))
    print(frequency_vs_current)
    
    """Generate an FFT for some artificial test data. This helps to convince us that we have got the amplitude of the harmonic voltages right."""
    
    def generate(amplitude, frequency, sample_rate, n_points):
        out = [ amplitude * math.sin(2*math.pi*frequency*i/sample_rate) for i in range(n_points) ]
        return out
    
    # start with a DC offset
    voltage_test_points = np.array([0.0 * 7812]) + 2.0
    # three ac frequency components, FFT should show peaks with these amplitudes
    # and frequencies
    v1 = generate(3.0*root2, 50.0, sample_rate, 7812)
    v2 = generate(1.0*root2, 150.0, sample_rate, 7812)
    v3 = generate(2.0*root2, 450.0, sample_rate, 7812)
    for v in [v1, v2, v3]:
        voltage_test_points = np.add(voltage_test_points, v)
    
    bins, mags, phases = fft(voltage_test_points, sample_rate, n_samples)
    frequency_vs_voltage_test = dict(zip(bins, mags))
    
    def threshold_check(v):
        key, value = v
        if value > 0.01:
            return True
        else:
            return False
    
    print(len(voltage_test_points))
    print(len(bins))
    print(dict(filter(threshold_check, frequency_vs_voltage_test.items())))
    
    """Total harmonic distortion (TBC)"""
    
    print(timestamps)
    
