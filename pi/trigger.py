#!/usr/bin/env python3

# Reset time t=0 in response to signal event eg voltage crossing zero
# Time offset other sample readings with respect to the trigger

import sys
import signal
import settings


INPUT_BUFFER_SIZE = 65535          # size of circular sample buffer


def trigger_gate(buf, ch, threshold, hysteresis, transition_gate, gate_number):

    def qualify(buf, ch, threshold, side):
        if side == 'L':
            qual = buf.peek()[ch+1] <= threshold
            #qual = buf[i][ch+1] <= threshold
        elif side == 'H':
            qual = buf.peek()[ch+1] >= threshold
            #qual = buf[i][ch+1] >= threshold
        return qual

    if qualify(buf, ch, threshold, hysteresis[gate_number]):
        gate_number = gate_number + 1
    # gate count transition_gate is special because it is the potential trigger position.
    # if qualify fails when gate_number == transition_gate, we keep the counter at
    # transition_gate because the pattern might succeed on subsequent samples.
    # if gate_number is any other value then the pattern is not satisfied, the trigger
    # qualification has failed and we set the gate counter back to zero again.
    elif gate_number != transition_gate:
        gate_number = 0

    return gate_number
 

class Buffer:
    buf = []
    ii = 0        # input index, for loading the buffer
    oi = 0        # output index, for draining the buffer
  
    def __init__(self):
        self.clear()

    # the storage location is determined by the input pointer, which is not intended
    # to be manipulated other than here.
    def store(self, samples):
        self.buf[self.ii] = samples
        self.ii = (self.ii + 1) % INPUT_BUFFER_SIZE

    # the following functions all operate/manipulate the output pointer, which can be
    # moved depending on the trigger logic required
    def shift_pointer(self, offset):
        self.oi = (self.oi + offset) % INPUT_BUFFER_SIZE

    def reset_pointer(self):
        self.oi = self.ii

    # returns sample of 4 channels
    def peek(self):      
        return self.buf[self.oi]

    def peek_previous(self):
        poi = (self.oi - 1) % INPUT_BUFFER_SIZE
        return self.buf[poi] 

    # drains -- returns sample of 4 channels and then advances the output pointer
    def drain(self):    
        out = self.buf[self.oi]
        self.oi = (self.oi + 1) % INPUT_BUFFER_SIZE
        return out

    def drained(self):
        return self.oi == self.ii
 
    def clear(self):
        for i in range(INPUT_BUFFER_SIZE):     # pre-charge the buffer with zeros
            self.buf.append([0.0, 0.0, 0.0, 0.0, 0.0])     


# note that s1 and s2 are arrays of 1 sample of all input channels
def interpolate(s1, s2, frac):
    return [ s1[i]*frac + s2[i]*(1-frac) for i in [0,1,2,3] ]


def main():
    # we make a buffer to temporarily hold a history of samples -- this allows us to output
    # a frame of waveform that includes samples 'before the trigger'
    buf = Buffer()

    # load settings into st object
    st = settings.Settings(buf.clear)

    # output counter, number of samples output in current frame
    oc = 0
    # holdoff counter, used to prevent re-triggering for a preset number of samples
    hc = 0
    # the exact trigger position is normally somewhere between samples
    interpolation_fraction = 0.0
    # gate counter, for qualifying hysteresis at the trigger point
    gc = 0
    # flag for controlling when output is required
    triggered = False

    # read data from standard input
    for line in sys.stdin:
        #
        # SPECIAL CASE, NO TRIGGER
        #
        if st.trigger_channel == -1:
            # just pass the data through unaltered
            sys.stdout.write(line)
            continue

        #
        # FILLING BUFFER
        #
        try:
            # we store each incoming line in a circular buffer
            buf.store([float(w) for w in line.split()])

        except ValueError:
            print('trigger.py, main(): Failed to read contents of line "' + line + '".', file=sys.stderr)

        #
        # TRIGGER TEST
        #
        # if hold off is clear, and we are not currently triggered, we check to see if any samples that 
        # haven't yet been tested meet the trigger qualification. If they do they will increase gc, the
        # trigger 'gate counter'. And then, if the gc exceeds a certain threshold, the trigger will be
        # 'fired'.
        while (not triggered) and (hc >= st.holdoff_samples) and (not buf.drained()):
        #while not triggered and not buf.drained():
            gc = trigger_gate(buf, st.trigger_channel, st.trigger_threshold,\
                                  st.trigger_hysteresis, st.trigger_gate_transition, gc)
            if gc == st.trigger_gate_length:
                # trigger qualifications (ie entire hysteresis pattern) has been met!
                triggered = True
                # using linear interpolation, find out the exact timing offset between
                # samples where the trigger position is 
                buf.shift_pointer(-st.trigger_gate_transition)
                s1 = buf.peek()[st.trigger_channel + 1]
                s0 = buf.peek_previous()[st.trigger_channel + 1]
                if s0 == s1:
                    # we need to trap situation where the samples have the same value
                    # to avoid a divide by zero error
                    interpolation_fraction = 0.0
                else:
                    interpolation_fraction = s1 / (s1 - s0)
                # figure out the 'pre-trigger' index and set the output pointer to that position
                # output to stdout will start from this position in the buffer
                buf.shift_pointer(-st.pre_trigger_samples)
                # set the holdoff counter and output counter to zero
                hc, oc = (0, 0)
            else:
                # move on to the next sample
                buf.drain()

        #
        # DRAINING BUFFER 
        #
        # if triggered, print out all outstanding samples up to a count of st.frame_samples
        while triggered and not buf.drained():
            ip = interpolate(buf.peek_previous()[1:], buf.peek()[1:], interpolation_fraction)
            output = (f'{st.interval*(oc-st.pre_trigger_samples) :12.4f} {ip[0] :10.3f} '
                      f'{ip[1] :10.5f} {ip[2] :10.3f} {ip[3] :10.7f}')
            # if we've finished a whole frame of data, mark the last sample and clear the trigger
            if oc >= st.frame_samples:
                print(output + ' END_FRAME')
                # this pushes everything we've printed recently out of the system buffers
                sys.stdout.flush()
                triggered = False
                gc = 0
                # reverse the output index to approx 10% of frame length from the current input 
                # position, up to a maximum of 2ms advance. This positioning helps the trigger 
                # to work in a stable way on a repetitive waveform that has a period that is
                # slightly faster than the display period.
                buf.reset_pointer()
                buf.shift_pointer(-min(st.frame_samples // 10, int(0.002*st.sample_rate)))
            # if we haven't finished yet, print the current sample and advance to the next one
            else:
                print(output)
                buf.drain()
            oc = oc + 1

        # increment the holdoff counter, this has to be done once per input sample/outer loop
        # the holdoff counter prevents early re-triggering.
        hc = hc + 1
 

if __name__ == '__main__':
    main()


