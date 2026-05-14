#! /usr/bin/env python3

import sys
import time
import serial
import serial.tools.list_ports


def find_serial_device():
    '''determines the serial port that the Pico is connected to. On Ubuntu/Raspberry
    Pi, serial ports are in the form '/dev/ttyUSBx' where x is an integer 0-7.
    On Windows, serial ports are in the form 'COMx' where x is an integer 1-8'''
    ports = serial.tools.list_ports.comports()
    port_name = None
    for port in ports:
        description = port.description
        if 'board in fs mode' in description.lower() or 'serial' in description.lower():
            port_name = port.device
            break
    return port_name


def reset_fluke_meter(ser):
    # reset meter to defaults
    ser.write(b'*rst\n')
    ser.readline()
    ser.readline()


def read_fluke_display(ser):
    global last_good_reading
    ser.write(b'val1?\n')
    try:
        line1 = ser.readline() # echo of command
        line2 = ser.readline() # actual value
        reading = float(line2)
        last_good_reading = reading # update last good reading
        line3 = ser.readline() # prompt =>
    except ValueError:
        # the meter probably wasn't ready, so we got empty strings
        # wait then read three times to resynchronise with the meter
        time.sleep(1)
        ser.readline()
        ser.readline()
        ser.readline()
        # re-issue the last good reading, if available
        try:
            reading = last_good_reading
        except NameError:
            reading = 0
    return reading


class Accumulators:
    """Retains a record of successive readings in an accumulator and a count.
    The accumulator is split into two halves so that it can be 'shifted' every
    second while computing averages every 2 seconds."""
    def __init__(self):
        self.acc0 = 0
        self.acc1 = 0
        self.count0 = 0
        self.count1 = 0

    def add(self, reading):
        self.acc1 += reading
        self.count1 += 1

    def get_average(self):
        """The average reading is the accumulators divided by the number of readings taken."""
        return (self.acc0 + self.acc1) / (self.count0 + self.count1)

    def shift(self):
        """Copies the second accumulator into the first, and clears the second accumulator."""
        self.acc0 = self.acc1
        self.acc1 = 0
        self.count0 = self.count1
        self.count1 = 0


def main():
    port_name = find_serial_device()
    if port_name:
        try:
            ser = serial.Serial(port_name, timeout=0.2)
            # discard anything hanging around in the hardware buffer
            ser.reset_input_buffer()
            #reset_fluke_meter(ser)
            # set up time watch variable
            tp = 0
            # set up accumulators, for averaging
            acc = Accumulators()
            while True:
                reading = read_fluke_display(ser)
                acc.add(reading)
                time.sleep(0.1)
                tn = int(time.time())
                if tn != tp:
                    # output the mean of the accumulators (2 seconds of readings)
                    print(f'{acc.get_average():.5g}')
                    # advance the accumulator for fresh readings
                    acc.shift()
                    tp = tn
        except KeyboardInterrupt:
            print(f"fluke_reader.py, main(): Interrupted.", file=sys.stderr)
        except:
            print(f"fluke_reader.py, main(): Connection failed, exiting.", file=sys.stderr)
        finally:
            # make sure we have closed the port if it was opened
            if 'ser' in locals():
                ser.close()
    else:
        print(f"Couldn't find a serial comms port to communicate with the meter.", file=sys.stderr)


if __name__ == '__main__':
    main()
