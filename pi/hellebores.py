#!/usr/bin/env python3

# figlet
#  _          _ _      _                                       
# | |__   ___| | | ___| |__   ___  _ __ ___  ___   _ __  _   _ 
# | '_ \ / _ \ | |/ _ \ '_ \ / _ \| '__/ _ \/ __| | '_ \| | | |
# | | | |  __/ | |  __/ |_) | (_) | | |  __/\__ \_| |_) | |_| |
# |_| |_|\___|_|_|\___|_.__/ \___/|_|  \___||___(_) .__/ \__, |
#                                                 |_|    |___/ 
#

import thorpy
import pygame
import time
import sys
import os
import select
import settings
from hellebores_constants import *
from hellebores_controls import *
from hellebores_waveform import Waveform
from hellebores_multimeter import Multimeter


# More UI is needed for the following:
#
# Measurements-1 (summary)
# Measurements-2 (harmonics)
# Wifi setting
# Shell prompt
# Software update, rollback and Raspberry Pi OS update
# About (including software version, kernel version, uuid of Pi and Pico)
# Exit to desktop

# The instance of this class will hold all the user interface states or 'groups'
# that can be displayed together with the currently active selection
class UI_groups:
    elements = {}
    updater = None
    mode = 'waveform'
    current_range = 'full'
    instruments = {}

    def __init__(self, st, waveform, multimeter, reaction_fns):
        self.instruments['waveform'] = waveform
        self.instruments['multimeter'] = multimeter

        self.elements['datetime'] = create_datetime()[0]
        self.elements['datetime'].set_topleft(0,0)

        # waveform group
        self.elements['waveform'] = waveform.create_waveform_controls()
        self.elements['waveform'].set_size(CONTROLS_BOX_SIZE)
        self.elements['waveform'].set_topright(*CONTROLS_BOX_POSITION)

        # multi-meter group
        self.elements['multimeter'] = multimeter.create_multimeter_controls()
        self.elements['multimeter'].set_size(CONTROLS_BOX_SIZE)
        self.elements['multimeter'].set_topright(*CONTROLS_BOX_POSITION)

        # voltage harmonic group
        #ui_voltage_harmonic = create_voltage_harmonic_controls(texts)
        #ui_voltage_harmonic.set_size(CONTROLS_BOX_SIZE)
        #ui_voltage_harmonic.set_topright(*CONTROLS_BOX_POSITION)
        #self.elements['voltage_harmonic'] = ui_voltage_harmonic

        # current harmonic group
        #ui_current_harmonic = create_current_harmonic_controls(texts)
        #ui_current_harmonic.set_size(CONTROLS_BOX_SIZE)
        #ui_current_harmonic.set_topright(*CONTROLS_BOX_POSITION)
        #self.elements['current_harmonic'] = ui_current_harmonic

        # control groups that overlay the main group when adjusting settings
        self.elements['mode'] = create_mode(reaction_fns)
        self.elements['current_range'] = create_current_range(reaction_fns)
        self.elements['vertical'] = create_vertical(st, reaction_fns)
        self.elements['horizontal'] = create_horizontal(st, reaction_fns)
        self.elements['trigger'] = create_trigger(st, waveform, reaction_fns)
        self.elements['options'] = create_options(waveform, reaction_fns)

        for k in ['mode', 'current_range', 'vertical', 'horizontal', 'trigger', 'options']:
            self.elements[k].set_topright(*SETTINGS_BOX_POSITION)

        # re-point the updater function in the external object to target the function in this object
        # NB dynamically altering a function definition is a relatively unusual programming move
        reaction_fns.set_updater = self.set_updater

    def set_current_range(self, required_range):
        self.current_range = required_range

    def refresh(self, buffer, screen):
        self.instruments[self.mode].refresh(buffer, screen)

    def draw_texts(self, capturing):
        self.instruments[self.mode].draw_texts(capturing)

    def set_updater(self, elements_group):
        # for 'waveform', 'multimeter', 'voltage_harmonic', 'current_harmonic',
        # we retain the group in a 'mode' variable for recall after menu selections.
        try:
            if elements_group in ['waveform', 'multimeter', 'voltage_harmonic', 'current_harmonic']:
                # if we picked a different display mode, store it in 'self.mode'.
                self.mode = elements_group
                elements = [ 
                    self.elements[self.mode],
                    self.elements['datetime']
                    ]
            elif elements_group == 'back':
                # if we picked 'back', then just use the pre-existing mode
                elements = [
                    self.elements[self.mode],
                    self.elements['datetime']
                    ]
            else:
                # otherwise, use the pre-existing mode and add the selected overlay
                # elements to it.
                elements = [
                    self.elements[self.mode],
                    self.elements[elements_group],
                    self.elements['datetime']
                    ]
            self.updater = thorpy.Group(elements=elements, mode=None).get_updater()
        except:
            print(
                'UI_groups.set_updater(): group parameter not recognised.\n',
                file=sys.stderr)

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


