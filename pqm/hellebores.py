#!/usr/bin/env python3

# figlet
#  _          _ _      _                                       
# | |__   ___| | | ___| |__   ___  _ __ ___  ___   _ __  _   _ 
# | '_ \ / _ \ | |/ _ \ '_ \ / _ \| '__/ _ \/ __| | '_ \| | | |
# | | | |  __/ | |  __/ |_) | (_) | | |  __/\__ \_| |_) | |_| |
# |_| |_|\___|_|_|\___|_.__/ \___/|_|  \___||___(_) .__/ \__, |
#                                                 |_|    |___/ 
#

# library imports
import thorpy
import pygame
import time
import sys
import os
import argparse
import select
import ast
import io

# project imports
from settings import Settings
from hellebores_constants import *
from hellebores_controls import *
from hellebores_waveform import Waveform
from hellebores_multimeter import Multimeter
from hellebores_harmonic import Harmonic
if os.name == 'nt':
    from mswin_pipes import Pipe, peek_pipe, get_pipe_from_stream


# The instance of this class will hold all the user interface states or 'groups'
# that can be displayed together with the currently active selection
class UI_groups:
    elements = {}
    mode = 'waveform'
    instruments = {}
    # the flag helps to reduce workload of screen refresh when there are overlay menus.
    overlay_dialog_active = False

    def __init__(self, st, buffer, waveform, multimeter, v_harmonics, i_harmonics, app_actions):
        # make a local reference to app_actions and st
        self.app_actions = app_actions
        self.st = st
        self.buffer = buffer

        # re-point the updater function in the app_actions object to target the function in this object
        # NB dynamically altering a function definition in another object is a relatively unusual
        # programming move, but I can't think of another convenient way to do it, because 'self' is
        # instantiated for this object only after the app_actions object was created.
        app_actions.set_updater = self.set_updater

        # datetime group
        self.elements['datetime'] = create_datetime()

        # waveform group
        self.instruments['waveform'] = waveform
        self.elements['waveform'] = [ waveform.waveform_controls ]

        # multi-meter group
        self.instruments['multimeter'] = multimeter
        self.elements['multimeter'] = [ multimeter.multimeter_controls ]

        # voltage harmonic group
        self.instruments['voltage_harmonic'] = v_harmonics
        self.elements['voltage_harmonic'] = [ v_harmonics.harmonic_controls ]

        # current harmonic group
        self.instruments['current_harmonic'] = i_harmonics
        self.elements['current_harmonic'] = [ i_harmonics.harmonic_controls ]

        # control groups that overlay the main group when adjusting settings
        self.elements['mode'] = create_mode(app_actions)
        self.elements['current_sensitivity'] = create_current_sensitivity(st, app_actions)
        self.elements['vertical'] = create_vertical(st, app_actions)
        self.elements['horizontal'] = create_horizontal(st, app_actions)
        self.elements['trigger'] = create_trigger(st, waveform, app_actions)
        self.elements['options'] = create_options(waveform, app_actions)
        self.elements['clear'] = create_clear(buffer, app_actions)

        for k in ['mode', 'current_sensitivity', 'vertical', 'horizontal', 'trigger', 'options', 'clear']:
            self.elements[k].set_topright(*SETTINGS_BOX_POSITION)


    def catch_latest_analysis(self):
        """At the point of stopping, capture the latest analysis results into the UI objects."""
        self.instruments['multimeter'].update_multimeter_display(self.buffer.cs)
        self.instruments['voltage_harmonic'].update_harmonic_display(self.buffer.cs)
        self.instruments['current_harmonic'].update_harmonic_display(self.buffer.cs)


    def refresh(self, screen):
        """dispatch to the refresh method of the element group currently selected."""
        if self.mode == 'waveform' and self.st.run_mode == 'running':
            # plot multiple traces if we're running in waveform mode
            traces = self.app_actions.multi_trace
            self.instruments[self.mode].refresh(self.buffer, screen, \
                multi_trace=self.app_actions.multi_trace)
        else:
            self.instruments[self.mode].refresh(self.buffer, screen)
        # update the status line
        self.elements['datetime'].draw()


    def update_annunciators(self):
        self.instruments[self.mode].update_annunciators()


    def set_multi_trace(self):
        # need to run this at least when the timebase changes or when there is an overlay dialog
        # currently caused to run for any event
        if self.st.time_axis_per_division < 10:
            if self.overlay_dialog_active:
                self.app_actions.multi_trace = 4
            else:
                self.app_actions.multi_trace = 2
        else:
            # for longer timebases, we can re-draw every time
            self.app_actions.multi_trace = 1

    def set_updater(self, elements_group):
        # for 'waveform', 'multimeter', 'voltage_harmonic', 'current_harmonic',
        # we retain the group in a 'mode' variable for recall after menu selections.
        if elements_group in ['waveform', 'multimeter', 'voltage_harmonic', 'current_harmonic']:
            # if we picked a different display mode, store it in 'self.mode'.
            self.mode = elements_group
            selected_elements = [ *self.elements[self.mode] ]
            self.app_actions.post_clear_screen_event()
            self.overlay_dialog_active = False
        elif elements_group == 'back':
            # if we picked 'back', then just use the pre-existing mode
            selected_elements = [ *self.elements[self.mode] ]
            self.overlay_dialog_active = False
        else:
            # otherwise, use the pre-existing mode and add the selected overlay
            # elements to it.
            selected_elements = [ *self.elements[self.mode], self.elements[elements_group] ]
            self.overlay_dialog_active = True
        try: 
            self.updater = thorpy.Group(elements=selected_elements, mode=None).get_updater()
        except KeyError:
            print(f"UI_groups.set_updater(): couldn't set or find"
                  f" '{elements_group}' updater object.\n", file=sys.stderr)
        return self.updater

    def get_updater(self):
        return self.updater 

    def get_element(self, element):
        return self.elements[element]


