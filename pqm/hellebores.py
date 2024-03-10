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
import select

# local imports
from settings import Settings
from hellebores_constants import *
from hellebores_controls import *
from hellebores_waveform import Waveform
from hellebores_multimeter import Multimeter
if os.name == 'nt':
    from mswin_pipes import Pipe


# More UI is needed for the following:
#
# Measurements-1 (summary)
# Measurements-2 (harmonics)
# rollback NOT IMPLEMENTED
# About (including software version, kernel version, uuid of Pi and Pico)

# The instance of this class will hold all the user interface states or 'groups'
# that can be displayed together with the currently active selection
class UI_groups:
    elements = {}
    mode = 'waveform'
    instruments = {}
    # the flag helps to reduce workload of screen refresh when there are overlay menus.
    overlay_dialog_active = False

    def __init__(self, st, waveform, multimeter, app_actions):
        # make a local reference to app_actions and st
        self.app_actions = app_actions
        self.st = st

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

        # current harmonic group

        # control groups that overlay the main group when adjusting settings
        self.elements['mode'] = create_mode(app_actions)
        self.elements['current_range'] = create_current_range(app_actions)
        self.elements['vertical'] = create_vertical(st, app_actions)
        self.elements['horizontal'] = create_horizontal(st, app_actions)
        self.elements['trigger'] = create_trigger(st, waveform, app_actions)
        self.elements['options'] = create_options(waveform, app_actions)

        for k in ['mode', 'current_range', 'vertical', 'horizontal', 'trigger', 'options']:
            self.elements[k].set_topright(*SETTINGS_BOX_POSITION)

    def set_current_range(self, required_range):
        self.current_range = required_range

    def refresh(self, buffer, screen):
        """dispatch to the refresh method of the element group currently selected."""
        if self.mode == 'waveform' and self.app_actions.capturing:
            # if capturing, we might display multiple frames in one display
            self.instruments[self.mode].refresh(buffer, self.app_actions.multi_trace, screen, self.elements['datetime'])
        elif self.mode == 'waveform':
            # but just one frame if in stopped mode
            self.instruments[self.mode].refresh(buffer, 1, screen, self.elements['datetime'])
        else:
            self.instruments[self.mode].refresh(buffer, screen, self.elements['datetime'])

    def draw_texts(self, capturing):
        self.instruments[self.mode].draw_texts(capturing)

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
        except:
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
        self.counter = self.counter + 1

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


# the version of is_data_available(f, t) that we will use is determined
# once at runtime
if os.name == 'posix':
    # f is file object to test for reading, t is time in seconds
    # wait at most 't' seconds for new data to appear
    # element 0 of tuple will be an empty list unless there is data ready to read
    is_data_available = lambda f, t: select.select( [f], [], [], t)[0] != []
elif os.name == 'nt':
    # simulated functionality for windows, which lacks the 'select' function 
    is_data_available = lambda p, t: p.is_data_available(t)
else:
    # other scenarios, this is unlikely to work
    is_data_available = lambda f, t: True 


