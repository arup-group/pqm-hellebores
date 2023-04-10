#!/usr/bin/env python3

# Reset time t=0 in response to signal event eg voltage crossing zero
# Time offset other sample readings with respect to the trigger

import sys
import signal
import json

INPUT_BUFFER_SIZE = 65535                   # size of circular sample buffer

def get_settings():
    global pre_trigger_time, post_trigger_time, trigger_direction, trigger_channel, trigger_threshold,\
               interval, post_trigger_samples, pre_trigger_samples
    try:
        f = open("settings.json", "r")
        js = json.loads(f.read())
        f.close()
        pre_trigger_time        = js['time_axis_pre_trigger_divisions'] * js['time_axis_per_division']
        post_trigger_time       = (js['time_axis_divisions'] - js['time_axis_pre_trigger_divisions']) * js['time_axis_per_division']
        trigger_direction       = js['trigger_direction']
        trigger_channel         = js['trigger_channel']
        trigger_threshold       = js['trigger_threshold']
        interval                = 1000.0 / js['sample_rate']
        post_trigger_samples    = int(post_trigger_time / interval)
        pre_trigger_samples     = int(pre_trigger_time / interval)
    except:
        print("trigger.py, get_settings(): couldn't read settings.json, using defaults.", file=sys.stderr)
        pre_trigger_time        = 5.0                    # milliseconds
        post_trigger_time       = 35.0                   # milliseconds
        trigger_direction       = 'rising'
        trigger_channel         = 3
        trigger_threshold       = 0.0
        interval                = 1000.0 / 7812.5
        post_trigger_samples    = int(post_trigger_time / interval)
        pre_trigger_samples     = int(pre_trigger_time / interval)
 
def settings_handler(signum, frame):
    get_settings()


def prev_index(index):
    return (index-1) % INPUT_BUFFER_SIZE

def next_index(index):
    return (index+1) % INPUT_BUFFER_SIZE


# three samples, channel selector and threshold/direction criteria
# returns true/false 
def trigger_detect(buf, ii, ch, threshold, direction, interval):
    trigger = False
    interpolation_fraction = 0.0
    ci = ch + 1  # channel index is channel number plus 1 (time is at index 0)
    if direction == 'rising':
        trigger = (buf[ii][ci] > threshold) and (buf[prev_index(ii)][ci] < threshold) and \
                      (buf[prev_index(prev_index(ii))][ci] < threshold)
    elif direction == 'falling':
        trigger = (buf[ii][ci] < threshold) and (buf[prev_index(ii)][ci] > threshold) and \
                      (buf[prev_index(prev_index(ii))][ci] > threshold)
    else:
        print('trigger_detect(): selected direction option not implemented', file=sys.stderr)
    if trigger == True:
        interpolation_fraction = buf[ii][ci] / (buf[ii][ci] - buf[prev_index(ii)][ci])
    return trigger, interpolation_fraction


# note that s1 and s2 are arrays of 1 sample of all input channels
def interpolate(s1, s2, interpolation_fraction):
    interpolated = [0.0, 0.0, 0.0, 0.0]
    for i in range(4):
       interpolated[i] = (s1[i]*interpolation_fraction + s2[i]*(1-interpolation_fraction))
    return interpolated


def main():
    global pre_trigger_time, post_trigger_time, trigger_direction, trigger_channel, trigger_threshold,\
               interval, post_trigger_samples, pre_trigger_samples
    get_settings()
    # if we receive 'SIGUSR1' signal (on linux) updated settings will be read from settings.json
    if sys.platform == 'linux':
        signal.signal(signal.SIGUSR1, settings_handler)

    # we make a buffer to temporarily hold a history of samples -- this allows output
    # of information 'before the trigger'
    buf = []
    for i in range(INPUT_BUFFER_SIZE):     # pre-charge the buffer with zeros
        buf.append([0.0, 0.0, 0.0, 0.0, 0.0])     

    ii = 0    # input buffer index 
    oc = 0    # output counter
    interpolation_fraction = 0.0  # the exact trigger position is normally somewhere between samples

    # flag for controlling when output is required
    triggered = False
    for line in sys.stdin:
        line = line.rstrip()
        try:
            # we store each incoming line, whether triggered or not, in a circular buffer
            buf[ii] = [float(w) for w in line.split()]
        except ValueError:
            print('trigger.py, main(): Failed to read contents of line "' + line + '".', file=sys.stderr)

        # if not currently triggered, check to see if latest sample causes a trigger
        if not triggered:
            triggered, interpolation_fraction = trigger_detect(buf, ii, trigger_channel, trigger_threshold, trigger_direction, interval) 
            if triggered:
                # ok, we have a new trigger, let's go
                pti = (ii - pre_trigger_samples) % INPUT_BUFFER_SIZE
                oc = -pre_trigger_samples 
                # print out all the pre-trigger contents of buffer
                for i in range(pre_trigger_samples):
                   print('{:10.3f} {:10.3f} {:10.3f} {:10.3f} {:10.3f}'.format(oc*interval,\
                             *interpolate(buf[prev_index(pti)][1:], buf[pti][1:], interpolation_fraction)))
                   pti = next_index(pti)
                   oc = oc + 1

        # if we are currently triggered, continue to print out post-trigger samples, as they arrive 
        if triggered:
            print('{:10.3f} {:10.3f} {:10.3f} {:10.3f} {:10.3f}'.format(oc*interval,\
                    *interpolate(buf[prev_index(ii)][1:], buf[ii][1:], interpolation_fraction)))
            oc = oc + 1

        # but if we've finished a whole frame of data, clear the trigger (which stops subsequent output)
        if oc >= post_trigger_samples:
            triggered = False

        # increment input index
        ii = next_index(ii)


if __name__ == '__main__':
    main()