class WFS_Counter:

    def __init__(self):
        self.wfs          = 0    # last computed wfs
        self.counter      = 0    # number of waveforms since last posting
        self.update_time  = 0    # time when the wfs/s was lasted posted to screen

    # called whenever we update the waveform on screen 
    def increment(self):
        self.counter += 1

    def time_to_update(self):
        # time now 
        tn = time.time()
        # if the time has increased by at least 1.0 second, update the wfm/s text
        elapsed = tn - self.update_time
        if elapsed >= 1.0:
            self.wfs = int(self.counter/elapsed)
            self.update_time = tn
            self.counter = 0
            return True
        else:
            return False
 
    def get(self):
        return self.wfs
        

def get_screen_hardware_size():
    i = pygame.display.Info()
    return i.current_w, i.current_h


class Sample_Buffer:

    def __init__(self, st, data_comms):
        # local reference to settings and app_actions
        self.st = st
        self.data_comms = data_comms
        # working points buffer for four lines, calculation array
        # flag for detecting when pipes are closed (end of file)
        self.ps = [ [],[],[],[] ]           # points
        self.cs = {}                        # calculations
        # sample buffer history
        # allows 'multitrace' to work
        self.waveforms = [ [] for i in range(SAMPLE_BUFFER_SIZE) ]

    def end_frame(self):
        # shift the history buffer along and add the new capture
        self.waveforms = [ self.ps, *self.waveforms[1:] ]
        # reset the working buffer
        self.ps = [ [],[],[],[] ]

    def add_sample(self, sample):
        self.ps[0].append((sample[0], sample[1]))
        self.ps[1].append((sample[0], sample[2]))
        self.ps[2].append((sample[0], sample[3]))
        self.ps[3].append((sample[0], sample[4]))

    def clear_analysis_bounds(self):
        """Incrementing the analysis_max_min_reset setting triggers a function in analyser.py
        to clear the analysis max/min boundaries."""
        self.st.analysis_max_min_reset += 1
        self.st.send_to_all() 


    def clear_accumulators(self):
        """Incrementing the analysis_accumulators_reset setting triggers a function in analyser.py
        to reset all the accumulators."""
        self.st.analysis_accumulators_reset += 1
        self.st.send_to_all()


    def load_analysis(self):
        # incoming analysis data is optional: returns false if no data source
        if l:=self.data_comms.get_analysis_line(0.0):
            try:
                # load the analysis into a local dictionary
                self.cs = ast.literal_eval(l)
            except (ValueError, AttributeError, SyntaxError):
                print('hellebores.py: Sample_Buffer.load_analysis()'
                      ' file reading error.', file=sys.stderr) 
            return True
        else:
            return False


    def load_waveform(self, wfs):
        # the loop will exit if:
        # (a) there is no data currently waiting to be read, 
        # (b) '.' end-of-frame marker in current line
        # (c) the line is empty, can't be split() or any other kind of read error,
        # (d) more than 1000 samples have been read (this keeps the UI responsive)
        sample_counter = 0
        while sample_counter < 1000 and (l := self.data_comms.get_waveform_line(0.02)):
            try:
                # lines beginning with '.' end the frame
                # in stopped mode, framer will send a larger block of '.' characters in one line
                # to flush the pipe buffer in the kernel.
                if l[0] == '.':
                    # end the current frame
                    self.end_frame()
                    wfs.increment()
                    break
                else:
                    # add a sample
                    self.add_sample([ int(w) for w in l.split() ])
                    sample_counter += 1
            except (IndexError, ValueError):
                print('hellebores.py: Sample_Buffer.load_analysis()'
                      ' file reading error.', file=sys.stderr) 
                break


    def get_waveform(self, index=0):
        # advance into history by 'index' frames
        return self.waveforms[min(index,SAMPLE_BUFFER_SIZE)]