class Sample_Buffer:

    def __init__(self):
        # working points buffer for four lines, calculation array
        # flag for detecting when pipes are closed (end of file)
        self.ps = [ [],[],[],[] ]           # points
        self.cs = []                        # calculations
        self.pipes_ok = True
        # sample buffer history
        # future extension is to use this buffer for electrical event history
        # (eg triggered by power fluctuation etc)
        self.sample_waveform_history = [ [] for i in range(SAMPLE_BUFFER_SIZE) ]
        # tracks previous 'x coordinate'
        self.xp = -1

    def end_frame(self, capturing, wfs):
        if capturing:
            # shift the history buffer along and append the new capture
            self.sample_waveform_history = self.sample_waveform_history[1:]
            self.sample_waveform_history.append(self.ps)
            #self.sample_waveform_history[SAMPLE_BUFFER_SIZE] = self.ps
            wfs.increment()
        # reset the working buffer
        self.ps = [ [],[],[],[] ]

    def add_sample(self, sample):
        self.ps[0].append((sample[0], sample[1]))
        self.ps[1].append((sample[0], sample[2]))
        self.ps[2].append((sample[0], sample[3]))
        self.ps[3].append((sample[0], sample[4]))

    def load_analysis(self, f, capturing):
        # incoming analysis data is optional
        if f and is_data_available(f, 0.0):
            try:
                l = f.readline()
                # read() and readline() return empty strings if the source of the pipe is closed
                # so we immediately test for that
                if l == '':
                    print('Analysis pipe was closed.', file=sys.stderr)
                    self.pipes_ok = False
                # then break the analysis into tokens
                analysis_items = l.split()
                if len(analysis_items) > 0:
                    self.cs = analysis_items
                    sys.stdout.write('.')
                    sys.stdout.flush()
            except:
                print('hellebores.py: Sample_Buffer.load_analysis()'
                      ' file reading error.', file=sys.stderr) 


    def load_waveform(self, f, capturing, wfs):
        # the loop will exit if:
        # (a) there is no data currently waiting to be read, 
        # (b) negative x coordinate indicates last sample of current frame
        # (c) the x coordinate 'goes backwards' indicating a new frame has started
        # (d) the line is empty, can't be split() or any other kind of read error
        # (e) more than 1000 samples have been read (this keeps the UI responsive)
        # returns 'True' if we have completed a new frame
        sample_counter = 0
        while is_data_available(f, 0.05) and sample_counter < 1000: 
            try:
                l = f.readline()
                if l == '':
                    print('Waveform pipe was closed.', file=sys.stderr)
                    self.pipes_ok = False
                    break
                ws = l.split()
                sample = [ int(w) for w in ws[:5] ]
                if ws[-1] == '*END*':
                    # add current sample then end the frame
                    self.add_sample(sample)
                    self.end_frame(capturing, wfs)
                    self.xp = -1
                    break
                elif sample[0] < self.xp:
                    # x coordinate has reset to indicate start of new frame...
                    # end the frame before adding current sample to a new one
                    self.end_frame(capturing, wfs)    
                    self.add_sample(sample)
                    self.xp = -1
                    break
                else:
                    # an ordinary, non-special, sample
                    self.add_sample(sample)
                self.xp = sample[0]
                sample_counter = sample_counter + 1
            except:
                print('hellebores.py: Sample_Buffer.load_analysis()'
                      ' file reading error.', file=sys.stderr) 
                break

    def get_waveform(self, index=0):
        # reverse into history by 'index' frames
        return self.sample_waveform_history[SAMPLE_BUFFER_SIZE-1-index]


class App_Actions:

    def __init__(self, waveform_stream_name, analysis_stream_name):
        # open the streams (input data pipe files)
        self.open_streams(waveform_stream_name, analysis_stream_name)
        # allow/stop update of the lines on the screen
        self.capturing = True
        # multi_trace mode overlays traces on one background and is used to optimise
        # for high frame rates or dialog overlay
        self.multi_trace = 1
        # create custom pygame events, which we use for clearing the screen
        # and triggering a redraw of the controls
        self.clear_screen_event = pygame.event.custom_type()
        self.draw_controls_event = pygame.event.custom_type()

    def open_pipe(self, file_name):
        if os.name == 'posix':
            # Pi, Ubuntu, WSL etc
            p = open(file_name, 'r')
        elif os.name == 'nt':
            # Windows
            p = Pipe(file_name, 'r')
        else:
            # Other
            print(f"{sys.argv[0]}: Don't know how to open incoming pipe on {os.name} system.", file=sys.stderr)
            raise NotImplementedError 
        return p
 
    def open_streams(self, waveform_stream_name, analysis_stream_name):
        # open the input stream fifos
        try:
            if waveform_stream_name != None:
                self.waveform_stream = self.open_pipe(waveform_stream_name) 
            else:
                self.waveform_stream = sys.stdin
            if analysis_stream_name != None:
                self.analysis_stream = self.open_pipe(analysis_stream_name)
            else:
                self.analysis_stream = None
        except:
            print(f"{sys.argv[0]}: App_Actions.open_streams() couldn't open the input streams "
                  f"{waveform_stream_name} and {analysis_stream_name}", file=sys.stderr)
            self.exit_application('error')

    def close_streams(self):
        try:
            self.waveform_stream.close()
            self.analysis_stream.close() 
        except:
            print(f"{sys.argv[0]}: App_Actions.close_streams() couldn't close the input streams", file=sys.stderr)


    def post_clear_screen_event(self):
        pygame.event.post(pygame.event.Event(self.clear_screen_event, {}))

    def post_draw_controls_event(self):
        pygame.event.post(pygame.event.Event(self.draw_controls_event, {}))

    def start_stop(self):
        self.capturing = not self.capturing

    def set_updater(self, mode):
        # this placeholder function is replaced dynamically by the implementation
        # inside the ui object
        print('hellebores.py: App_Actions.set_updater() virtual function '
              'should be substituted prior to calling it.', file=sys.stderr)

    def exit_application(self, option='quit'):
        exit_codes = { 'quit': 0,
                       'error': 1,
                       'restart': 2,
                       'software_update': 3,
                       'shutdown': 4 }
        try:
            code = exit_codes[option]
        except:
            print(f"hellebores.py: App_Actions.exit_application() exit option '{option}'"
                   " isn't implemented, exiting with error code 1.", file=sys.stderr)
            code = 1
            
        self.close_streams()
        pygame.quit()
        sys.exit(code)   # quit application with the selected exit code



