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
import math

# local
from settings import Settings


BUFFER_SIZE = 65536                  # size of circular sample buffer
MAX_FORWARD_READ = 8192              # maximum reads, post trigger after stopping
SHORT_DOTS = '.' * 32                # used in running mode to mark end of frame
LONG_DOTS = '.' * 8192               # a longer line of dots is used in stopped mode
                                     # to make sure all data is flushed through

VOLTAGE_INDEX = 0                    # Indices for fields in the incoming data
CURRENT_INDEX = 1                    # are defined here
POWER_INDEX = 2
EARTH_LEAKAGE_INDEX = 3


class Mapper:
    """Converts SI units into pixel coordinates."""
    st = None
    # these parameters are set up on initialisation
    output_function = lambda: None
    x_min = 0
    x_max = 0
    x_zero = 0
    y_min = 0
    y_max = 0
    y_zero = 0

    def __init__(self, st, output_format):
        self.st = st
        self.configure_for_new_settings()
        # select an appropriate output transformation function
        if output_format == 'pixels':
            self.output_function = self._pixels_out
        else:
            self.output_function = self._values_out

    def configure_for_new_settings(self):
        """Set upper bounds for x,y coordinates and zero point for trigger position."""
        self.x_max     = self.st.time_axis_divisions * self.st.horizontal_pixels_per_division
        self.y_max     = self.st.vertical_axis_divisions * self.st.vertical_pixels_per_division
        self.x_zero    = (self.st.time_axis_pre_trigger_divisions
                          * self.st.horizontal_pixels_per_division)
        self.y_zero    = self.y_max // 2

    def _pixels_out(self, timestamp, sample):
        """Prepare a line of stored buffer for output with pixel scaling."""
        # Clamping function to avoid exception errors in plotting.
        y_clamp = lambda v: min(max(self.y_min, v), self.y_max)

        c0, c1, c2, c3 = sample
        x  = int(timestamp * self.st.horizontal_pixels_per_division
                  / self.st.time_axis_per_division) + self.x_zero
        y0 = y_clamp(int(- float(c0) * self.st.vertical_pixels_per_division
                  / self.st.voltage_axis_per_division) + self.y_zero)
        y1 = y_clamp(int(- float(c1) * self.st.vertical_pixels_per_division
                  / self.st.current_axis_per_division) + self.y_zero)
        y2 = y_clamp(int(- float(c2) * self.st.vertical_pixels_per_division
                  / self.st.power_axis_per_division) + self.y_zero)
        y3 = y_clamp(int(- float(c3) * self.st.vertical_pixels_per_division
                  / self.st.earth_leakage_current_axis_per_division) + self.y_zero)
        return f'{x :4d} {y0 :4d} {y1 :4d} {y2 :4d} {y3 :4d}'

    def _values_out(self, timestamp, sample):
        """Prepare a line of stored buffer for output with raw values."""
        c0, c1, c2, c3 = sample
        return f'{timestamp:12.4f} {c0:10.3f} {c1:10.5f} {c2:10.3f} {c3:12.7f}'