class Data_comms:
    """Contains references and methods to deal with the connection to and reading of
    incoming data for waveforms and analysis results. Deployed on Pi, this will
    normally use named pipes controlled by a shell script. However the class here
    also supports anonymous pipe from stdin (waveform data only), for convenience
    when interacting with the project in the shell."""
    def __init__(self, waveform_stream_name, analysis_stream_name):
        self.waveform_stream = None
        self.analysis_stream = None
        self.pipes_ok = False
        # open the streams (input data pipe files)
        # if successful, this will flip the pipes_ok flag to true
        self.open_streams(waveform_stream_name, analysis_stream_name)

    def select_peek_data_function(self, source_type):
        """The version of self.peek_data(f, t) that we will use is determined
        once at runtime."""
        if os.name == 'posix':
            self.peek_data = lambda f, t: select.select( [f], [], [], t)[0] != []
        elif os.name == 'nt' and source_type == 'named_pipe':
            self.peek_data = lambda p, t: peek_pipe(p.get_handle(), t)
        elif os.name == 'nt' and source_type == 'stream':
            self.peek_data = lambda stream, t: peek_pipe(get_pipe_from_stream(stream), t)
        else:
            # other scenarios, this is unlikely to work
            self.peek_data = lambda f, t: True 

    def open_pipe(self, pipe_name):
        if os.name == 'posix':
            # Pi, Ubuntu, WSL etc
            p = open(pipe_name, 'r')
        elif os.name == 'nt':
            # Windows
            p = Pipe(pipe_name, 'r')
        else:
            # Other
            print(f"{sys.argv[0]}: Don't know how to open incoming pipe on {os.name} "
                  f"system.", file=sys.stderr)
            raise NotImplementedError 
        return p
 
    def open_streams(self, waveform_stream_name, analysis_stream_name):
        # open the input stream fifos
        try:
            if waveform_stream_name == 'stdin':
                self.waveform_stream = sys.stdin
                self.select_peek_data_function('stream')
            else:
                self.waveform_stream = self.open_pipe(waveform_stream_name) 
                self.select_peek_data_function('named_pipe')
            if analysis_stream_name:
                self.analysis_stream = self.open_pipe(analysis_stream_name)
            self.pipes_ok = True
        except (PermissionError, FileNotFoundError, OSError):
            print(f"{sys.argv[0]}: App_Actions.open_streams() couldn't open the input streams "
                  f"{waveform_stream_name} and {analysis_stream_name}", file=sys.stderr)
            self.exit_application('error')

    def close_streams(self):
        try:
            for stream in [ self.waveform_stream, self.analysis_stream ]:
                if stream:
                    stream.close()
        except OSError:
            print(f"{sys.argv[0]}: App_Actions.close_streams() couldn't close the input streams", file=sys.stderr)

    def get_line(self, source, timeout):
        """Checks state of stream for up to timeout seconds and either reads a line of
        new data, or returns False. If the pipe is broken (empty string), will clear the pipes_ok flag."""
        try:
            # False if data isn't ready, line of data if ready, '' if pipe is broken
            l = self.peek_data(source, timeout) and source.readline()
            if l == '':
                print(f'The {source} pipe was closed.', file=sys.stderr)
                self.pipes_ok = False
            return l
        except IOError:
            print(f"{sys.argv[0]}: Data_comms.get_line() failed to read from the {source} stream.", file=sys.stderr)

    def get_waveform_line(self, timeout):
        """Returns a line of data from the waveform stream, which must be valid."""
        return self.get_line(self.waveform_stream, timeout)

    def get_analysis_line(self, timeout):
        """Returns a line of data from the analysis stream. However, if one isn't set, returns False
        and allows the program to continue."""
        if self.analysis_stream:
            return self.get_line(self.analysis_stream, timeout)
        else:
            return False



