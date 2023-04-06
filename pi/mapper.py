#!/usr/bin/env python3

# Convert values into display coordinates, where the display is 800x600 pixels (graphics to be 700x500 to leave space):
# we'll make the x axis (time) from 0 to 699:
# Where 0 pixel = 0ms and 699pixel = 40ms
# x = int(t/40.0*699)
# we'll make the vertical axis y (Voltage) from 0 to 479 pixels:
# Where 0 pixel = 400V and 479pixel = -400V (negative because axis y goes down)

import sys

TIME_SHIFT = 10.0          # milliseconds time axis shift (positive values move '0ms' towards the right)
TIME_SCALE = 4.0           # milliseconds per division (10 horizontal divisions)
Y0_SCALE   = 200.0         # volts/amps/watts per division (8 vertical divisions)
Y1_SCALE   = 200.0         # volts/amps/watts per division (8 vertical divisions)
Y2_SCALE   = 200.0         # volts/amps/watts per division (8 vertical divisions)
Y3_SCALE   = 200.0         # volts/amps/watts per division (8 vertical divisions)
PIXELS_PER_DIVISION = 70   # size of each division in terms of display pixels
X_PIXELS   = 700
Y_PIXELS   = 480

def main():
    for line in sys.stdin: #receive data from standard input
        try:
            t, c0, c1, c2, c3 = line.split() # take this line and split on whitespace
            # % X_PIXELS forces x coordinate to be between 0 and 699
            x = int((float(t) + TIME_SHIFT)*PIXELS_PER_DIVISION/TIME_SCALE) % X_PIXELS
            # % Y_PIXELS forces y coordinate to be between 0 and 479
            y0 = (int(-float(c0)*PIXELS_PER_DIVISION/Y0_SCALE) + 240) % Y_PIXELS
            y1 = (int(-float(c1)*PIXELS_PER_DIVISION/Y1_SCALE) + 240) % Y_PIXELS
            y2 = (int(-float(c2)*PIXELS_PER_DIVISION/Y2_SCALE) + 240) % Y_PIXELS
            y3 = (int(-float(c3)*PIXELS_PER_DIVISION/Y3_SCALE) + 240) % Y_PIXELS
            print(x, y0, y1, y2, y3)
        except ValueError:
            # if stuff goes wrong, deal with it here
            print("Failed to process coordinates.", file=sys.stderr)



if __name__ == '__main__':
    main()