class Buffer:
    """Local buffer memory for samples. Enables framing of data to be constructed while
    searching for a trigger. Also allows data frame to be modified in stopped mode."""
    st = None                   # will hold settings object
    buf = []                    # will be array of 5*float vectors, ie BUFFER_SIZE * 5
    # Frame pointers are set after trigger pointer is set, in sync/inrush mode,
    # immediately after frame output in free-run mode, and when settings are changed,
    # including in stopped mode.
    # Pointers increase indefinitely. We don't modulo rotate the pointers except when
    # accessing the circular buffer. This is to make it easier to do numeric comparison
    # between pointers and to calculate new frame pointers after each new trigger or
    # after settings have changed.
    frame_startp = 0            # beginning of frame to be output
    frame_endp = 0              # end of frame to be output
    sp = 0                      # storage pointer (advances by 1 for every new sample)
    tp = 0                      # trigger pointer (in running mode, this is moved
                                # forward when trigger condition is next satisfied)
    sync_holdoff_counter = 0    # inhibits the sync trigger for N samples
    inrush_holdoff_counter = 0  # inhibits the inrush trigger for N samples
    frame_samples = 0           # the total number of samples in a frame, derived from
                                # the timebase setting
    pre_trigger_samples = 0     # the number of samples that need to be displayed before
                                # the trigger sample
    post_trigger_samples = 0    # the number of samples displayed after the trigger
    sync_holdoff_samples = 0    # the next sync trigger is inhibited for this number of
                                # samples
    # freerun_interpolation_increment corrects for creeping time error in freerun mode
    # it's set up when new settings are applied
    freerun_interpolation_increment = 0
    # reframed flag indicates that the data in the frame is fresh
    reframed = False
    # trigger flag(s) are raised when a new trigger is detected, and lowered after we
    # have output a frame
    frame_triggered = False
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


    def __init__(self, st):
        """Set up the buffer with settings read from st object."""
        self.st = st
        self.clear_buffer()
        self.configure_for_new_settings()

    def clear_buffer(self):
        """Buffer memory initialised with empty data"""
        # *** Performance optimisation: could consider memoryview object and tuples here ***
        # Consider whether we need to store time data at all
        self.buf = [ [0.0, 0.0, 0.0, 0.0] for i in range(BUFFER_SIZE) ]

    def store_line(self, line):
        """Store a line of new data into the next buffer location"""
        # The storage location is determined by the input pointer sp, which is not intended
        # to be manipulated other than here.
        self.sp += 1
        try:
            self.buf[self.sp % BUFFER_SIZE] = [ float(w) for w in line.split()[1:] ]
        except ValueError:
            self.buf[self.sp % BUFFER_SIZE] = [0.0, 0.0, 0.0, 0.0]
            print(f"trigger.py, store_line(): Couldn't interpret '{line}'.",
                file=sys.stderr)

    def update_frame_markers(self):
        """Call this after frame is re-primed or a new trigger is detected, to set the frame
        markers for the next output."""
        # Set the start and end markers.
        # NB the start marker can slightly overlap the previous end marker in running mode
        # to allow frame rate to be maintained at 50 wf/s for signals in the range 48-52 Hz.
        # Determine the start index depending on the trigger index and where the
        # interpolation fraction landed.
        if self.interpolation_fraction < 0.5:
            self.frame_startp = self.tp - self.pre_trigger_samples - 1
        else:
            self.frame_startp = self.tp - self.pre_trigger_samples
        # End index is start index plus length of frame
        self.frame_endp = self.frame_startp + self.frame_samples
        self.reframed = True

    def reprime(self):
        """Clear the trigger flags."""
        self.frame_triggered = False
        self.inrush_triggered = False

    def trigger_test(self):
        """Call this to check if current sample causes a trigger"""
        self.trigger_test_fn(
            # Take the channel reading for two successive samples and compare
            # against the trigger criteria
            self.buf[(self.sp - 1) % BUFFER_SIZE],
            self.buf[self.sp % BUFFER_SIZE])
        # We only update frame markers and set holdoff if this is a 'new' trigger
        if (self.frame_triggered and not self.reframed) or self.inrush_triggered:
            self.sync_holdoff_counter = self.sync_holdoff_samples
            self.update_frame_markers()

    def ready_for_output(self):
        """Check if we have a new frame and we have stored enough samples to commence output"""
        return True if self.reframed and self.sp > self.frame_endp else False

    def output_frame(self, mapper):
        """Output the array slice with xy shifts to show up in the correct position on screen."""
        # Exact trigger position occurred between the sample self.tp - 1 and self.tp
        precise_trigger_position = self.tp - 1 + self.interpolation_fraction
        for s in range(self.frame_startp, self.frame_endp):
            # timestamp = 0.0ms at the trigger position
            timestamp = self.st.interval * (s - precise_trigger_position)
            sample = self.buf[s % BUFFER_SIZE]
            print(mapper.output_function(timestamp, sample))
        # Some frame data will be held in the kernel pipe buffer
        # If we're in stopped mode or inrush trigger occurred (which will be followed by
        # stopped mode), flush it through with a longer line of dots
        if self.st.run_mode == 'stopped' or self.stop_flag:
            print(LONG_DOTS)
        else:
            print(SHORT_DOTS)
        sys.stdout.flush()

    def build_frame(self, line):
        """Store samples, except in stopped mode beyond MAX_FORWARD_READ"""
        if self.st.run_mode == 'stopped' and self.sp - self.tp > MAX_FORWARD_READ:
            return False
        else:
            self.store_line(line)
            return True

    def i_frac(self, v1, v2, trigger_level):
        """linear interpolation fraction between two samples"""
        return (trigger_level - v1) / (v2 - v1) if v1 != v2 else 0.0

    def rising_trigger_test(self, s1, s2, channel_index, trigger_level):
        """s1 and s2 contain two sample lines. Detect whether the trigger_level is
        crossed in the rising direction."""
        v1 = s1[channel_index]
        v2 = s2[channel_index]
        if self.sync_holdoff_counter <= 0 and v1 <= trigger_level and v2 >= trigger_level:
            self.frame_triggered = True
            self.tp = self.sp
            self.interpolation_fraction = self.i_frac(v1, v2, trigger_level)
        return self.frame_triggered

    def falling_trigger_test(self, s1, s2, channel_index, trigger_level):
        """s1 and s2 contain two sample lines. Detect whether the trigger_level is
        crossed in the falling direction."""
        v1 = s1[channel_index]
        v2 = s2[channel_index]
        if self.sync_holdoff_counter <= 0 and v1 >= trigger_level and v2 <= trigger_level:
            self.frame_triggered = True
            self.tp = self.sp
            self.interpolation_fraction = self.i_frac(v1, v2, trigger_level)
        return self.frame_triggered

    def inrush_trigger_test(self, s1, channel_index, trigger_level):
        """s1 contains a single sample line. Detect whether the trigger_level is
        exceeded."""
        v1 = s1[channel_index]
        if self.inrush_holdoff_counter <= 0 and abs(v1) >= trigger_level:
            self.inrush_triggered = True
            self.tp = self.sp
            # raise a flag to stop at this frame
            self.stop_flag = True
        return self.inrush_triggered

    def freerun_trigger(self):
        """Automatically retrigger after exactly one frame is output. Correct for time
        error where duration of frame is not an exact multiple of sample periods."""
        # Immediately re-trigger
        self.frame_triggered = True
        # The next trigger point is calculated relative to the current trigger point.
        self.tp = self.tp + self.frame_samples
        # The interpolation_fraction corrects for creeping time error -- the frame_samples do not
        # necessarily correspond to exactly one frame of time -- we accumulate the fractional part
        # and then advance by one extra sample position when required.
        self.interpolation_fraction += self.freerun_interpolation_increment
        if self.interpolation_fraction > 1.0:
            self.interpolation_fraction -= 1
            self.tp += 1
        return self.frame_triggered

    def configure_for_new_settings(self):
        """We don't want to process 'mode' logic every time we read a sample. Therefore we create
        a trigger test function dynamically, but do it only when settings are changed."""
        # Calculate dimensional parameters for the frame
        self.frame_samples          = math.floor(self.st.time_axis_divisions
                                          * self.st.time_axis_per_division
                                          / self.st.interval)
        self.pre_trigger_samples    = math.floor(self.st.time_axis_pre_trigger_divisions
                                          * self.st.time_axis_per_division
                                          / self.st.interval)
        self.post_trigger_samples   = self.frame_samples - self.pre_trigger_samples
        # Set a hold-off threshold (minimum number of samples between triggers) to be
        # slightly less (2ms) than the frame samples.
        self.sync_holdoff_samples   = self.frame_samples - int(0.002 * self.st.sample_rate)

        # Setup a composite trigger function and store it in self.trigger_test_fn
        # The logical expressions here help a previous trigger frame to 'latch' correctly
        # (NB the trigger test function is called for every sample).
        if self.st.trigger_mode == 'sync' and self.st.trigger_slope == 'rising':
            self.trigger_test_fn = (lambda s1, s2:
                    self.frame_triggered
                    or self.rising_trigger_test(s1, s2, VOLTAGE_INDEX, 0.0))
        elif self.st.trigger_mode == 'sync' and self.st.trigger_slope == 'falling':
            self.trigger_test_fn = (lambda s1, s2:
                    self.frame_triggered
                    or self.falling_trigger_test(s1, s2, VOLTAGE_INDEX, 0.0))
        elif self.st.trigger_mode == 'inrush' and self.st.trigger_slope == 'rising':
            self.trigger_test_fn = (lambda s1, s2:
                    self.inrush_triggered
                    or self.inrush_trigger_test(s1, CURRENT_INDEX, self.st.inrush_trigger_level)
                    or self.frame_triggered
                    or self.rising_trigger_test(s1, s2, VOLTAGE_INDEX, 0.0))
        elif self.st.trigger_mode == 'inrush' and self.st.trigger_slope == 'falling':
            self.trigger_test_fn = (lambda s1, s2:
                    self.inrush_triggered
                    or self.inrush_trigger_test(s1, CURRENT_INDEX, self.st.inrush_trigger_level)
                    or self.frame_triggered
                    or self.falling_trigger_test(s1, s2, VOLTAGE_INDEX, 0.0))
        elif self.st.trigger_mode == 'freerun':
            self.trigger_test_fn = (lambda s1, s2:
                    self.frame_triggered
                    or self.freerun_trigger())
            self.freerun_interpolation_increment = (self.st.time_axis_divisions
                                                  * self.st.time_axis_per_division / 1000
                                                  * self.st.sample_rate) % 1
            # We may need to jump the freerun trigger pointer by catching up on
            # any elapsed frames, eg returning from stopped mode
            # Advance to latest storage minus post trigger samples
            if self.sp - self.tp > self.frame_samples:
                self.tp = self.sp - self.post_trigger_samples

        self.inrush_holdoff_counter = self.pre_trigger_samples
        self.sync_holdoff_counter = self.sync_holdoff_samples
        # Frame boundary can change, even in stopped mode
        self.update_frame_markers()