class App_Actions:

    def __init__(self):
        self.st = None             # links to other objects
        self.ui = None             # need to be immediately
        self.buffer = None         # set up after they are
        self.data_comms = None     # created, by calling set_other_objects()
        # multi_trace mode overlays traces on one background and is used to optimise
        # for high frame rates or dialog overlay
        self.multi_trace = 1
        # create custom pygame events, which we use for clearing the screen
        # and triggering a redraw of the controls
        self.clear_screen_event = pygame.event.custom_type()
        self.draw_controls_event = pygame.event.custom_type()
        self.former_run_mode = ''  # we keep track of when run mode changes


    def set_other_objects(self, st, ui, buffer, data_comms):
        self.st = st
        self.ui = ui
        self.buffer = buffer
        self.data_comms = data_comms


    def post_clear_screen_event(self):
        pygame.event.post(pygame.event.Event(self.clear_screen_event, {}))


    def post_draw_controls_event(self):
        pygame.event.post(pygame.event.Event(self.draw_controls_event, {}))


    def settings_changed(self):
        """make sure we catch latest analysis results if we are entering stopped
        state from running state, even if those results are not currently
        being displayed."""
        if self.former_run_mode!='stopped' and self.st.run_mode=='stopped':
            self.ui.catch_latest_analysis()
        self.former_run_mode = self.st.run_mode


    def start_stop(self, action='flip'):
        former_run_mode = self.st.run_mode
        if (action=='flip' and former_run_mode=='stopped') or action=='run':
            self.st.run_mode = 'running'
        elif (action=='flip' and former_run_mode=='running') or action == 'stop':
            self.st.run_mode = 'stopped'
        self.st.send_to_all()
        self.settings_changed()


    def set_updater(self, mode):
        # this placeholder function is replaced dynamically by the implementation
        # inside the ui object
        print('hellebores.py: App_Actions.set_updater() virtual function '
              'should be substituted prior to calling it.', file=sys.stderr)


    def exit_application(self, option='quit'):
        exit_codes = { 'quit'           : 0,
                       'error'          : 1,
                       'restart'        : 2,
                       'software_update': 3,
                       'shutdown'       : 4 }
        try:
            code = exit_codes[option]
        except KeyError:
            print(f"hellebores.py: App_Actions.exit_application() exit option '{option}'"
                   " isn't implemented, exiting with error code 1.", file=sys.stderr)
            code = 1
            
        self.data_comms.close_streams()
        pygame.quit()
        sys.exit(code)   # quit application with the selected exit code



def get_command_args():
    # NB argparse library adds extra backslash escape characters to strings, which we don't want
    cmd_parser = argparse.ArgumentParser(description='Read waveform and analysis (optional) '
        'data streams and provide a GUI to display them and configure the post-processing.')
    cmd_parser.add_argument('--waveform_file', default='stdin', \
        help='Path of waveform file stream or pipe.')
    cmd_parser.add_argument('--analysis_file', default=None, \
        help='Path of analysis file stream or pipe.')
    program_name = cmd_parser.prog
    args = cmd_parser.parse_args()
    return (program_name, args)