# the version of is_data_available that we will use is determined
# once at runtime
if os.name == 'posix':
    # f is file object to test for reading, t is time in seconds
    # wait at most 't' seconds for new data to appear
    # element 0 of tuple will be an empty list unless there is data ready to read
    is_data_available = lambda f, t: select.select( [f], [], [], t)[0] != []
else:
    # unfortunately this test isn't easy to implement on windows
    # so we return a default 'True' response
    is_data_available = lambda f, t: True
 

class Sample_Buffer:
    # working points buffer for four lines
    ps = [ [],[],[],[] ] 

    # sample buffer history
    # future extension is to use this buffer for electrical event history
    # (eg triggered by power fluctuation etc)
    sample_buffer_history = [[] for i in range(SAMPLE_BUFFER_SIZE+1)]
    xp = -1                 # tracks previous 'x coordinate'

    def end_frame(self, capturing, wfs):
        if capturing:
            self.sample_buffer_history[SAMPLE_BUFFER_SIZE] = self.ps
            wfs.increment()
        # reset the working buffer
        self.ps = [ [],[],[],[] ]

    def add_sample(self, sample):
        self.ps[0].append((sample[0], sample[1]))
        self.ps[1].append((sample[0], sample[2]))
        self.ps[2].append((sample[0], sample[3]))
        self.ps[3].append((sample[0], sample[4]))

    def load_buffer(self, f, capturing, wfs):
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
                ws = f.readline().split()
                sample = [ int(w) for w in ws[:5] ]
                if ws[-1] == '*END*':
                    # add current sample then end the frame
                    self.add_sample(sample)
                    self.end_frame(capturing, wfs)
                    self.xp = -1
                    return True
                elif sample[0] < self.xp:
                    # x coordinate has reset to indicate start of new frame...
                    # end the frame before adding current sample to a new one
                    self.end_frame(capturing, wfs)    
                    self.add_sample(sample)
                    self.xp = -1
                    return True
                else:
                    # an ordinary, non-special, sample
                    self.add_sample(sample)
                self.xp = sample[0]
                sample_counter = sample_counter + 1
            except:
                break   # break if we have any type of error with the input data
        return False

    def save_buffer(self):
        self.sample_buffer_history = self.sample_buffer_history[1:]
        self.sample_buffer_history.append('')

    def get_buffer(self, index = SAMPLE_BUFFER_SIZE):
        if (index < 0) or (index > SAMPLE_BUFFER_SIZE):
            index = SAMPLE_BUFFER_SIZE
        return self.sample_buffer_history[index]

    def __init__(self):
        pass


