#!/usr/bin/env python3

#Convert values into display coordinates, where the display is 800x600 pixels (graphics to be 700x500 to leave space):
##we'll make the x axis (time) from 0 to 698:
#####Where 0 pixel = 0ms and 699pixel = 40ms
#########x = int(t/40.0*698)
##we'll make the vertical axis y (Voltage) from 0 to 499 pixels:
#####Where 0 pixel = 400V and 498pixel = -400V (negative because axis y goes down)

import sys

TIME_SHIFT = 00.0          # milliseconds time axis shift (positive values move '0ms' towards the right)
TIME_SCALE = 4.0           # milliseconds per division (10 horizontal divisions)
Y0_SCALE   = 200.0         # volts/amps/watts per division (8 vertical divisions)
Y1_SCALE   = 200.0         # volts/amps/watts per division (8 vertical divisions)
Y2_SCALE   = 200.0         # volts/amps/watts per division (8 vertical divisions)
Y3_SCALE   = 200.0         # volts/amps/watts per division (8 vertical divisions)
PIXELS_PER_DIVISION = 70   # size of each division in terms of display pixels

def main():
    for line in sys.stdin: #receive data from standard input
        try:
            t, c0, c1, c2, c3 = line.split() # take this line and split on whitespace
            x = int((float(t) + TIME_SHIFT)*PIXELS_PER_DIVISION/TIME_SCALE) % 700
            # do other coordinates y1 = vcv
            y0 = int(-float(c0)*PIXELS_PER_DIVISION/Y0_SCALE) + 250
            y1 = int(-float(c1)*PIXELS_PER_DIVISION/Y1_SCALE) + 250
            y2 = int(-float(c2)*PIXELS_PER_DIVISION/Y2_SCALE) + 250
            y3 = int(-float(c3)*PIXELS_PER_DIVISION/Y3_SCALE) + 250
            print(x, y0, y1, y2, y3)
        except ValueError:
            # if stuff goes wrong, deal with it here
            1
        #print('{} {int(t/40.0*699)} {:10.3f} {:10.3f} {:10.3f}')



if __name__ == '__main__':
    main()
