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


def string_to_dict(line):
    """Converts a dictionary expressed as a string into a python dictionary
    object and then removes unwanted key/value pairs."""
    try:
        analysis = ast.literal_eval(line)
        analysis.pop('harmonic_voltage_percentages') 
        analysis.pop('harmonic_current_percentages') 
    except KeyError:
        # If it doesn't have expected keys, pass silently
        pass
    except (AttributeError, SyntaxError):
        # If it's something more serious, raise a ValueError
        raise ValueError
    return analysis

def main():
    program_name = sys.argv[0]
    # open up a csv object to write to stdout
    # We use \n rather than os.linesep because the stdout stream object already
    # converts \n to \r\n on Windows.
    csv_writer = csv.writer(sys.stdout, lineterminator='\n') 
    try:
        # for the first line, we push out both headers and data
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



