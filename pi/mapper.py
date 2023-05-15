#!/usr/bin/env python3

# Convert values into display coordinates, where the display is 800x600 pixels
# (graphics to be 700x500 to leave space):
# we'll make the x axis (time) from 0 to 699:
# Where 0 pixel = 0ms and 699pixel = 40ms
# x = int(t/40.0*699)
# we'll make the vertical axis y (Voltage) from 0 to 479 pixels:
# Where 0 pixel = 400V and 479pixel = -400V (negative because axis y goes down)

import sys
import signal
import settings


def bound(lower, upper, value):
    return max(lower, min(upper, value))

def main():
   # load settings into st object from settings.json
   st = settings.Settings()
   ymax = st.y_pixels-1
   for line in sys.stdin: # receive data from standard input
        try:
            ws = line.split()    # take this line and split on whitespace
            t, c0, c1, c2, c3 = ws[:5]
            # % st.x_pixels forces x coordinate to be between 0 and 699
            x = int((float(t) + st.time_shift) \
                        * st.horizontal_pixels_per_division/st.time_axis_per_division) % st.x_pixels
            # % st.y_pixels forces y coordinate to be between 0 and 479
            y0 = bound(0, ymax, \
                    (int(-float(c0) * st.vertical_pixels_per_division/st.voltage_axis_per_division) \
                           + st.half_y_pixels))
            y1 = bound(0, ymax, \
                    (int(-float(c1) * st.vertical_pixels_per_division/st.current_axis_per_division) \
                           + st.half_y_pixels))
            y2 = bound(0, ymax, \
                    (int(-float(c2) * st.vertical_pixels_per_division/st.power_axis_per_division) \
                           + st.half_y_pixels))
            y3 = bound(0, ymax, \
                    (int(-float(c3) * st.vertical_pixels_per_division/st.earth_leakage_current_axis_per_division) \
                           + st.half_y_pixels))
            if ws[-1] == 'END_FRAME':
                # negative number at end is a flag in numerical form to indicate that this is the last 
                # sample of the current frame
                print(f'{x} {y0} {y1} {y2} {y3} -1')
                sys.stdout.flush()
            else:
                print(f'{x} {y0} {y1} {y2} {y3}')

        except ValueError:
            # if stuff goes wrong, deal with it here
            print("mapper.py: Failed to process coordinates.", file=sys.stderr)



if __name__ == '__main__':
    main()
