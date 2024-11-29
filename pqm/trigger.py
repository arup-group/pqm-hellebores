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


BUFFER_SIZE = 65536                  # size of circular sample buffer
MAX_FORWARD_READ = BUFFER_SIZE // 4  # maximum reads, post frame end pointer

class Buffer:
    st = None            # will hold settings object
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
    # When there is a successful trigger, the trigger_test_fn will calculate an estimate
    # of the fractional time offset between samples when the trigger took place.
    # The interpolation fraction is used to create an accurate time offset which helps
    # to stabilise the position of successive waveforms on screen.
    interpolation_fraction = 0.0
    # trigger_test_ch defines the input channel that will be used for triggering
    # normally left on the voltage channel, but could be changed.
    # trigger_test_fn when defined takes two arguments, current and previous samples
    # returns True or False depending on whether a trigger criterion (defined inside
    # the function) is met
    trigger_test_ch = 1
    trigger_test_fn = None
    # a function reference is assigned to process_fn when trigger settings are updated
    process_fn = lambda line: 0  # dummy function -- this will be replaced at runtime

    def __init__(self, st, size=BUFFER_SIZE):
        """buffer memory initialised with empty data"""
        # *** performance optimisation: could consider memoryview object here ***
        self.size = size
        self.buf = [ [0.0, 0.0, 0.0, 0.0, 0.0] for i in range(size) ]
        self.st = st
        self.frame_startp = 0
        self.frame_endp = st.frame_samples

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
        if self.st.run_mode == 'running':
            if self.st.trigger_mode == 'sync' or self.st.trigger_mode == 'inrush':
                # make sure the start marker does not precede the end marker of the previous output
                self.frame_startp = max(self.outp, self.tp - self.st.pre_trigger_samples)
                self.frame_endp = self.tp + self.st.post_trigger_samples - 1
            elif st.trigger_mode == 'freerun':
                # in freerun mode, we just run frames back to back with one another
                self.frame_startp = self.frame_outp
                self.frame_endp = self.frame_startp + self.st.frame_samples
        # in stopped mode, we move the existing frame boundaries around the current trigger
        else:
            self.frame_startp = self.tp - self.st.pre_trigger_samples
            self.frame_endp = self.tp + self.st.post_trigger_samples - 1

    def reprime_trigger(self):
        """Set the earliest trigger position to be at least the hold-off time after the
        previous trigger (dependent on the time axis, so we don't trigger too early in the
        frame)"""
        self.tp = self.tp + self.st.holdoff_samples
        self.triggered = False


    def trigger_test(self):
        """call this to check if recent samples from self.tp onwards cause a trigger"""
        while self.tp < self.sp:
            self.triggered, self.interpolation_fraction = (
                self.trigger_test_fn(
                    # take the channel reading for two successive samples and compare
                    # against the trigger criteria
                    self.buf[(self.tp - 1) % self.size][self.trigger_test_ch], 
                    self.buf[self.tp % self.size][self.trigger_test_ch]))
            if self.triggered == True:
                self.update_frame_markers()
                break
            else:
                self.tp += 1
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
        print(f'Output settings: outp {self.outp}, startp {self.frame_startp}, endp {self.frame_endp}, tp {self.tp}, sp {self.sp}', file=sys.stderr)
        # time=0 at exactly the trigger position corrected by an interpolation fraction
        trigger_offset = self.tp - 1 + self.interpolation_fraction
        for s in range(self.frame_startp, self.frame_endp):
            sample = self.buf[s % self.size]
            # modify the timestamp
            timestamp = self.st.interval * (s - trigger_offset)
            # if it's the last sample in the frame, add an 'END' marker
            em = '*END*' if s == self.frame_endp - 1 else ''
            print(f'{timestamp:12.4f} {sample[1]:10.3f} '
                  f'{sample[2]:10.5f} {sample[3]:10.3f} {sample[4]:12.7f} {em}')
        self.outp = self.frame_endp
        sys.stdout.flush()


    def via_trigger(self, line):
        # store samples even in stopped mode up to MAX_SAMPLES
        if self.sp - self.frame_endp < MAX_FORWARD_READ:
            self.store_line(line)
            if not self.triggered:
                self.trigger_test()
    

    def pass_through(self, line):
        # pretty simple, no triggering at all, just copy the input to the output
        if self.sp - self.frame_endp < MAX_FORWARD_READ:
            self.store_line(line)


    def update_trigger_settings(self):
        global st

        # interpolation fraction
        def i_frac(s1, s2, threshold):
            if s1 == s2:
                return 0.0
            else:
                return (threshold-s1)/(s2-s1)

        def trigger_fn_generator(trigger_mode, slope, threshold):
            if trigger_mode == 'sync' or trigger_mode == 'inrush':
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
            elif trigger_mode == 'freerun':
                # in freerun mode, the trigger always fires True
                return (lambda s1, s2: True)
            else:
                return None

        # we define the signal processing function 'process_fn' to point to different
        # behaviours depending on the mode of triggering that is specified
        if self.st.trigger_mode == 'freerun':
            # would prefer to implement in a consolidated function (via_trigger, renamed)
            self.process_fn = lambda line: self.pass_through(line)
        elif self.st.trigger_mode == 'sync':
            self.process_fn = lambda line: self.via_trigger(line)
            self.trigger_test_fn = trigger_fn_generator('sync', self.st.trigger_slope, 0.0)
            self.trigger_test_ch = 1
        elif self.st.trigger_mode == 'inrush':
            self.process_fn = lambda line: self.via_trigger(line)
            self.trigger_test_fn = trigger_fn_generator('inrush', self.st.trigger_slope, self.st.trigger_level)
            self.trigger_test_ch = 3
        else:
            print(
                "trigger.py, Buffer:trigger_fn_generator(): Trigger_mode not recognised, defaulting to sync.",
                file=sys.stderr)
            self.process_fn = lambda line: self.via_trigger(line)
            self.trigger_test_fn = trigger_fn_generator('sync', self.st.trigger_slope, 0.0)
            self.trigger_test_ch = 1
        # output the buffer if in stopped mode, since the framing boundary or scaling may
        # have changed with these new settings
        if self.st.run_mode == 'stopped':
            self.update_frame_markers()
            self.output_frame()


