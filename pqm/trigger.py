#!/usr/bin/env python3


#  _        _                                   
# | |_ _ __(_) __ _  __ _  ___ _ __ _ __  _   _ 
# | __| '__| |/ _` |/ _` |/ _ \ '__| '_ \| | | |
# | |_| |  | | (_| | (_| |  __/ | _| |_) | |_| |
#  \__|_|  |_|\__, |\__, |\___|_|(_) .__/ \__, |
#             |___/ |___/          |_|    |___/ 
#
# Monitors signal and detects signal event eg voltage crossing zero
# Offsets time axis with respect to the trigger (trigger time is t=0)

import sys
import signal
from settings import Settings


READ_CHUNK_SIZE = 64                 # we read input lines in blocks, for efficiency
BUFFER_SIZE = 65536                  # size of circular sample buffer
MAX_FORWARD_READ = BUFFER_SIZE // 4  # maximum reads, post frame end pointer

class Buffer:
    buf = None           # array of 5*floats, ie BUFFER_SIZE * 5
    # Frame pointers are set after trigger pointer is set, in triggered mode,
    # immediately after frame output in free-run mode, and when settings are changed,
    # including in stopped mode.
    # Pointers increase indefinitely. We don't modulo rotate the pointers except when
    # accessing the circular buffer. This is to make it easier to do numeric comparison
    # between pointers and to calculate new frame pointers after each new trigger or
    # after settings have changed.
    frame_startp = 0     # beginning of frame to be output
    frame_endp = 0       # end of frame to be output
    outp = 0             # end of last output
    sp = 0               # storage pointer (advances by 1 for every new sample)
    tp = 0               # trigger pointer (in running mode, this is moved forward when
                         # trigger condition is next satisfied)
    # triggered flag is raised when a new trigger is detected, and lowered after we
    # have output a frame
    triggered = False
    # When there is a successful trigger, the trigger_test_fn will return an estimate
    # of the fractional time offset between samples when the trigger took place.
    # The interpolation fraction is used to create an accurate time offset which helps
    # to stabilise the position of successive waveforms on screen.
    interpolation_fraction = 0.0
    # trigger_test_ch defines the input channel that will be used for triggering
    # normally left on the voltage channel 3, but could be changed.
    # trigger_test_fn when defined takes two arguments, current and previous samples
    # returns True or False depending on whether a trigger criterion (defined inside
    # the function) is met
    trigger_test_ch = 3
    trigger_test_fn = None
    # a function reference is assigned to process_fn when new settings are received
    process_fn = lambda line: 0  # dummy function -- this will be replaced at runtime

    def __init__(self, size=BUFFER_SIZE):
        """buffer memory initialised with empty data"""
        # *** performance optimisation: could consider memoryview object here ***
        self.size = size
        self.buf = [ [0.0, 0.0, 0.0, 0.0, 0.0] for i in range(size) ]


    def setup_trigger(self, test_fn, test_ch):
        """sets updated trigger test function and trigger channel"""
        self.trigger_test_fn = test_fn
        self.trigger_test_ch = test_ch


    def store_line(self, line):
        """store a line of new data into the next buffer location"""
        # the storage location is determined by the input pointer sp, which is not intended
        # to be manipulated other than here.
        try:
            self.buf[self.sp % self.size] = [ float(w) for w in line.split() ]
        except ValueError:
            self.buf[self.sp % self.size] = [ 0.0, 0.0, 0.0, 0.0, 0.0 ]
            print(f"trigger.py, store_line(): Couldn't interpret '{line}'.",
                file=sys.stderr)
        self.sp += 1


    def update_frame_markers(self):
        """Call this after a frame has been output or a new trigger is detected, to set the frame
        markers for the next output."""
        # in running mode, we move both frame markers forward
        if st.run_mode == 'running':
            if st.trigger_mode == 'sync' or st.trigger_mode == 'inrush':
                # make sure the start marker does not precede the end marker of the previous output
                self.frame_startp = max(self.outp, self.tp - st.pre_trigger_samples)
                self.frame_endp = self.tp + st.post_trigger_samples - 1
            elif st.trigger_mode == 'freerun':
                # in freerun mode, we just run frames back to back with one another
                self.frame_startp = self.frame_endp
                self.frame_endp = self.frame_start_p + st.pre_trigger_samples \
                                      + st.post_trigger_samples - 1
        # in stopped mode, we move the existing frame boundaries around the current trigger
        else:
            self.frame_startp = self.tp - st.pre_trigger_samples
            self.frame_endp = self.tp + st.post_trigger_samples - 1

    def reprime_trigger(self):
        """Set the next trigger position to be the greater of the end of the previous frame
        and the hold-off time (dependent on the time axis, so we don't trigger too early in the
        frame)"""
        self.tp = self.frame_endp + st.holdoff_samples
        self.triggered = False


    def trigger_test(self):
        """call this to check if recent samples from self.tp onwards cause a trigger"""
        while self.tp < self.sp:
            self.triggered, self.interpolation_fraction = (
                self.trigger_test_fn(
                    # the trigger test function takes the channel reading for
                    # two successive samples and compares them against the trigger
                    # criteria
                    self.buf[(self.tp - 1) % self.size][self.trigger_test_ch], 
                    self.buf[self.tp % self.size][self.trigger_test_ch]))
            self.tp += 1
            if self.triggered == True:
                self.update_frame_markers()
                break
        return self.triggered


    def ready_for_output(self):
        """Check if we have triggered and/or we have stored enough samples to
        commence output"""
        return True if self.sp >= self.frame_endp else False


    def output_frame(self):
        """output the correct array slice with a time shift"""
        # exact trigger position occurred between the sample self.tp - 1 and self.tp
        # this needs to be t = 0
        # at the moment, the additional offset of 1 sample is unexplained.
        timeshift = - (self.tp - 2 + self.interpolation_fraction)
        for s in range(self.frame_startp, self.frame_endp):
            sample = self.buf[s % self.size]
            # modify the timestamp
            timestamp = st.interval * (s + timeshift)
            # if it's the last sample in the frame, add an 'END' marker
            em = '*END*' if s == self.frame_endp - 1 else ''
            print(f'{timestamp:12.4f} {sample[1]:10.3f} '
                  f'{sample[2]:10.5f} {sample[3]:10.3f} {sample[4]:12.7f} {em}')
        self.outp = self.frame_endp
        sys.stdout.flush()


