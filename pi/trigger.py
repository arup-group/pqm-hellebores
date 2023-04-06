#!/usr/bin/env python3

# Reset time t=0 in response to signal event eg voltage crossing zero
# Time offset other sample readings with respect to the trigger

import sys

PRE_TRIGGER_TIME = 10.0                     # milliseconds
POST_TRIGGER_TIME = 30.0                    # milliseconds
RE_TRIGGER_HOLD_OFF_TIME = (PRE_TRIGGER_TIME + POST_TRIGGER_TIME) * 0.9  # milliseconds, allows slightly early re-trigger
INPUT_BUFFER_SIZE = 65535        # size of pre-trigger sample buffer

# trigger conditions
direction = 'rising'
threshold = 0.0
ch = 4

# returns the time interval between samples
def interval_detect():
    t0 = [float(w) for w in sys.stdin.readline().split()][0]
    t1 = [float(w) for w in sys.stdin.readline().split()][0]
    return t1-t0

# three samples, channel selector and threshold/direction criteria
# returns true/false 
def trigger_detect(s0, s1, s2, ch, threshold, direction):
    trigger = False
    if direction == 'rising':
        trigger = ((s2[ch] > threshold) and (s1[ch] < threshold) and (s0[ch] < s1[ch]))
    elif direction == 'falling':
        trigger = ((s2[ch] < threshold) and (s1[ch] > threshold) and (s0[ch] > s1[ch])) 
    else:
        print('trigger_detect(): selected direction option not implemented', file=sys.stderr)
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

    # figure out sample interval
    try:
        interval = interval_detect()
    except ValueError:
        print('trigger.py, main(): Error reading first two lines.', file=sys.stderr)
        sys.exit(1)
 
    # initialise post-samples and pre-samples required 
    # and initialise output counter
    post_trigger_samples = int(POST_TRIGGER_TIME / interval)
    pre_trigger_samples = int(PRE_TRIGGER_TIME / interval)
    ii = 0    # input index 
    oi = 0    # output index

    # flag for controlling when output is required
    triggered = False
    for line in sys.stdin:
        line = line.rstrip()
        try:
            # we store each incoming line, whether triggered or not, in a circular buffer
            buf[ii] = [float(w) for w in line.split()]
        except ValueError:
            print('trigger.py, main(): Failed to read contents of line "' + line + '".', file=sys.stderr)

        # if not currently triggered, or outside the trigger hold-off time, check to see if latest sample causes a trigger
        if (not triggered or (oi*interval > RE_TRIGGER_HOLD_OFF_TIME)) and trigger_detect(buf[prev_index(prev_index(ii))], buf[prev_index(ii)], buf[ii], ch, threshold, direction): 
            # ok, new trigger, let's go
            triggered = True
            oi = 0
            pre_trigger_index = (ii - pre_trigger_samples) % INPUT_BUFFER_SIZE
            # print out all the pre-trigger contents of buffer
            for i in range(pre_trigger_samples):
                print('{:10.3f} {:10.3f} {:10.3f} {:10.3f} {:10.3f}'.format((oi - pre_trigger_samples)*interval,\
                         *buf[(pre_trigger_index + oi) % INPUT_BUFFER_SIZE][1:]))
                oi = oi + 1

        # if a trigger occurred, continue to print out post-trigger samples, as they arrive 
        if triggered:
            print('{:10.3f} {:10.3f} {:10.3f} {:10.3f} {:10.3f}'.format((oi - pre_trigger_samples)*interval, *buf[ii][1:]))
            oi = oi + 1

        # but if we've finished a frame of data, clear the trigger (which stops the output)
        if oi >= (pre_trigger_samples + post_trigger_samples):
            triggered = False

        # increment input index
        ii = next_index(ii)


if __name__ == '__main__':
    main()