def main():
    # flag to reload settings into st object
    settings_were_updated = True

    def flip_new_settings_flag():
        nonlocal settings_were_updated
        settings_were_updated = not settings_were_updated

    # when we receive a SISUSR1 signal, the st object will flip the flag
    st = Settings(flip_new_settings_flag,
                     other_programs = [ 'scaler.py', 'mapper.py', 'hellebores.py', 'analyser.py' ])
    
    # we make a buffer to temporarily hold a history of samples -- this allows us to output
    # a frame of waveform that includes samples 'before and after the trigger'
    # in 'stopped' mode, it allows us to change the framing (extent of time axis) around the trigger
    buf = Buffer(st)

    # process data from standard input
    try:
        for line in sys.stdin:
            # the function that process_fn will execute changes dynamically
            # depending on trigger settings. This is setup in 'update_trigger_settings(buf)'
            if settings_were_updated:
                buf.update_trigger_settings()
                flip_new_settings_flag()
            buf.process_fn(line.rstrip())
            if st.run_mode == 'running' and buf.ready_for_output():
                buf.output_frame()
                buf.reprime_trigger()
                buf.update_frame_markers()
                # update settings if we are in inrush mode
                if st.trigger_mode == 'inrush':
                    st.run_mode = 'stopped'
                    st.send_to_all()

    except ValueError:
        print(
            f"trigger.py, main(): Failed to read contents of line '{line}'.",
            file=sys.stderr)



if __name__ == '__main__':
    main()


