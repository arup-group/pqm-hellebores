#!/usr/bin/env python3

# Reset time t=0 in response to signal event eg voltage crossing zero
# Time offset other sample readings with respect to the trigger

import sys
import signal
import settings


INPUT_BUFFER_SIZE = 65535          # size of circular sample buffer


def prev_index(index):
    return (index-1) % INPUT_BUFFER_SIZE

def next_index(index):
    return (index+1) % INPUT_BUFFER_SIZE


def trigger_gate(buf, i, ch, threshold, hysteresis, gate_number):
    global st
    def qualify(buf, i, ch, threshold, side):
        if side == 'L':
            qual = buf[i][ch+1] <= threshold
        elif side == 'H':
            qual = buf[i][ch+1] >= threshold
        return qual

    if qualify(buf, i, ch, threshold, hysteresis[gate_number]):
        gate_number = gate_number + 1
    # gate count TRIGGER_GATE is special because it is the potential trigger threshold.
    # if qualify fails when gc=TRIGGER_GATE, we keep the counter at TRIGGER_GATE because the
    # pattern might succeed on subsequent samples.
    # if gc is any other value then the pattern is not satisfied, the trigger qualification
    # has failed and we start again.
    elif gate_number != st.trigger_gate_transition:
        gate_number = 0

    return gate_number
 

# note that s1 and s2 are arrays of 1 sample of all input channels
def interpolate(s1, s2, interpolation_fraction):
    interpolated = [0.0, 0.0, 0.0, 0.0]
    for i in range(4):
       interpolated[i] = (s1[i]*interpolation_fraction + s2[i]*(1-interpolation_fraction))
    return interpolated


def clear_buffer():
    global buf
    buf = []
    for i in range(INPUT_BUFFER_SIZE):     # pre-charge the buffer with zeros
        buf.append([0.0, 0.0, 0.0, 0.0, 0.0])     


def main():
    global st
    # load settings into st object
    st = settings.Settings(clear_buffer)

    # we make a buffer to temporarily hold a history of samples -- this allows us to output
    # waveform samples 'before the trigger'
    clear_buffer()

    ii = 0    # input index (into buf, filling buffer) 
    oi = 0    # output index (out of buf, draining buffer)
    # output counter, number of samples output in current frame
    oc = 0
    # holdoff counter, used to prevent re-triggering for a preset number of samples
    hc = 0
    # the exact trigger position is normally somewhere between samples
    interpolation_fraction = 0.0
    # gate counter, for tracking hysteresis at the trigger point
    gc = 0
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
        # samples meet the trigger qualification. If they do they will increase gc, the trigger 'gate counter'.
        while not triggered and (hc >= st.holdoff_samples) and (oi != ii):
            gc = trigger_gate(buf, oi, st.trigger_channel, st.trigger_threshold, st.trigger_hysteresis, gc)
            if gc == st.trigger_gate_length:
                # trigger qualifications (ie entire hysteresis pattern) has been met
                triggered = True
                # using linear interpolation, find out the exact timing offset between
                # samples where the trigger position is 
                oi = (oi - st.trigger_gate_transition) % INPUT_BUFFER_SIZE
                s1 = buf[oi][st.trigger_channel + 1]
                s0 = buf[prev_index(oi)][st.trigger_channel + 1]
                if s0 == s1:
                    interpolation_fraction = 0.0
                else:
                    interpolation_fraction = s1 / (s1 - s0)
                # figure out the 'pre-trigger' index and set the output pointer to that position
                # set an output sample counter, and then exit this loop
                oi = (oi - st.pre_trigger_samples) % INPUT_BUFFER_SIZE
                # set the holdoff counter, output counter and gate counter to zero
                hc = 0
                oc = 0
                gc = 0
            else:
                oi = next_index(oi)  
   
        # if triggered, print out all buffered/outstanding samples up to the current input pointer
        while triggered and (oi != ii):
            print('{:10.3f} {:10.3f} {:10.3f} {:10.3f} {:10.3f}'.format(st.interval *\
                      (oc - st.pre_trigger_samples), *interpolate(buf[prev_index(oi)][1:],\
                      buf[oi][1:], interpolation_fraction)))
            oc = oc + 1
            # if we've finished a whole frame of data, clear the trigger and position the output
            # index counter 2ms behind the current input index
            if oc >= st.frame_samples:
                triggered = False
                oi = (ii - int(0.002 * st.sample_rate)) % INPUT_BUFFER_SIZE
            else:
                oi = next_index(oi)
            
        # increment the holdoff counter, this has to be done once per input sample/outer loop
        hc = hc + 1
 

if __name__ == '__main__':
    main()


