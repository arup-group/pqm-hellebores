#!/usr/bin/env python3

# Reset time t=0 in response to signal event eg voltage crossing zero
# Time offset other sample readings with respect to the trigger

import sys
import signal
import settings


BUFFER_SIZE = 65535          # size of circular sample buffer


class Buffer:
    buf = None           # numpy array, BUFFER_SIZE * 5 (of float)
    fp = 0               # front pointer of frame
    tp = 0               # trigger pointer (somewhere between front and rear)
    rp = 0               # rear pointer of frame
    sp = 0               # storage pointer (new samples)
    triggered = False    # trigger flag
    # when there is a successful trigger, the trigger_test_fn will return an estimate
    # of the fractional time offset between samples when the trigger took place.
    interpolation_fraction = 0.0
    # trigger_test_fn when defined takes two arguments, current and previous samples
    # returns True or False depending on whether a trigger criterion (defined inside
    # the function) is met
    trigger_test_ch = 3
    trigger_test_fn = None


    def __init__(self):
        self.buf = [ [0.0, 0.0, 0.0, 0.0, 0.0] for i in range(BUFFER_SIZE) ]

    def reset(self, test_fn, test_ch):
        self.trigger_test_fn = test_fn
        self.trigger_test_ch = test_ch
     

    # the storage location is determined by the input pointer sp, which is not intended
    # to be manipulated other than here.
    def store_line(self, line):
        try:
            self.buf[self.sp % BUFFER_SIZE] = [ float(w) for w in line.split() ]
        except:
            print(f"trigger.py, store_line(): Couldn't interpret '{line}'.", file=sys.stderr)
        self.sp = self.sp + 1 


    # call this to check if recent samples from tp pointer onwards cause a trigger
    def trigger_test(self):
        while self.tp < self.sp:
            self.triggered, self.interpolation_fraction = \
                   self.trigger_test_fn(self.buf[(self.tp - 1) % BUFFER_SIZE][self.trigger_test_ch], \
                                            self.buf[self.tp % BUFFER_SIZE][self.trigger_test_ch])
            if self.triggered:
                self.fp = self.tp + st.post_trigger_samples
                self.rp = self.tp - st.pre_trigger_samples
                self.tp = self.tp + st.holdoff_samples
                return True
            self.tp = self.tp + 1
        return False

    # see if we have stored enough post-trigger samples to commence output
    def output_ready(self):
        if self.triggered and self.sp >= self.fp:
            return True
        else:
            return False

    def generate_output(self):
        # output the correct array slice with a time shift
        shift = 1.0 - self.rp - st.pre_trigger_samples - self.interpolation_fraction
        end_mark = ''
        for s in range(self.rp, self.fp):
            sample = self.buf[s % BUFFER_SIZE]
            # modify the time stamps
            timestamp = st.interval * (s + shift)
            if s == self.fp - 1:
                end_mark = '*END*'
            print('{:12.4f} {:10.3f} {:10.5f} {:10.3f} {:12.7f} {}'.format(timestamp, *sample[1:], end_mark))
        sys.stdout.flush()
 

def via_trigger(line, buf):
    buf.store_line(line)
    if buf.triggered == False:
        buf.trigger_test()
    elif buf.output_ready():
        buf.generate_output()
        buf.triggered = False


def pass_through(line, buf):
    print(line)


def receive_new_settings(buf):
    global st, process_fn
    
    # interpolation fraction
    def i_frac(s1, s2, threshold):
        if s1 == s2:
            return 0.0
        else:
            return (threshold-s1)/(s2-s1)

    def trigger_fn_generator(slope, threshold):
        # the lambda expressions in this function create closures (customised functions)
        # that are sent into the buffer for trigger detection
        if slope == 'rising':
            return lambda s1, s2: (True, i_frac(s1,s2,threshold)) if s1 <= threshold \
                       and s2 >= threshold else (False, 0.0)
        elif slope == 'falling':
            return lambda s1, s2: (True, i_frac(s1,s2,threshold)) if s1 >= threshold \
                       and s2 <= threshold else (False, 0.0)
        else:
            return None
 
    if st.trigger_mode == 'freerun':
        process_fn = pass_through
    elif st.trigger_mode == 'sync':
        process_fn = via_trigger
        buf.reset(trigger_fn_generator(st.trigger_slope, 0.0), 1) 
    elif st.trigger_mode == 'inrush':
        buf.reset(trigger_fn_generator(st.trigger_slope, st.trigger_level), 3)
    else:
        print("trigger.py, reset(): trigger_mode not recognised, defaulting to sync.", file=sys.stderr)
        process_fn = via_trigger
        buf.reset(trigger_fn_generator(st.trigger_slope, 0.0), 1) 


def main():
    global st, process_fn
    # we make a buffer to temporarily hold a history of samples -- this allows us to output
    # a frame of waveform that includes samples 'before the trigger'
    buf = Buffer()

    # load settings into st object
    st = settings.Settings(lambda: receive_new_settings(buf))
    
    # setup process_fn and set correct trigger condition
    receive_new_settings(buf)

    # read data from standard input
    try:
        for line in sys.stdin:
            # the process_fn that will be executed will change dynamically depending on 
            # trigger settings. This is setup in 'receive_new_settings'
            process_fn(line.rstrip(), buf)

    except ValueError:
        print(f"trigger.py, main(): Failed to read contents of line '{line}'.", file=sys.stderr)



if __name__ == '__main__':
    main()


