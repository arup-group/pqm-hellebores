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
#
# This is hard!! There are many gotchas with triggering and framing the display --
# ensure enough lead-in (continuity of capture before the trigger), prevent
# early re-trigger via 'holdoff' samples, allow inrush trigger to override
# sync trigger. The logic is inter-twined and edits are liable to have unintended
# consequences. So edit with care!
#

import sys
import signal
import argparse

# local
from settings import Settings


BUFFER_SIZE = 65536                  # size of circular sample buffer
MAX_FORWARD_READ = BUFFER_SIZE // 4  # maximum reads, post frame end pointer
SHORT_DOTS = '.' * 32                # used in running mode to mark end of frame
LONG_DOTS = '.' * 8192               # a longer line of dots is used in stopped mode
                                     # to make sure all data is flushed through

TIME_INDEX = 0                       # Indices for fields in the incoming data
VOLTAGE_INDEX = 1                    # are defined here
CURRENT_INDEX = 2
POWER_INDEX = 3
EARTH_LEAKAGE_INDEX = 4

class Buffer:
    st = None                   # will hold settings object
    buf = None                  # array of 5*float vectors, ie BUFFER_SIZE * 5
    # Frame pointers are set after trigger pointer is set, in sync/inrush mode,
    # immediately after frame output in free-run mode, and when settings are changed,
    # including in stopped mode.
    # Pointers increase indefinitely. We don't modulo rotate the pointers except when
    # accessing the circular buffer. This is to make it easier to do numeric comparison
    # between pointers and to calculate new frame pointers after each new trigger or
    # after settings have changed.
    frame_startp = 0            # beginning of frame to be output
    frame_endp = 0              # end of frame to be output
    outp = 0                    # end of previous output
    sp = 0                      # storage pointer (advances by 1 for every new sample)
    tp = 0                      # trigger pointer (in running mode, this is moved
                                # forward when trigger condition is next satisfied)
    sync_holdoff_counter = 0    # inhibits the sync trigger for N samples
    inrush_holdoff_counter = 0  # inhibits the inrush trigger for N samples
    # reframed flag indicates that the data in the frame is fresh
    reframed = False
    # trigger flag(s) are raised when a new trigger is detected, and lowered after we
    # have output a frame
    sync_triggered = False
    inrush_triggered = False
    stop_flag = False
    # When there is a successful trigger, the trigger_test_fn will calculate an estimate
    # of the fractional time offset between samples when the trigger took place.
    # The interpolation fraction is used to create an accurate time offset which helps
    # to stabilise the position of successive waveforms on screen.
    # In freerun mode, we use the same parameter to correct for framing time errors so
    # that framing drift is compensated.
    interpolation_fraction = 0.0
    # trigger_test_fn once defined takes two arguments, previous and current samples
    # returns True or False depending on whether a trigger criterion (defined
    # inside the function) is met. This function is dynamically redefined for mode-specific
    # logic when settings are changed
    trigger_test_fn = lambda self, s1, s2: False
    # output function is set during __init__
    output_function = None

    def __init__(self, output_format):
        """caller needs to set self.st after init."""
        self.buf = []
        # select an appropriate output transformation function
        if output_format == 'pixels':
            self.output_function = self.pixels_out
        else:
            self.output_function = self.values_out
        self.clear_buffer()


    def clear_buffer(self):
        """buffer memory initialised with empty data"""
        # *** performance optimisation: could consider memoryview object here ***
        self.buf = [ [0.0, 0.0, 0.0, 0.0, 0.0] for i in range(BUFFER_SIZE) ]


    def store_line(self, line):
        """store a line of new data into the next buffer location"""
        # the storage location is determined by the input pointer sp, which is not intended
        # to be manipulated other than here.
        self.sp += 1
        try:
            self.buf[self.sp % BUFFER_SIZE] = [ float(w) for w in line.split() ]
        except ValueError:
            self.buf[self.sp % BUFFER_SIZE] = [ 0.0, 0.0, 0.0, 0.0, 0.0 ]
            print(f"trigger.py, store_line(): Couldn't interpret '{line}'.",
                file=sys.stderr)


    def update_frame_markers(self):
        """Call this after frame is re-primed or a new trigger is detected, to set the frame
        markers for the next output."""
        # set the start and end markers
        self.frame_startp = self.tp - self.st.pre_trigger_samples
        self.frame_endp = self.frame_startp + self.st.frame_samples - 1
        # in running mode, make sure the start marker doesn't precede the previous end marker
        if self.st.run_mode == 'running' and self.st.trigger_mode == 'sync':
            self.frame_startp = max(self.outp, self.frame_startp)
        # signal that we have set up a new frame
        self.reframed = True


    def reprime(self):
        """Set the earliest position for the next trigger and clear the trigger flag if not
        in freerun mode"""
        if self.st.trigger_mode == 'freerun':
            self.freerun_trigger_test()
        else:
            # in sync or inrush mode, clear the sync trigger flag
            self.sync_triggered = False
        # always clear the inrush trigger flag
        self.inrush_triggered = False


    def trigger_test(self):
        """call this to check if current sample causes a trigger"""
        self.trigger_test_fn(
            # take the channel reading for two successive samples and compare
            # against the trigger criteria
            self.buf[(self.sp - 1) % BUFFER_SIZE],
            self.buf[self.sp % BUFFER_SIZE])
        # we only update frame markers and set holdoff if this is a 'new' trigger
        if (self.sync_triggered and not self.reframed) or self.inrush_triggered:
            self.sync_holdoff_counter = self.st.sync_holdoff_samples
            self.update_frame_markers()

    def ready_for_output(self):
        """Check if we have a new frame and we have stored enough samples to commence output"""
        if self.reframed and self.sp > self.frame_endp:
            return True
        else:
            return False

    def values_out(self, timestamp, sample):
        """prepare a line of stored buffer for output with raw values."""
        c0, c1, c2, c3 = sample
        return f'{timestamp:12.4f} {c0:10.3f} {c1:10.5f} {c2:10.3f} {c3:12.7f}'

    def pixels_out(self, timestamp, sample):
        """prepare a line of stored buffer for output with pixel scaling."""
        c0, c1, c2, c3 = sample
        # Clamping function to avoid exception errors in plotting.
        y_clamp = lambda v: min(max(0, v), self.st.y_pixels-1)

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
        return f'{x :4d} {y0 :4d} {y1 :4d} {y2 :4d} {y3 :4d}'

    def output_frame(self):
        """Output the array slice with xy shifts to show up in the correct position on screen."""
        # exact trigger position occurred between the sample self.tp - 1 and self.tp
        precise_trigger_position = self.tp - 1 + self.interpolation_fraction
        for s in range(self.frame_startp, self.frame_endp):
            # timestamp = 0.0ms at the trigger position
            timestamp = self.st.interval * (s - precise_trigger_position)
            sample = self.buf[s % BUFFER_SIZE][VOLTAGE_INDEX:]
            print(self.output_function(timestamp, sample))
        # some frame data will be held in the kernel pipe buffer
        # if we're in stopped mode or inrush trigger occurred (which will be followed by
        # stopped mode), flush it through with a longer line of dots
        if self.st.run_mode == 'stopped' or self.stop_flag:
            print(LONG_DOTS)
        else:
            print(SHORT_DOTS)
        self.outp = self.frame_endp
        sys.stdout.flush()
        self.reframed = False


    def build_frame(self, line):
        """Store samples, except in stopped mode beyond MAX_FORWARD_READ"""
        if self.st.run_mode == 'stopped' and self.sp - self.frame_endp > MAX_FORWARD_READ:
            return False
        else:
            self.store_line(line)
            return True

    def i_frac(self, v1, v2, trigger_level):
        """linear interpolation fraction between two samples"""
        return (trigger_level - v1) / (v2 - v1) if v1 != v2 else 0.0

    def rising_trigger_test(self, s1, s2, channel_index, trigger_level):
        v1 = s1[channel_index]
        v2 = s2[channel_index]
        if self.sync_holdoff_counter <= 0 and v1 <= trigger_level and v2 >= trigger_level:
            self.sync_triggered = True
            self.tp = self.sp
            self.interpolation_fraction = self.i_frac(v1, v2, trigger_level)
        return self.sync_triggered

    def falling_trigger_test(self, s1, s2, channel_index, trigger_level):
        v1 = s1[channel_index]
        v2 = s2[channel_index]
        if self.sync_holdoff_counter <= 0 and v1 >= trigger_level and v2 <= trigger_level:
            self.sync_triggered = True
            self.tp = self.sp
            self.interpolation_fraction = self.i_frac(v1, v2, trigger_level)
        return self.sync_triggered

    def inrush_trigger_test(self, s1, channel_index, trigger_level):
        v1 = s1[channel_index]
        if self.inrush_holdoff_counter <= 0 and abs(v1) >= trigger_level:
            self.inrush_triggered = True
            self.tp = self.sp
            # raise a flag to stop at this frame
            self.stop_flag = True
        return self.inrush_triggered

    def freerun_trigger_test(self):
        # in freerun mode, we advance by exactly one frame and immediately trigger
        self.sync_triggered = True
        # the next trigger point is calculated relative to the current storage pointer
        # rather than the current trigger pointer so that we easily recover from a stopped
        # state when returning to a running state. ie instead of:
        # self.tp = self.tp + self.st.frame_samples
        # we do:
        self.tp = self.sp + self.st.pre_trigger_samples + 1
        # the interpolation_fraction corrects for creeping time error -- the frame_samples do not
        # necessarily correspond to exactly one frame of time
        self.interpolation_fraction += (self.st.time_axis_divisions * self.st.time_axis_per_division \
            / 1000 * self.st.sample_rate) % 1
        if self.interpolation_fraction > 1.0:
            self.tp += int(self.interpolation_fraction)
            self.interpolation_fraction = self.interpolation_fraction % 1
        return self.sync_triggered

    def configure_for_new_settings(self):
        """We don't want to process 'mode' logic every time we read a sample. Therefore we create
        a trigger test function dynamically, only when settings are changed."""
        # setup a composite trigger function and store it in self.trigger_test_fn
        # the logical expressions here help a previous trigger frame to 'latch' correctly
        # (the trigger test function is called for every sample)
        if self.st.trigger_mode == 'sync' and self.st.trigger_slope == 'rising':
            self.trigger_test_fn = (lambda s1, s2:
                    self.sync_triggered
                    or self.rising_trigger_test(s1, s2, VOLTAGE_INDEX, 0.0))
        elif self.st.trigger_mode == 'sync' and self.st.trigger_slope == 'falling':
            self.trigger_test_fn = (lambda s1, s2:
                    self.sync_triggered
                    or self.falling_trigger_test(s1, s2, VOLTAGE_INDEX, 0.0))
        elif self.st.trigger_mode == 'inrush' and self.st.trigger_slope == 'rising':
            self.trigger_test_fn = (lambda s1, s2:
                    self.inrush_triggered
                    or self.inrush_trigger_test(s1, CURRENT_INDEX, self.st.inrush_trigger_level)
                    or self.sync_triggered
                    or self.rising_trigger_test(s1, s2, VOLTAGE_INDEX, 0.0))
        elif self.st.trigger_mode == 'inrush' and self.st.trigger_slope == 'falling':
            self.trigger_test_fn = (lambda s1, s2:
                    self.inrush_triggered
                    or self.inrush_trigger_test(s1, CURRENT_INDEX, self.st.inrush_trigger_level)
                    or self.sync_triggered
                    or self.falling_trigger_test(s1, s2, VOLTAGE_INDEX, 0.0))
        elif self.st.trigger_mode == 'freerun':
            self.trigger_test_fn = (lambda s1, s2:
                    self.sync_triggered
                    or self.freerun_trigger_test())
        self.inrush_holdoff_counter = self.st.pre_trigger_samples
        self.sync_holdoff_counter = self.st.sync_holdoff_samples
        # frame boundary can change, even in stopped mode
        self.update_frame_markers()



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

    # we make a buffer to temporarily hold a history of samples -- this allows us to output
    # a frame of waveform that includes samples 'before and after the trigger'
    # in 'stopped' mode, it allows us to change the framing (extent of time axis) around the trigger
    buf = Buffer(output_format='values' if args.unmapped else 'pixels')

    # when we receive a SIGUSR1 signal, the st object will update buffer object settings
    st = Settings(buf.configure_for_new_settings,
        other_programs = [ 'scaler.py', 'hellebores.py', 'analyser.py' ])

    # now store a reference to the st object in the buffer object
    # and initialise settings
    buf.st = st
    buf.configure_for_new_settings()

    # process data from standard input
    try:
        for line in sys.stdin:
            # process the incoming line with the current trigger settings
            buf.build_frame(line.rstrip())
            if not buf.inrush_triggered:
                buf.trigger_test()
            # decrement the holdoff counters
            buf.sync_holdoff_counter -= 1
            buf.inrush_holdoff_counter -= 1
            # print out the frame if we're ready
            if buf.ready_for_output():
                buf.output_frame()
                # if running, reset ready for the next frame
                if st.run_mode == 'running':
                    buf.reprime()
            # stop flag will be raised by the inrush trigger
            if buf.stop_flag:
                st.run_mode = 'stopped'
                st.send_to_all()
                buf.stop_flag = False

    except ValueError:
        print(
            f"{program_name}, main(): Failed to read contents of line '{line}'.",
            file=sys.stderr)



if __name__ == '__main__':
    main()
