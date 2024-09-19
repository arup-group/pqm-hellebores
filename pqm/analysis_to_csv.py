#!/usr/bin/env python3

# 
#                    _           _        _                                     
#   __ _ _ __   __ _| |_   _ ___(_)___   | |_ ___     ___ _____   ___ __  _   _ 
#  / _` | '_ \ / _` | | | | / __| / __|  | __/ _ \   / __/ __\ \ / / '_ \| | | |
# | (_| | | | | (_| | | |_| \__ \ \__ \  | || (_) | | (__\__ \\ V /| |_) | |_| |
#  \__,_|_| |_|\__,_|_|\__, |___/_|___/___\__\___/___\___|___/ \_(_) .__/ \__, |
#                      |___/         |_____|    |_____|            |_|    |___/ 
# 

import sys
import ast
import csv
from datetime import datetime, timezone
from settings import Settings


def string_to_dict(line):
    """Converts a dictionary expressed as a string into a python dictionary
    object and then removes unwanted key/value pairs."""
    wanted_keys = ['rms_voltage','rms_current','mean_power','mean_volt_ampere_reactive',\
                   'mean_volt_ampere','watt_hour','volt_ampere_reactive_hour',\
                   'volt_ampere_hour','hours','power_factor','crest_factor_current','frequency',\
                   'rms_leakage_current','total_harmonic_distortion_voltage_percentage',\
                   'total_harmonic_distortion_current_percentage']
    try:
        analysis = ast.literal_eval(line)
        # insert timestamp, rounded down to nearest second
        # Excel-compatible datetime without timezone information
        # for RFC3339 format with timezone, add .astimezone().isoformat('T)
        filtered_analysis = { 'timestamp':  datetime.now().replace(microsecond=0) }
        filtered_analysis.update({ k:analysis[k] for k in wanted_keys })
    except KeyError:
        # If a key error, help to point to that problem
        print(f"{sys.argv[0]}, string_to_dict(): Key error in {wanted_keys}.", file=sys.stderr)
    except (AttributeError, SyntaxError):
        # If another type of problem, raise a ValueError
        raise ValueError
    return filtered_analysis

def main():
    # The only purpose we create st object is to to trap CTRL-C (SIGINT) signal.
    # This signal is used to control reload of settings in other programs 
    # in the project but unavoidably also received by this program.
    st=Settings(reload_on_signal=False)

    program_name = sys.argv[0]
    # open up a csv object to write to stdout
    # We use \n rather than os.linesep because the stdout stream object already
    # converts \n to \r\n on Windows.
    csv_writer = csv.writer(sys.stdout, lineterminator='\n') 
    try:
        # skip the first two lines, to allow averages to be established
        line = sys.stdin.readline()
        line = sys.stdin.readline()
        # for the third line, we push out both headers and data
        line = sys.stdin.readline()
        analysis = string_to_dict(line)
        csv_writer.writerow(analysis.keys())
        csv_writer.writerow(analysis.values())
        # for the subsequent lines, we write data only
        for line in sys.stdin:
            analysis = string_to_dict(line)
            csv_writer.writerow(analysis.values())
    except (OSError, IOError, ValueError):
        print(f"{program_name}, main(): Failed to process '{line.strip()}', quitting.",\
                  file=sys.stderr) 


if __name__ == '__main__':
    main()



