#!/usr/bin/env python3

# Reset time t=0 in response to signal event eg voltage crossing zero
# Interpolate sample readings to centre the subsequent time samples on t=0

import sys

OUTPUT_FRAME_LENGTH = 100.0      # milliseconds
PRE_TRIGGER = 10.0               # percent
INPUT_BUFFER_SIZE = 65535        # size of pre-trigger sample buffer
 

def trigger_detect(s0, s1, ch, threshold, direction):
    trigger = False
    if direction == 'rising':
        trigger = (s1[ch] > threshold and s0[ch] < threshold)
    elif direction == 'falling':
        trigger = (s1[ch] < threshold and s0[ch] > threshold) 
    elif direction == 'either':
        trigger = ((s1[ch] > threshold and s0[ch] < threshold) or \
            (s1[ch] < threshold and s0[ch] > threshold)) 
    else:
        print('trigger_detect(): direction option not implemented', file=sys.stderr)
    return trigger

def prev_index(index):
    return (index-1) % INPUT_BUFFER_SIZE

def next_index(index):
    return (index+1) % INPUT_BUFFER_SIZE

def main():
    # we make a buffer to temporarily hold a history of samples -- this allows output
    # of information 'before the trigger'
    buf = []
    for i in range(INPUT_BUFFER_SIZE):     # pre-charge the buffer with zeros
        buf.append([0.0, 0.0, 0.0, 0.0, 0.0])     

    # buffer has size INPUT_BUFFER_SIZE
    # these are the index pointers for the current (p1) and immediately previous (p0) samples
    p0 = 0
    p1 = 1

    # trigger conditions
    direction = 'rising'
    threshold = 0.0
    ch = 4

    # read the first couple of lines to figure out sample interval
    try:
        t0 = [float(w) for w in sys.stdin.readline().split()][0]
        t1 = [float(w) for w in sys.stdin.readline().split()][0]
    except ValueError:
        print('trigger.py, main(): Error reading first two lines.', file=sys.stderr)
        sys.exit(1)
    interval = t1 - t0
 
    # initialise total samples and pre-samples required 
    # and initialise output counter
    output_samples = int(OUTPUT_FRAME_LENGTH / interval)
    output_pre_samples = int(output_samples * PRE_TRIGGER / 100.0)
    oi = 0    # output index

    # flag for controlling when output is required
    triggered = False
    for line in sys.stdin:
        line = line.rstrip()
        try:
            # we store each incoming line in a circular buffer
            buf[p1] = [float(w) for w in line.split()]
        except ValueError:
            print('trigger.py, main(): Failed to read contents of line "' + line + '".', file=sys.stderr)

        if not triggered and trigger_detect(buf[p0], buf[p1], ch, threshold, direction): 
            # ok, new trigger, let's go
            triggered = True
            pre_trigger_index = (p1 - output_pre_samples) % INPUT_BUFFER_SIZE
            # print out all the pre-trigger contents of buffer
            # this will do nothing if the PRE_TRIGGER % is zero
            print('**** PRE-TRIGGER ****')
            for i in range(output_pre_samples):
                print('{:10.3f} {:10.3f} {:10.3f} {:10.3f} {:10.3f}'.format((oi - output_pre_samples)*interval,\
                         *buf[(pre_trigger_index + oi) % INPUT_BUFFER_SIZE][1:]))
                oi = oi + 1
            print('**** TRIGGER ****')                    

        # if a trigger occurred, continue to print out post-trigger samples, as they arrive 
        if triggered:
            print('{:10.3f} {:10.3f} {:10.3f} {:10.3f} {:10.3f}'.format((oi - output_pre_samples)*interval, *buf[p1][1:]))
            oi = oi + 1

        # if we've finished a frame of data, clear the trigger (which stops the output)
        if oi*interval >= OUTPUT_FRAME_LENGTH:
            triggered = False
            oi = 0

        # increment buffer pointers
        p0 = p1              # last sample
        p1 = next_index(p1)  # next sample


if __name__ == '__main__':
    main()


