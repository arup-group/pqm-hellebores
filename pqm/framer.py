#!/usr/bin/env python3


#   __                                           
#  / _|_ __ __ _ _ __ ___   ___ _ __ _ __  _   _ 
# | |_| '__/ _` | '_ ` _ \ / _ \ '__| '_ \| | | |
# |  _| | | (_| | | | | | |  __/ | _| |_) | |_| |
# |_| |_|  \__,_|_| |_| |_|\___|_|(_) .__/ \__, |
#                                   |_|    |___/ 
# 
# Monitors signal and detects signal event eg voltage crossing zero
# Offsets time axis with respect to the trigger (trigger time is t=0)

import sys
import signal
import argparse

# local
from settings import Settings


BUFFER_SIZE = 65536                  # size of circular sample buffer
MAX_FORWARD_READ = BUFFER_SIZE // 4  # maximum reads, post frame end pointer
SHORT_DOTS = '.' * 32                # used in running mode to mark end of frame
LONG_DOTS = '.' * 8192               # used in stopped mode to make sure
                                     # all data is flushed through
TIME_INDEX = 0
VOLTAGE_INDEX = 1
CURRENT_INDEX = 2
POWER_INDEX = 3
EARTH_LEAKAGE_INDEX = 4

class Buffer:
    st = None                # will hold settings object
    buf = None               # array of 5*float vectors, ie BUFFER_SIZE * 5
    # Frame pointers are set after trigger pointer is set, in triggered mode,
    # immediately after frame output in free-run mode, and when settings are changed,
    # including in stopped mode.
    # Pointers increase indefinitely. We don't modulo rotate the pointers except when
    # accessing the circular buffer. This is to make it easier to do numeric comparison
    # between pointers and to calculate new frame pointers after each new trigger or
    # after settings have changed.
    frame_startp = 0         # beginning of frame to be output
    frame_endp = 0           # end of frame to be output
    outp = 0                 # end of last output
    sp = 0                   # storage pointer (advances by 1 for every new sample)
    tp = 0                   # trigger pointer (in running mode, this is moved
                             # forward when trigger condition is next satisfied)
    ip = 0                   # inrush trigger pointer
    # new_frame flag indicates that the data in the frame is fresh
    new_frame = True
    # triggered flag is raised when a new trigger is detected, and lowered after we
    # have output a frame
    triggered = False
    # When there is a successful trigger, the trigger_test_fn will calculate an estimate
    # of the fractional time offset between samples when the trigger took place.
    # The interpolation fraction is used to create an accurate time offset which helps
    # to stabilise the position of successive waveforms on screen.
    # In freerun mode, we use the same parameter to correct for framing time errors so
    # that framing drift is compensated.
    interpolation_fraction = 0.0
    # trigger_test_index defines the input channel that will be used for triggering
    # normally left on the voltage channel, but could be changed.
    # trigger_test_fn when defined takes two arguments, current and previous samples
    # returns True or False depending on whether a trigger criterion (defined inside
    # the function) is met
    trigger_test_index = VOLTAGE_INDEX
    trigger_test_fn = None

    def __init__(self, st, output_mode='pixels'):
        self.st = st
        self.buf = []
        self.frame_startp = 0
        self.frame_endp = st.frame_samples
        self.output_mode = output_mode    # 'pixels' or 'values'
        self.clear_buffer()


    def clear_buffer(self):
        """buffer memory initialised with empty data"""
        # *** performance optimisation: could consider memoryview object here ***
        self.buf = [ [0.0, 0.0, 0.0, 0.0, 0.0] for i in range(BUFFER_SIZE) ]
        print('hi', file=sys.stderr)


    def store_line(self, line):
        """store a line of new data into the next buffer location"""
        # the storage location is determined by the input pointer sp, which is not intended
        # to be manipulated other than here.
        try:
            self.buf[self.sp % BUFFER_SIZE] = [ float(w) for w in line.split() ]
        except ValueError:
            self.buf[self.sp % BUFFER_SIZE] = [ 0.0, 0.0, 0.0, 0.0, 0.0 ]
            print(f"trigger.py, store_line(): Couldn't interpret '{line}'.",
                file=sys.stderr)
        self.sp += 1


    def update_frame_markers(self):
        """Call this after frame is re-primed or a new trigger is detected, to set the frame
        markers for the next output."""
        # set the start and end markers
        self.frame_startp = self.tp - self.st.pre_trigger_samples
        self.frame_endp = self.frame_startp + self.st.frame_samples - 1
        # in running mode, make sure the start marker doesn't precede the previous end marker
        if self.st.run_mode == 'running':
            self.frame_startp = max(self.outp, self.frame_startp)
        # signal that we have set up a new frame
        self.new_frame = True


    def reprime(self):
        """Set the earliest position for the next trigger and clear the trigger flag if not
        in freerun mode"""
        if self.st.trigger_mode == 'sync':
            # new trigger is required, but we wait for at least holdoff samples
            self.tp = max(self.outp, self.sp + self.st.holdoff_samples)
            self.triggered = False
        elif self.st.trigger_mode == 'inrush':
            # for inrush, we are usually leaving stopped mode so we need to allow pre-trigger
            # lead-in for continuity of the samples through the capture
            self.tp = self.sp + self.st.pre_trigger_samples
            self.triggered = False
        elif self.st.trigger_mode == 'freerun':
            # in freerun mode, we advance by exactly one frame and immediately trigger
            self.tp = self.tp + self.st.frame_samples
            # the interpolation_fraction corrects for creeping time error -- the frame_samples do not
            # necessarily correspond to exactly one frame of time
            self.interpolation_fraction += (self.st.time_axis_divisions * self.st.time_axis_per_division \
                / 1000 * self.st.sample_rate) % 1
            if self.interpolation_fraction > 1.0:
                self.tp += int(self.interpolation_fraction)
                self.interpolation_fraction = self.interpolation_fraction % 1
            self.triggered = True


    def trigger_test(self):
        """call this to check if recent samples from self.tp onwards cause a trigger"""
        while self.tp < self.sp:
            self.triggered, self.interpolation_fraction = (
                self.trigger_test_fn(
                    # take the channel reading for two successive samples and compare
                    # against the trigger criteria
                    self.buf[(self.tp - 1) % BUFFER_SIZE][self.trigger_test_index],
                    self.buf[self.tp % BUFFER_SIZE][self.trigger_test_index]))
            if self.triggered == True:
                self.update_frame_markers()
                break
            # increment trigger position ready to try again
            else:
                self.tp += 1


    def ready_for_output(self):
        """Check if we have triggered and we have stored enough samples to
        commence output"""
        if self.new_frame and self.triggered and self.sp >= self.frame_endp:
            return True
        else:
            return False


    def mapper(self, timestamp, sample, pixels_out=True):
        """prepare a line of stored buffer for output, defaults to pixel scaling, otherwise raw values"""

        c0, c1, c2, c3 = sample
        # Clamping function to avoid exception errors in plotting.
        y_clamp = lambda v: min(max(0, v), self.st.y_pixels-1)

        if pixels_out:
            # output pixels
            x  = int(timestamp * self.st.horizontal_pixels_per_division \
                      / self.st.time_axis_per_division) + self.st.x_offset
            y0 = y_clamp(int(- float(c0) * self.st.vertical_pixels_per_division
                      / self.st.voltage_axis_per_division) + self.st.y_offset)
            y1 = y_clamp(int(- float(c1) * self.st.vertical_pixels_per_division
                      / self.st.current_axis_per_division) + self.st.y_offset)
            y2 = y_clamp(int(- float(c2) * self.st.vertical_pixels_per_division
                      / self.st.power_axis_per_division) + self.st.y_offset)
            y3 = y_clamp(int(- float(c3) * self.st.vertical_pixels_per_division
                      / self.st.earth_leakage_current_axis_per_division) + self.st.y_offset)
            out = f'{x :4d} {y0 :4d} {y1 :4d} {y2 :4d} {y3 :4d}'
        else:
            # output values
            out = f'{timestamp:12.4f} {c0:10.3f} {c1:10.5f} {c2:10.3f} {c3:12.7f}'
        return out


    def output_frame(self):
        """Output the array slice with xy shifts to show up in the correct position on screen."""
        # exact trigger position occurred between the sample self.tp - 1 and self.tp
        precise_trigger_position = self.tp - 1 + self.interpolation_fraction
        pixels_out = True if self.output_mode == 'pixels' else False
        for s in range(self.frame_startp, self.frame_endp):
            # timestamp = 0.0ms at the trigger position
            timestamp = self.st.interval * (s - precise_trigger_position)
            sample = self.buf[s % BUFFER_SIZE][VOLTAGE_INDEX:]
            out = self.mapper(timestamp, sample, pixels_out)
            print(out)
        # some frame data will be held in the kernel pipe buffer
        # if we're in stopped mode or inrush trigger mode (which will be followed by
        # stopped mode), flush it through with a longer line of dots
        if self.st.run_mode == 'stopped' or self.st.trigger_mode == 'inrush':
            print(LONG_DOTS)
        else:
            print(SHORT_DOTS)
        self.outp = self.frame_endp
        sys.stdout.flush()
        self.new_frame = False


    def build_frame(self, line):
        """Store samples, except in stopped mode beyond MAX_FORWARD_READ"""
        if self.st.run_mode == 'stopped' and self.sp - self.frame_endp > MAX_FORWARD_READ:
            return False
        else:
            self.store_line(line)
            return True
    

    def update_trigger_settings(self):
        # interpolation fraction
        def i_frac(s1, s2, trigger_level):
            return (trigger_level - s1) / (s2 - s1) if s1 != s2 else 0.0

        def sync_trigger(slope, trigger_level):
            if slope == 'rising':
                trigger_fn = (lambda s1, s2: (True, i_frac(s1,s2,trigger_level))
                                 if s1 <= trigger_level and s2 >= trigger_level else (False, 0.0))
            elif slope == 'falling':
                trigger_fn = (lambda s1, s2: (True, i_frac(s1,s2,trigger_level))
                                 if s1 >= trigger_level and s2 <= trigger_level else (False, 0.0))
            return trigger_fn

        def inrush_trigger(trigger_level):
            trigger_fn = (lambda s1, s2: (True, 0.0)
                             if abs(s2) >= trigger_level else (False, 0.0))
            return trigger_fn

        if self.st.trigger_mode == 'inrush':
            self.trigger_test_fn = inrush_trigger(self.st.inrush_trigger_level)
            self.trigger_test_index = CURRENT_INDEX
        elif self.st.trigger_mode == 'sync':
            self.trigger_test_fn = sync_trigger(self.st.trigger_slope, 0.0)
            self.trigger_test_index = VOLTAGE_INDEX