def main():
    program_name, args = get_command_args()

    # initialise pygame
    pygame.init()
    pygame.display.set_caption('PQM Hellebores')

    # fullscreen on Pi, but not on laptop
    # also make the mouse pointer invisible on Pi, as we will use the touchscreen
    # we can't make the pointer inactive using the pygame flags because we need it working
    # to return correct coordinates from the touchscreen
    if get_screen_hardware_size() == PI_SCREEN_SIZE:
        screen = pygame.display.set_mode(PI_SCREEN_SIZE, flags=pygame.FULLSCREEN)
        hide_mouse_pointer = True
    else:
        screen = pygame.display.set_mode(PI_SCREEN_SIZE)
        hide_mouse_pointer = False

    # initialise thorpy
    thorpy.set_default_font(FONT, FONT_SIZE)
    thorpy.init(screen, thorpy.theme_simple)

    # object holding the state of the application and the incoming communication streams
    app_actions  = App_Actions()
    data_comms   = Data_comms(args.waveform_file, args.analysis_file)

    # load configuration settings from settings.json into a settings object 'st'.
    # the list of 'other programs' is used to send signals when we change
    # settings in this program. We call st.send_to_all() and then
    # these programs are each told to re-read the settings file.
    st = Settings(callback_fn = app_actions.settings_changed, \
                  other_programs = [ 'scaler.py', 'framer.py', 'analyser.py' ], \
                  reload_on_signal=True)

    # objects that hold the data buffers and UI
    buffer       = Sample_Buffer(st, data_comms)
    wfs          = WFS_Counter()
    waveform     = Waveform(st, wfs, app_actions)
    multimeter   = Multimeter(st, app_actions)
    v_harmonics  = Harmonic(st, app_actions, harmonic_of_what='voltage')
    i_harmonics  = Harmonic(st, app_actions, harmonic_of_what='current')
    ui           = UI_groups(st, buffer, waveform, multimeter, v_harmonics, i_harmonics, app_actions)

    # tell app_actions how to access the other objects it needs to manipulate
    app_actions.set_other_objects(st, ui, buffer, data_comms)

    # start up in the waveform mode
    ui.app_actions.set_updater('waveform')

    # clear the analysis accumulators:
    # this causes the st.analysis_start_time parameter to be initialised in the working
    # copy of settings.json
    buffer.clear_accumulators()

    try:
        # main loop
        while True:
            # ALWAYS read new data, even if we are not capturing it, to keep the incoming data
            # pipeline flowing. If the read rate doesn't keep up with the pipe, then we will see 
            # artifacts on screen. Check if the BUFFER led on PCB is stalling if performance
            # problems are suspected here.
            # The load_waveform() function also implicitly manages display refresh speed
            # by waiting for a definite time for new data.
    
            # if multi_trace is active, read multiple frames into the buffer, otherwise just one
            for i in range(app_actions.multi_trace):
                buffer.load_waveform(wfs)
    
            # read new analysis results, if available 
            analysis_updated = buffer.load_analysis()
    
            if not data_comms.pipes_ok:
                # one or both incoming data pipes were closed, quit the application
                app_actions.exit_application('quit')
    
            # hack to make the cursor invisible while still responding to touch signals
            # would like to do this only once, rather than every trip round the loop
            # **** OPTIMISE this to test whether we need to do it only once on startup ****
            if hide_mouse_pointer:
                pygame.mouse.set_cursor(
                    (8,8), (0,0), (0,0,0,0,0,0,0,0), (0,0,0,0,0,0,0,0))
    
            # we update status texts and datetime every second
            if wfs.time_to_update():
                if st.run_mode=='running':
                    ui.get_element('datetime').set_text(time.ctime())
                ui.update_annunciators()
                # force controls - including new text - to be re-drawn
                app_actions.post_draw_controls_event()
    
            # here we process mouse/touch/keyboard events.
            events = pygame.event.get()
            for e in events:
                if (e.type == pygame.QUIT) or (e.type == pygame.KEYDOWN and e.key == pygame.K_q):
                    app_actions.exit_application('quit')
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_d:     # dots
                    waveform.plot_mode('dots')
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_l:     # lines
                    waveform.plot_mode('lines')
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_r:     # run
                    app_actions.start_stop('run')
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_s:     # stop
                    app_actions.start_stop('stop')
                elif e.type == app_actions.clear_screen_event:
                    # this event is posted when the 'mode' of the software is changed and we
                    # want to clear the screen completely
                    screen.fill(LIGHT_GREY)
                elif e.type == app_actions.draw_controls_event:
                    # we don't actually do anything here, just want the side effect of 'events'
                    # having something in it because it is tested shortly, and will cause the 
                    # controls to be re-drawn
                    pass
    
            # SCREEN REDRAWING FUNCTIONS FOLLOW
            # The 'if' conditions optimise the redraw work to reduce CPU usage.
    
            # we don't use the event handler to schedule plotting updates, because it is not
            # efficient enough for high frame rates. Instead we plot explicitly each
            # time round the loop. Depending on the current mode, waveforms, meter readings etc
            # will be drawn as necessary.
            if ui.mode == 'waveform' or events or analysis_updated:
                ui.refresh(screen)
 
            # ui.get_updater().update() is an expensive function, so we use the simplest possible
            # thorpy theme to achieve the quickest redraw time. Then, we only update/redraw when
            # buttons are pressed or the text needs updating. When there is an overlay menu displayed
            # there is more drawing work to do, so we use multi_trace to help optimise.
            if ui.overlay_dialog_active or events:
                ui.set_multi_trace()
                ui.get_updater().update(events=events)
    
            # push all of our updated work into the active display framebuffer
            if ui.mode == 'waveform' or events or ui.overlay_dialog_active or analysis_updated:
                pygame.display.flip()
    
    # General exception catch here will attempt to exit cleanly and signal to the controlling script
    # a suitable exit code, so that it knows that something went wrong.
    except Exception as e:
        print(repr(e), file=sys.stderr)
        app_actions.exit_application('error')

if __name__ == '__main__':
    main()