def get_command_args():
    """Process command line argument for whether we want raw data or mapped to pixels."""
    cmd_parser = argparse.ArgumentParser(description='Frames waveform data with various '
        'trigger setups, and buffers waveform for re-transmission in stopped mode.')
    cmd_parser.add_argument('--unmapped', default=False, action=argparse.BooleanOptionalAction,
        help='Inhibit mapping of sample values to pixels.')
    program_name = cmd_parser.prog
    args = cmd_parser.parse_args()
    return (program_name, args)


def main():
    # Launch program with --unmapped option to get output as values rather than pixels.
    program_name, args = get_command_args()
    st = Settings(other_programs = [ 'scaler.py', 'hellebores.py', 'analyser.py' ])

    # Make a buffer to temporarily hold a history of samples -- this allows us to output
    # a frame of waveform that includes samples 'before and after the trigger'
    # in 'stopped' mode, it allows us to change the framing (extent of time axis) around the trigger
    buf = Buffer(st)

    # Mapper object helps us to scale output to pixel values
    mapper = Mapper(st, output_format='values' if args.unmapped else 'pixels')

    # When we receive a SIGUSR1 signal, the st object will reconfigure both objects
    st.set_callback_fn(lambda: (buf.configure_for_new_settings(),
                                mapper.configure_for_new_settings()))

    # Process incoming data
    try:
        for line in sys.stdin:
            # Process the incoming line with the current trigger settings
            buf.build_frame(line.rstrip())
            if st.run_mode == 'running' and not buf.inrush_triggered:
                # if buf.frame_triggered, we still check because there might
                # be a subsequent inrush trigger.
                buf.trigger_test()
            # Decrement the holdoff counters
            buf.sync_holdoff_counter -= 1
            buf.inrush_holdoff_counter -= 1
            # Print out the frame if we're ready
            if buf.ready_for_output():
                buf.output_frame(mapper)
                buf.reframed = False
                # In run mode, reset ready for the next frame
                if st.run_mode == 'running':
                    buf.reprime()
            # Stop flag will be raised by the inrush trigger, we send_to_all to
            # update the UI
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
