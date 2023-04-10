#!/usr/bin/env python3

# Convert values into display coordinates, where the display is 800x600 pixels (graphics to be 700x500 to leave space):
# we'll make the x axis (time) from 0 to 699:
# Where 0 pixel = 0ms and 699pixel = 40ms
# x = int(t/40.0*699)
# we'll make the vertical axis y (Voltage) from 0 to 479 pixels:
# Where 0 pixel = 400V and 479pixel = -400V (negative because axis y goes down)

import sys
import signal
import json


def get_settings():
    global time_axis_per_division, time_axis_divisions, time_axis_pre_trigger_divisions, voltage_axis_per_division,\
               current_axis_per_division, power_axis_per_division, earth_leakage_current_axis_per_division,\
               vertical_axis_divisions, horizontal_pixels_per_division, vertical_pixels_per_division, time_shift, x_pixels,\
               y_pixels, half_y_pixels
    try:
        f = open("settings.json", "r")
        js = json.loads(f.read())
        f.close()
        time_axis_per_division                   = js['time_axis_per_division']
        time_axis_divisions                      = js['time_axis_divisions']
        time_axis_pre_trigger_divisions          = js['time_axis_pre_trigger_divisions']
        voltage_axis_per_division                = js['voltage_axis_per_division']
        current_axis_per_division                = js['current_axis_per_division']
        power_axis_per_division                  = js['power_axis_per_division']
        earth_leakage_current_axis_per_division  = js['earth_leakage_current_axis_per_division']
        vertical_axis_divisions                  = js['vertical_axis_divisions']
        horizontal_pixels_per_division           = js['horizontal_pixels_per_division']
        vertical_pixels_per_division             = js['vertical_pixels_per_division']
        time_shift                               = time_axis_pre_trigger_divisions * time_axis_per_division
        x_pixels                                 = time_axis_divisions * horizontal_pixels_per_division
        y_pixels                                 = vertical_axis_divisions * vertical_pixels_per_division
        half_y_pixels                            = y_pixels // 2
    except:
        print("mapper.py, get_settings(): couldn't read settings.json, using defaults.", file=sys.stderr)
        time_axis_per_division                   = 4.0
        time_axis_divisions                      = 10
        time_axis_pre_trigger_divisions          = 2
        voltage_axis_per_division                = 200.0
        current_axis_per_division                = 200.0
        power_axis_per_division                  = 200.0
        earth_leakage_current_axis_per_division  = 200.0
        vertical_axis_divisions                  = 8
        horizontal_pixels_per_division           = 70
        vertical_pixels_per_division             = 60
        time_shift                               = time_axis_pre_trigger_divisions * time_axis_per_division
        x_pixels                                 = time_axis_divisions * horizontal_pixels_per_division
        y_pixels                                 = vertical_axis_divisions * vertical_pixels_per_division
        half_y_pixels                            = y_pixels // 2 


def settings_handler(signum, frame):
   get_settings()


def main():
   global time_axis_per_division, time_axis_divisions, time_axis_pre_trigger_divisions, voltage_axis_per_division,\
               current_axis_per_division, power_axis_per_division, earth_leakage_current_axis_per_division,\
               vertical_axis_divisions, horizontal_pixels_per_division, vertical_pixels_per_division, time_shift, x_pixels,\
               y_pixels, half_y_pixels
   get_settings()
   # if we receive 'SIGUSR1' signal (on linux) updated settings will be read from settings.json
   if sys.platform == 'linux':
       signal.signal(signal.SIGUSR1, settings_handler)

   for line in sys.stdin: # receive data from standard input
        try:
            t, c0, c1, c2, c3 = line.split() # take this line and split on whitespace
            # % X_PIXELS forces x coordinate to be between 0 and 699
            x = int((float(t) + time_shift)*horizontal_pixels_per_division/time_axis_per_division) % x_pixels
            # % Y_PIXELS forces y coordinate to be between 0 and 479
            y0 = (int(-float(c0)*vertical_pixels_per_division/voltage_axis_per_division) + half_y_pixels) % y_pixels
            y1 = (int(-float(c1)*vertical_pixels_per_division/current_axis_per_division) + half_y_pixels) % y_pixels
            y2 = (int(-float(c2)*vertical_pixels_per_division/power_axis_per_division) + half_y_pixels) % y_pixels
            y3 = (int(-float(c3)*vertical_pixels_per_division/earth_leakage_current_axis_per_division) + half_y_pixels) % y_pixels
            print(x, y0, y1, y2, y3)
        except ValueError:
            # if stuff goes wrong, deal with it here
            print("Failed to process coordinates.", file=sys.stderr)



if __name__ == '__main__':
    main()
