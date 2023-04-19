#!/usr/bin/env python3

# Reset time t=0 in response to signal event eg voltage crossing zero
# Time offset other sample readings with respect to the trigger

import sys
import signal
import json

INPUT_BUFFER_SIZE = 65535                   # size of circular sample buffer

def get_settings():
    global sample_rate, time_axis_per_division, pre_trigger_time, post_trigger_time, trigger_direction,\
               trigger_channel, trigger_threshold, interval, post_trigger_samples, pre_trigger_samples, \
               holdoff_threshold
    try:
        f = open("settings.json", "r")
        js = json.loads(f.read())
        f.close()
        sample_rate             = js['sample_rate']
        time_axis_per_division  = js['time_axis_per_division']
        pre_trigger_time        = js['time_axis_pre_trigger_divisions'] * time_axis_per_division 
        post_trigger_time       = (js['time_axis_divisions'] - js['time_axis_pre_trigger_divisions']) * js['time_axis_per_division']
        trigger_direction       = js['trigger_direction']
        trigger_channel         = js['trigger_channel']
        trigger_threshold       = js['trigger_threshold']
        interval                = 1000.0 / js['sample_rate']
        post_trigger_samples    = int(post_trigger_time / interval)
        pre_trigger_samples     = int(pre_trigger_time / interval)
        # we set a hold-off threshold (minimum number of samples to next trigger) to be slightly less
        # than one full screenful of data
        holdoff_threshold       = 0.9 * (pre_trigger_samples + post_trigger_samples)

    except:
        print("trigger.py, get_settings(): couldn't read settings.json, using defaults.", file=sys.stderr)
        sample_rate             = 7812.5
        time_axis_per_division  = 4.0                    # milliseconds
        pre_trigger_time        = 4.0                    # milliseconds
        post_trigger_time       = 36.0                   # milliseconds
        trigger_direction       = 'rising'
        trigger_channel         = 3
        trigger_threshold       = 0.0
        interval                = 1000.0 / 7812.5
        post_trigger_samples    = int(post_trigger_time / interval)
        pre_trigger_samples     = int(pre_trigger_time / interval)
        holdoff_threshold       = 0.9 * (pre_trigger_samples + post_trigger_samples)

 
def settings_handler(signum, frame):
    global buf
    get_settings()
    buf = clear_buffer()

def prev_index(index):
    return (index-1) % INPUT_BUFFER_SIZE

def next_index(index):
    return (index+1) % INPUT_BUFFER_SIZE


# three samples, channel selector and threshold/direction criteria
# returns true/false 
def trigger_detect(buf, ii, ch, threshold, direction):
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


def clear_buffer():
    buf = []
    for i in range(INPUT_BUFFER_SIZE):     # pre-charge the buffer with zeros
        buf.append([0.0, 0.0, 0.0, 0.0, 0.0])     
    return buf


def main():
    global sample_rate, time_axis_per_division, pre_trigger_time, post_trigger_time, trigger_direction,\
               trigger_channel, trigger_threshold, interval, post_trigger_samples, pre_trigger_samples, buf, \
               holdoff_threshold
    get_settings()
    # we make a buffer to temporarily hold a history of samples -- this allows us to output
    # waveform samples 'before the trigger'
    buf = clear_buffer()

    # if we receive 'SIGUSR1' signal (on linux) updated settings will be read from settings.json
    if sys.platform == 'linux':
        signal.signal(signal.SIGUSR1, settings_handler)

    ii = 0    # input index (into buf, filling buffer) 
    oi = 0    # output index (out of buf, draining buffer)
    # output counter, number of samples output in current frame
    oc = pre_trigger_samples + post_trigger_samples
    # the exact trigger position is normally somewhere between samples
    interpolation_fraction = 0.0

    # flag for controlling when output is required
    triggered = False

    # read data from standard input
    for line in sys.stdin:
        # FILLING BUFFER
        try:
            # we store each incoming line, whether triggered or not, in a circular buffer
            buf[ii] = [float(w) for w in line.split()]
            ii = next_index(ii)

        except ValueError:
            print('trigger.py, main(): Failed to read contents of line "' + line + '".', file=sys.stderr)

        # DRAINING BUFFER 
        # if hold off is clear, and we are not currently triggered, check to see if any outstanding 
        # samples qualify for a trigger
        if (oc >= holdoff_threshold) and not triggered:
            while oi != ii:
                triggered, interpolation_fraction = trigger_detect(buf, oi, trigger_channel,\
                                                        trigger_threshold, trigger_direction) 
                if triggered:
                    # we have found a valid trigger
                    # figure out the 'pre-trigger' index and set the output pointer to that position
                    # set an output sample counter, and then exit this loop
                    oi = (oi - pre_trigger_samples) % INPUT_BUFFER_SIZE
                    oc = 0 
                    break
                oi = next_index(oi)  
   
        # if triggered, print out all buffered/outstanding samples up to the input pointer
        if triggered:
            while oi != ii:
                print('{:10.3f} {:10.3f} {:10.3f} {:10.3f} {:10.3f}'.format(interval *\
                          (oc - pre_trigger_samples), *interpolate(buf[prev_index(oi)][1:],\
                          buf[oi][1:], interpolation_fraction)))
                oi = next_index(oi)
                oc = oc + 1

        # if we've finished a whole frame of data, clear the trigger and back up the output
        # index counter by one division
        if oc >= pre_trigger_samples + post_trigger_samples:
            triggered = False
            oi = (oi - int(sample_rate * time_axis_per_division/1000)) % INPUT_BUFFER_SIZE

if __name__ == '__main__':
    main()


