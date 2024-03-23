#!/usr/bin/env python3

import subprocess
import settings

READINGS=10

def main():
    process = subprocess.Popen('./rain_chooser.py | ./scaler.py --uncalibrated | ./analyser.py',
                               stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL,
                               shell=True)
    accumulators = [0,0,0,0,0]
    for i in range(READINGS):
        output_words = process.stdout.readline().decode('utf-8').strip().split()
        output_numbers = [ float(w) for w in output_words ] 
        accumulators = [ a+n for a,n in zip(output_numbers, accumulators) ]
    process.terminate()
    accumulators = [ n/READINGS for n in accumulators ]
    print(accumulators)


if __name__ == '__main__':
    main()


#
#
# INTRO
# Display current calibration settings that settings.py is going to use
#
#
# DC OFFSETS
# Plan: ./reader.py
# Run for 10 seconds, and take average of all readings
# Print out the integer offset needed to bring these averages to zero
#
#
# VOLTAGE
# Plan: ./reader.py | ./scaler.py
# Run for 10 seconds, and take average of voltage reading
# Apply integer offset
# Accept calibrated RMS voltage measurement
# Print out correction factor g3
#
#
# CURRENT FULL RANGE
# Plan: ./reader.py | ./scaler.py
# Run for 10 seconds, and take average of current reading
# Apply integer offset
# Accept calibrated RMS current measurement
# Print out correction factor g2
#
#
# CURRENT LOW RANGE
# Plan: ./reader.py | ./scaler.py
# Run for 10 seconds, and take average of current reading
# Apply integer offset
# Accept calibrated RMS current measurement
# Print out correction factor g1
#
#
# EARTH LEAKAGE CURRENT
# Plan: ./reader.py | ./scaler.py
# Run for 10 seconds, and take average of current reading
# Apply integer offset
# Accept calibrated RMS current measurement
# Print out correction factor g0
#
#