def main():
    # get names of stream files from the command line, or use stdin
    if len(sys.argv) == 3:
        # read incoming data from named pipes
        waveform_stream_name = sys.argv[1]
        analysis_stream_name = sys.argv[2]
    elif len(sys.argv) == 1:
        # read incoming data from stdin (waveform only)
        waveform_stream_name = None
        analysis_stream_name = None
    else:
        print(f"Usage: {sys.argv[0]} [waveform_stream_name] [analysis_stream_name].", file=sys.stderr)
        sys.exit(1)

    # initialise pygame
    pygame.init()
    pygame.display.set_caption('pqm-hellebores')

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

    # load configuration settings from settings.json into a settings object 'st'.
    # the list of 'other programs' is used to send signals when we change
    # settings in this program. We call st.send_to_all() and then
    # these programs are each told to re-read the settings file.
    st = Settings(other_programs = [ 'scaler.py', 'trigger.py', 'mapper.py' ],
                  reload_on_signal=False)

    # create objects that hold the state of the application and UI
    app_actions  = App_Actions(waveform_stream_name, analysis_stream_name)
    wfs          = WFS_Counter()
    waveform     = Waveform(st, wfs, app_actions)
    multimeter   = Multimeter(st, app_actions)
    ui           = UI_groups(st, waveform, multimeter, app_actions)

    # start up in the waveform mode
    ui.app_actions.set_updater('waveform')

    # set up a sample buffer object
    buffer = Sample_Buffer()

    # main loop
    while True:
        # ALWAYS read new data, even if we are not capturing it, to keep the incoming data
        # pipeline flowing. If the read rate doesn't keep up with the pipe, then we will see 
        # artifacts on screen. Check if the BUFFER led on PCB is stalling if performance
        # problems are suspected here.
        # The load_waveform() function also implicitly manages display refresh speed when not
        # capturing, by waiting for a definite time for new data.

        # if multi_trace is active, read multiple frames into the buffer, otherwise just one
        for i in range(app_actions.multi_trace):
            buffer.load_waveform(app_actions.waveform_stream, app_actions.capturing, wfs)

        # read new analysis results, if available 
        buffer.load_analysis(app_actions.analysis_stream, app_actions.capturing)

        if buffer.pipes_ok == False:
            # one or both incoming data pipes were closed, quit the application
            app_actions.exit_application('quit')

        # hack to make the cursor invisible while still responding to touch signals
        # would like to do this only once, rather than every trip round the loop
        if hide_mouse_pointer:
            pygame.mouse.set_cursor(
                (8,8), (0,0), (0,0,0,0,0,0,0,0), (0,0,0,0,0,0,0,0))

        # we update status texts and datetime every second
        if wfs.time_to_update():
            if app_actions.capturing == True:
                ui.get_element('datetime').set_text(time.ctime())
            ui.draw_texts(app_actions.capturing)
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
                app_actions.capturing = True
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_s:     # stop
                app_actions.capturing = False
            elif e.type == app_actions.clear_screen_event:
                # this event is posted when the 'mode' of the software is changed and we
                # want to clear the screen completely
                screen.fill(LIGHT_GREY)
            elif e.type == app_actions.draw_controls_event:
                # we don't actually do anything here, just want the side effect of 'events'
                # having something in it because it is tested next, and will cause the 
                # controls to be re-drawn
                pass

        # we don't use the event handler to schedule plotting updates, because it is not
        # efficient enough for high frame rates. Instead we plot explicitly each
        # time round the loop. Depending on the current mode, waveforms, meter readings etc
        # will be drawn as necessary.
        ui.refresh(buffer, screen)

        # ui.get_updater().update() is an expensive function, so we use the simplest possible
        # thorpy theme to achieve the quickest redraw time. Then, we only update/redraw when
        # buttons are pressed or the text needs updating. When there is an overlay menu displayed
        # there is more drawing work to do, so we use multi_trace to help optimise.
        if events or ui.overlay_dialog_active:
            ui.set_multi_trace()
            ui.get_updater().update(events=events)

        # push all of our updated work into the active display framebuffer
        pygame.display.flip()


if __name__ == '__main__':
    main()


