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
    """Truncates a value to within a bounded minimum and maximum range"""
    return max(lower, min(upper, value))

def main():
   # load settings into st object from settings.json
   st = settings.Settings()
   ymax = st.y_pixels-1
   for line in sys.stdin: # receive data from standard input
        try:
            ws = line.split()    # take this line and split on whitespace
            # time, channels 0 to 3, end marker may be present at ws[5]
            t, c0, c1, c2, c3 = ws[:5]
            if ws[-1] == '*END*':
                em = '*END*'
            else:
                em = ''              
            # % st.x_pixels forces x coordinate to be between 0 and 699
            x = int(((float(t) + st.time_shift) 
                     * st.horizontal_pixels_per_division/st.time_axis_per_division)
                    % st.x_pixels)
            # % st.y_pixels forces y coordinate to be between 0 and 479
            y0 = bound(0, ymax, 
                       (int(- float(c0)
                            * st.vertical_pixels_per_division
                            / st.voltage_axis_per_division) 
                       + st.half_y_pixels))
            y1 = bound(0, ymax,
                       (int(- float(c1)
                            * st.vertical_pixels_per_division
                            /st.current_axis_per_division)
                       + st.half_y_pixels))
            y2 = bound(0, ymax,
                       (int(- float(c2)
                            * st.vertical_pixels_per_division
                            / st.power_axis_per_division) 
                       + st.half_y_pixels))
            y3 = bound(0, ymax,
                       (int(- float(c3)
                            * st.vertical_pixels_per_division
                            / st.earth_leakage_current_axis_per_division) 
                       + st.half_y_pixels))
            print(f'{x :4d} {y0 :4d} {y1 :4d} {y2 :4d} {y3 :4d} {em}')
            # make sure we get a clean flush of the buffer so that single shot (eg inrush) events
            # will be immediately displayed
            if em == '*END*':
                sys.stdout.flush()

        except ValueError:
            print('mapper.py: Failed to process coordinates.', file=sys.stderr)



if __name__ == '__main__':
    main()