def main():

    # initialise pygame
    pygame.init()
    pygame.display.set_caption('pqm-hellebores')

    # fullscreen on Pi, but not on laptop
    # also make the mouse pointer invisible on Pi, as we will use the touchscreen
    # we can't make the pointer inactive using the pygame flags because we need it working
    # to return correct coordinates from the touchscreen
    if get_screen_hardware_size() == PI_SCREEN_SIZE:
        screen    = pygame.display.set_mode(PI_SCREEN_SIZE, flags=pygame.FULLSCREEN)
        hide_mouse_pointer = True
    else:
        screen    = pygame.display.set_mode(PI_SCREEN_SIZE)
        hide_mouse_pointer = False

    # initialise thorpy
    thorpy.set_default_font(FONT, FONT_SIZE)
    thorpy.init(screen, thorpy.theme_simple)

    # load configuration settings from settings.json into a settings object 'st'.
    # the list of 'other programs' is used to send signals when we change
    # settings in this program. We call st.send_to_all() and then
    # these programs are each told to re-read the settings file.
    st = settings.Settings(
        other_programs = [
            'rain.py',
            'reader.py',
            'scaler.py',
            'trigger.py',
            'mapper.py'
            ])


    class Reaction_Functions:
        capturing = True        # allow/stop update of the lines on the screen

        def start_stop(self):
            self.capturing = not self.capturing

        def set_updater(self, mode):
            # this placeholder function is replaced dynamically by the implementation
            # inside the ui object
            pass

        def exit_application(self, option='quit'):
            exit_codes = { 'quit': 0, 'restart': 2, 'software_update': 3, 'shutdown': 4, }
            pygame.quit()
            sys.exit(exit_codes[option])



 
    # create objects that hold the state of the UI
    reaction_fns = Reaction_Functions()
    wfs          = WFS_Counter()
    waveform     = Waveform(st, wfs, reaction_fns)
    multimeter   = Multimeter(st, reaction_fns)
    ui           = UI_groups(st, waveform, multimeter, reaction_fns)

    # start with the waveform group enabled
    reaction_fns.set_updater('waveform')

    # set up a sample buffer object
    buffer = Sample_Buffer()
    

    # main loop
    while True:
        # hack to make the cursor invisible while still responding to touch signals
        # would like to do this only once, rather than every trip round the loop
        if hide_mouse_pointer:
            pygame.mouse.set_cursor(
                (8,8), (0,0), (0,0,0,0,0,0,0,0), (0,0,0,0,0,0,0,0))
        # we update status texts and datetime every second
        if wfs.time_to_update():
            if reaction_fns.capturing == True:
                ui.get_element('datetime').set_text(time.ctime())
            ui.draw_texts(reaction_fns.capturing)

        # ALWAYS read new data, even if we are not capturing it, to keep the incoming data
        # pipeline flowing. If the read rate doesn't keep up with the pipe, then we will see 
        # artifacts on screen. Check if the BUFFER led on PCB is stalling if performance
        # problems are suspected here.
        # The load_buffer() function also implicitly manages display refresh speed when not
        # capturing, by waiting for a definite time for new data.
        got_new_frame = buffer.load_buffer(sys.stdin, reaction_fns.capturing, wfs)
       
        # we don't use the event handler to schedule plotting updates, because it is not
        # efficient enough for high frame rates. Instead we plot explicitly when needed, every
        # time round the loop. 
        ui.refresh(buffer, screen)

        # here we process mouse/touch/keyboard events.
        events = pygame.event.get()
        for e in events:
            if (e.type == pygame.QUIT) or (e.type == pygame.KEYDOWN and e.key == pygame.K_q):
                reaction_fns.exit_application('quit')
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_d:
                waveform.plot_mode('dots')
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_l:
                waveform.plot_mode('lines')
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_r:
                reaction_fns.capturing = True
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_s:
                reaction_fns.capturing = False

        # ui_current_updater.update() is an expensive function, so we use the simplest possible
        # thorpy theme to achieve highest performance/frame rate
        ui.get_updater().update(events=events)
        # push all of our updated work into the active display framebuffer
        pygame.display.flip()


if __name__ == '__main__':
    main()


