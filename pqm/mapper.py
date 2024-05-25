#!/usr/bin/env python3

                                                   
#  _ __ ___   __ _ _ __  _ __   ___ _ __ _ __  _   _ 
# | '_ ` _ \ / _` | '_ \| '_ \ / _ \ '__| '_ \| | | |
# | | | | | | (_| | |_) | |_) |  __/ | _| |_) | |_| |
# |_| |_| |_|\__,_| .__/| .__/ \___|_|(_) .__/ \__, |
#                 |_|   |_|             |_|    |___/ 
# 
# Convert values into display coordinates, where the display is 800x480 pixels
# (graphics to be 700x480 to leave space for ui buttons)
# therefore the x axis (time) from 0 to 699, the vertical axis y (voltage, current etc) from 0 to 479 pixels.
# note that y=0 is top of screen, and y=479 is bottom of screen

import sys
import signal
import settings


def main():
   # load settings into st object from settings.json
   st = settings.Settings()
   ymax = st.y_pixels
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
            y0 = (int(- float(c0) * st.vertical_pixels_per_division / st.voltage_axis_per_division) 
                      + st.half_y_pixels)
            y1 = (int(- float(c1) * st.vertical_pixels_per_division /st.current_axis_per_division)
                      + st.half_y_pixels)
            y2 = (int(- float(c2) * st.vertical_pixels_per_division / st.power_axis_per_division) 
                      + st.half_y_pixels)
            y3 = (int(- float(c3) * st.vertical_pixels_per_division / st.earth_leakage_current_axis_per_division) 
                      + st.half_y_pixels)
           
            print(f'{x :4d} {y0 :4d} {y1 :4d} {y2 :4d} {y3 :4d} {em}')
            # make sure we get a clean flush of the buffer so that single shot (eg inrush) events
            # will be immediately displayed
            if em == '*END*':
                sys.stdout.flush()

        except ValueError:
            print('mapper.py: Failed to process coordinates.', file=sys.stderr)



if __name__ == '__main__':
    main()