def get_command_args():
    cmd_parser = argparse.ArgumentParser(description='Frames waveform data with or '
        'without synchronisation trigger, and buffers waveform for re-transmission in stopped mode.')
    cmd_parser.add_argument('--unmapped', default=False, action=argparse.BooleanOptionalAction, \
        help='Inhibit mapping of sample values to pixels.')
    program_name = cmd_parser.prog
    args = cmd_parser.parse_args()
    return (program_name, args)


def main():
    # Launch program with --unmapped option to get output as values rather than pixels.
    program_name, args = get_command_args()
         
    # flag to reload settings into st object
    settings_were_updated = True

    def set_settings_were_updated():
        nonlocal settings_were_updated
        settings_were_updated = True

    # when we receive a SIGUSR1 signal, the st object will flip the flag
    st = Settings(set_settings_were_updated,
        other_programs = [ 'scaler.py', 'hellebores.py', 'analyser.py' ])
    
    # we make a buffer to temporarily hold a history of samples -- this allows us to output
    # a frame of waveform that includes samples 'before and after the trigger'
    # in 'stopped' mode, it allows us to change the framing (extent of time axis) around the trigger
    buf = Buffer(st, output_mode='values' if args.unmapped else 'pixels')

    # process data from standard input
    try:
        for line in sys.stdin:
            # new settings received, update the trigger settings and the frame boundary
            if settings_were_updated:
                buf.update_trigger_settings()
                # if we are in running mode, then re-prime the trigger
                # regardless of the trigger mode
                if st.run_mode == 'running':
                    if st.trigger_mode == 'inrush':
                        # clear out old data if we reprime in inrush mode
                        buf.clear_buffer()
                        buf.output_frame()
                    buf.reprime()
                # frame boundary can change, even in stopped mode
                buf.update_frame_markers()
                # lower the flag
                settings_were_updated = False
            # process the incoming line with the current trigger settings
            buf.build_frame(line.rstrip())
            if not buf.triggered:
                buf.trigger_test()
            if buf.ready_for_output():
                buf.output_frame()
                # if running, reset for the next frame
                if st.run_mode == 'running':
                    if st.trigger_mode == 'inrush' and buf.triggered:
                        # stop running if we were triggered in inrush mode
                        st.run_mode = 'stopped'
                        st.send_to_all()
                    else:
                        # otherwise reprime the trigger and move the frame forwards
                        buf.reprime()
                        buf.update_frame_markers()

    except ValueError:
        print(
            f"{program_name}, main(): Failed to read contents of line '{line}'.",
            file=sys.stderr)



if __name__ == '__main__':
    main()