def via_trigger(line, buf):
    # store samples even in stopped mode up to MAX_SAMPLES
    if buf.sp - buf.frame_endp < MAX_FORWARD_READ:
        buf.store_line(line)
        if not buf.triggered:
            buf.trigger_test()


def pass_through(line, buf):
    # pretty simple, no triggering at all, just copy the input to the output
    if buf.sp - buf.frame_endp < MAX_FORWARD_READ:
        buf.store_line(line)


def receive_new_settings(buf):
    global st
    
    # interpolation fraction
    def i_frac(s1, s2, threshold):
        if s1 == s2:
            return 0.0
        else:
            return (threshold-s1)/(s2-s1)

    def trigger_fn_generator(slope, threshold):
        # the lambda expressions in this function create closures (customised functions)
        # that are stored in the buffer object for trigger detection
        if slope == 'rising':
            return (lambda s1, s2:
                       (True, i_frac(s1,s2,threshold))
                           if s1 <= threshold and s2 >= threshold
                       else (False, 0.0))
        elif slope == 'falling':
            return (lambda s1, s2:
                       (True, i_frac(s1,s2,threshold))
                           if s1 >= threshold and s2 <= threshold
                       else (False, 0.0))
        else:
            return None

    # we define the signal processing function 'process_fn' to point to different
    # behaviours depending on the mode of triggering that is specified
    if st.trigger_mode == 'freerun':
        buf.process_fn = lambda line, buf=buf: pass_through(line, buf)
    elif st.trigger_mode == 'sync':
        buf.process_fn = lambda line, buf=buf: via_trigger(line, buf)
        buf.setup_trigger(trigger_fn_generator(st.trigger_slope, 0.0), 1)
    elif st.trigger_mode == 'inrush':
        buf.process_fn = lambda line, buf=buf: via_trigger(line, buf)
        buf.setup_trigger(trigger_fn_generator(st.trigger_slope, st.trigger_level), 3)
    else:
        print(
            "trigger.py, trigger_fn_generator(): Trigger_mode not recognised, defaulting to sync.",
            file=sys.stderr)
        buf.process_fn = lambda line, buf=buf: via_trigger(line, buf)
        buf.setup_trigger(trigger_fn_generator(st.trigger_slope, 0.0), 1)
    # output the buffer if in stopped mode, since the framing boundary or scaling may
    # have changed with these new settings
    if st.run_mode == 'stopped':
        buf.output_frame()


def main():
    global st
    # we make a buffer to temporarily hold a history of samples -- this allows us to output
    # a frame of waveform that includes samples 'before and after the trigger'
    buf = Buffer(BUFFER_SIZE)

    # load settings into st object
    # new settings can alter the trigger behaviour, so the receive_new_settings() function
    # deals with that. We also signal other programs when we are triggered in inrush mode.
    st = Settings(lambda buf=buf: receive_new_settings(buf),
                     other_programs = [ 'scaler.py', 'mapper.py', 'hellebores.py', 'analyser.py' ])
    
    # setup process_fn and set correct trigger condition
    receive_new_settings(buf)

    # process data from standard input
    try:
        for line in sys.stdin:
            # the process that proces_fn will be executed will change dynamically
            # depending on trigger settings. This is setup in 'receive_new_settings(buf)'
            buf.process_fn(line.rstrip())
            if st.run_mode == 'running' and buf.ready_for_output():
                buf.output_frame()
                buf.reprime_trigger()
                buf.update_frame_markers()
                # update settings if required
                if st.trigger_mode == 'inrush':
                    buf.reprime_trigger()
                    st.run_mode = 'stopped'
                    st.send_to_all()

    except ValueError:
        print(
            f"trigger.py, main(): Failed to read contents of line '{line}'.",
            file=sys.stderr)



if __name__ == '__main__':
    main()


