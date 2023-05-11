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
import math
import pygame
import time
import sys
import os
import select
import signal
import settings



      
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
MAGENTA = (255, 0, 255)
CYAN = (0, 255, 255)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DARK_GREY = (30, 30, 30)
GREY = (75, 75, 75)
LIGHT_GREY = (100, 100, 100)
PI_SCREEN_SIZE = (800,480)
SCOPE_BOX_SIZE = (700,480)
CONTROLS_BOX_SIZE = (100,480)
CONTROLS_BOX_POSITION = (700,0)
SETTINGS_BOX_SIZE = (500,400)
SETTINGS_BOX_POSITION = (380,100)
BUTTON_SIZE = (86,50) 
ARROW_BUTTON_SIZE = (80,50)
TEXT_SIZE = (100,16)
FONT = 'dejavusansmono'
FONT_SIZE = 14
LINES_BUFFER_SIZE = 100 

# Default pygame font: freesansbold
# Ubuntu monospaced fonts:
# dejavusansmono
# ubuntumono
# bitstreamverasansmono
# nimbusmonops
# notosansmono
# notomono
 
# button enumerations
B_RUNSTOP     = 0
B_MODE        = 1
B_HORIZONTAL  = 2
B_VERTICAL    = 3
B_TRIGGER     = 4
B_OPTIONS     = 5


# text message cell enumerations
T_RUNSTOP     = 0
T_WFS         = 1
T_UNDEF2      = 2
T_UNDEF3      = 3
T_UNDEF4      = 4
T_UNDEF5      = 5


def signal_other_processes(st):
    # send a signal to everyone to update their settings
    st.set_derived_settings()
    st.save_settings()
    if sys.platform == 'linux':
        os.system("pkill -f --signal=SIGUSR1 'python3 ./rain.py'")
        os.system("pkill -f --signal=SIGUSR1 'python3 ./reader.py'")
        os.system("pkill -f --signal=SIGUSR1 'python3 ./scaler.py'")
        os.system("pkill -f --signal=SIGUSR1 'python3 ./trigger.py'")
        os.system("pkill -f --signal=SIGUSR1 'python3 ./mapper.py'")
    # update the background, in case the graticule has changed
    draw_background(st)
    

class Range_controller:
    ranges = []
    range_selector = 0
    maximum_range = 1

    def __init__(self, required_ranges, initial_index):
        self.ranges = required_ranges
        self.range_selector = initial_index
        self.maximum_range = len(required_ranges) - 1

    def get_index(self):
        return self.range_selector

    def get_value(self):
        return self.ranges[self.range_selector]

    def change_range(self, offset):
        if offset == 1:
            self.range_selector = min(self.maximum_range, self.range_selector+1)
        elif offset == -1:
            self.range_selector = max(0, self.range_selector-1)
        else:
            sys.stderr.write("Range_controller.change_range: can only change range by +1 or -1.") 



def create_datetime():
    #####
    # Datetime display
    #####
    text_datetime = thorpy.Text(time.ctime())
    text_datetime.set_font_color(WHITE)
    return [ text_datetime ]



def create_main_controls(texts):
    #####
    # Main controls, on right of screen
    #####
    button_runstop       = thorpy.Button('Run/Stop')
    button_runstop.set_size(BUTTON_SIZE)
    button_runstop.at_unclick    = lambda: start_stop_reaction(texts)

    button_mode          = thorpy.Button('Mode')
    button_mode.set_size(BUTTON_SIZE)
    button_mode.at_unclick       = mode_reaction

    button_horizontal    = thorpy.Button('Horizontal')
    button_horizontal.set_size(BUTTON_SIZE)
    button_horizontal.at_unclick = horizontal_reaction

    button_vertical      = thorpy.Button('Vertical')
    button_vertical.set_size(BUTTON_SIZE)
    button_vertical.at_unclick   = vertical_reaction

    button_trigger       = thorpy.Button('Trigger')
    button_trigger.set_size(BUTTON_SIZE)
    button_trigger.at_unclick    = trigger_reaction

    button_options       = thorpy.Button('Options')
    button_options.set_size(BUTTON_SIZE)
    button_options.at_unclick    = options_reaction

    return [ button_runstop, \
             button_mode, \
             button_horizontal, \
             button_vertical, \
             button_trigger, \
             button_options, \
             *texts.get_texts() ]


def create_vertical(st):
    #####
    # Vertical controls
    #####
    def update_voltage_range(voltages, offset):
        voltages.change_range(offset)
        display_voltage.set_text(f'{voltages.get_value()} V/div')
        st.voltage_display_index = voltages.get_index()
        signal_other_processes(st)

    def update_current_range(currents, offset):
        currents.change_range(offset)
        current_display.set_text(f'{currents.get_value()} A/div')
        st.current_display_index = currents.get_index()
        signal_other_processes(st)

    def update_power_range(powers, offset):
        powers.change_range(offset)
        power_display.set_text(f'{powers.get_value()} W/div')
        st.power_display_index = powers.get_index()
        signal_other_processes(st)

    def update_leakage_current_range(leakage_currents, offset):
        leakage_currents.change_range(offset)
        leakage_current_display.set_text(f'{leakage_currents.get_value()*1000.0} mA/div')
        st.earth_leakage_current_display_index = leakage_currents.get_index()
        signal_other_processes(st)

    button_done               = thorpy.Button('Done')
    button_done.set_size(BUTTON_SIZE)
    button_done.at_unclick    = back_to_main_reaction

    voltages                  = Range_controller(st.voltage_display_ranges, st.voltage_display_index)
    display_voltage           = thorpy.Text(f'{voltages.get_value()} V/div') 
    down_voltage              = thorpy.ArrowButton('up', ARROW_BUTTON_SIZE)
    down_voltage.at_unclick   = lambda: update_voltage_range(voltages, -1)
    up_voltage                = thorpy.ArrowButton('down', ARROW_BUTTON_SIZE)
    up_voltage.at_unclick     = lambda: update_voltage_range(voltages, 1)
 
    currents                  = Range_controller(st.current_display_ranges, st.current_display_index)
    current_display           = thorpy.Text(f'{currents.get_value()} A/div')
    current_down              = thorpy.ArrowButton('up', ARROW_BUTTON_SIZE)
    current_down.at_unclick   = lambda: update_current_range(currents, -1)
    current_up                = thorpy.ArrowButton('down', ARROW_BUTTON_SIZE)
    current_up.at_unclick     = lambda: update_current_range(currents, 1)
    
    powers                    = Range_controller(st.power_display_ranges, st.power_display_index)
    power_display             = thorpy.Text(f'{powers.get_value()} W/div')
    power_down                = thorpy.ArrowButton('up', ARROW_BUTTON_SIZE)
    power_down.at_unclick     = lambda: update_power_range(powers, -1)
    power_up                  = thorpy.ArrowButton('down', ARROW_BUTTON_SIZE)
    power_up.at_unclick       = lambda: update_power_range(powers, 1)
  
    leakage_currents          = Range_controller(st.earth_leakage_current_display_ranges, \
                                                   st.earth_leakage_current_display_index)
    leakage_current_display   = thorpy.Text(f'{leakage_currents.get_value()*1000.0} mA/div')
    leakage_current_down      = thorpy.ArrowButton('up', ARROW_BUTTON_SIZE)
    leakage_current_down.at_unclick     = lambda: update_leakage_current_range(leakage_currents, -1)
    leakage_current_up        = thorpy.ArrowButton('down', ARROW_BUTTON_SIZE)
    leakage_current_up.at_unclick       = lambda: update_leakage_current_range(leakage_currents, 1)

    return [thorpy.TitleBox(text='Vertical', children=[button_done, \
            thorpy.Group(elements=[display_voltage, down_voltage, up_voltage], mode='h'), \
            thorpy.Group(elements=[current_display, current_down, current_up], mode='h'), \
            thorpy.Group(elements=[power_display, power_down, power_up], mode='h'),
            thorpy.Group(elements=[leakage_current_display, leakage_current_down, leakage_current_up], mode='h') ])]


def create_horizontal(st):
    #####
    # Horizontal controls
    #####
    def update_time_range(times, offset):
        times.change_range(offset)
        display_time.set_text(f'{times.get_value()} ms/div')
        st.time_display_index = times.get_index()
        signal_other_processes(st)

    button_done               = thorpy.Button('Done')
    button_done.set_size(BUTTON_SIZE)
    button_done.at_unclick    = back_to_main_reaction

    times                     = Range_controller(st.time_display_ranges, st.time_display_index)
    display_time              = thorpy.Text(f'{times.get_value()} ms/div') 
    down_time                 = thorpy.ArrowButton('left', ARROW_BUTTON_SIZE)
    down_time.at_unclick      = lambda: update_time_range(times, -1)
    up_time                   = thorpy.ArrowButton('right', ARROW_BUTTON_SIZE)
    up_time.at_unclick        = lambda: update_time_range(times, 1)
 
    return [thorpy.TitleBox(text='Horizontal', children=[button_done, \
        thorpy.Group(elements=[display_time, down_time, up_time], mode='h') ])]
 

# More UI is needed for the following:
#
# Trigger settings
# Measurements-1 (summary)
# Measurements-2 (harmonics)
# Wifi setting
# Shell prompt
# Software update, rollback and Raspberry Pi OS update
# About (including software version, kernel version, uuid of Pi and Pico)
# Exit to desktop



def mode_reaction():
   pass

def horizontal_reaction():
   global ui_groups, ui_updater
   ui_updater = ui_groups['horizontal'].get_updater() 

def vertical_reaction():
   global ui_groups, ui_updater
   ui_updater = ui_groups['vertical'].get_updater() 


def trigger_reaction():
   pass

def options_reaction():
   pass


def back_to_main_reaction():
    global ui_groups, ui_updater
    ui_updater = ui_groups['main'].get_updater() 


class Texts:
    # array of thorpy text objects
    texts = []

    def __init__(self):
        for s in range(0,7):
            t = thorpy.Text('')
            t.set_size(TEXT_SIZE)
            self.texts.append(t)

    def get_texts(self):
        return self.texts

    # update text message string
    def set_text(self, item, value):
        self.texts[item].set_text(value)

    def clear_texts(self):
        for t in self.texts:
            t.set_text('')


def create_ui_groups(st, texts):
 
    ui_groups = {}

    ui_datetime = create_datetime()[0]
    ui_datetime.set_topleft(0,0)
    ui_groups['datetime'] = ui_datetime
 
    ui_main = thorpy.Box(create_main_controls(texts))
    ui_main.set_size(CONTROLS_BOX_SIZE)
    ui_main.set_topleft(*CONTROLS_BOX_POSITION)
    ui_groups['main'] = thorpy.Group(elements=[ui_main, ui_datetime], mode=None)

    ui_vertical = thorpy.Box(create_vertical(st))
    ui_vertical.set_topleft(*SETTINGS_BOX_POSITION)
    ui_groups['vertical'] = thorpy.Group(elements=[ui_main, ui_vertical, ui_datetime], mode=None)

    ui_horizontal = thorpy.Box(create_horizontal(st))
    ui_horizontal.set_topleft(*SETTINGS_BOX_POSITION)
    ui_groups['horizontal'] = thorpy.Group(elements=[ui_main, ui_horizontal, ui_datetime], mode=None)

    return ui_groups


def start_stop_reaction(texts):
   global capturing
   if capturing == True:
       capturing = False
       texts.set_text(T_RUNSTOP, "Stopped")
   else:
       capturing = True
       texts.set_text(T_RUNSTOP, "Running")
       

def options_reaction():
    alert = thorpy.Alert(title="hellebores.py",
                         text="Power quality meter, v0.03",
                         ok_text="Ok, I've read")
    alert.set_draggable()
    alert.cannot_drag_outside = True
    alert.launch_nonblocking()


def refresh_reaction(lines, screen, background_surface, wfs):
    global capturing
    if capturing:
        lines.read_lines(sys.stdin, wfs)
    # blit the screen with background image (graticule)
    # if we didn't capture new lines, we still redraw the old ones
    screen.blit(background_surface, (0,0))
    draw_lines(screen, lines.get_lines())
    

def draw_background(st):
    xmax = SCOPE_BOX_SIZE[0] - 1
    ymax = SCOPE_BOX_SIZE[1] - 1

    # empty background
    background_surface = pygame.Surface(SCOPE_BOX_SIZE)
    background_surface.fill(GREY)

    # draw the graticule lines
    for dx in range(1, st.time_axis_divisions):
        x = st.horizontal_pixels_per_division * dx
        # mark the trigger position (t=0) with a thicker line
        if dx == st.time_axis_pre_trigger_divisions:
            lc = WHITE
        else:
            lc = LIGHT_GREY
        pygame.draw.line(background_surface, lc, (x, 0), (x, ymax), 1)
    for dy in range(1, st.vertical_axis_divisions):
        y = st.vertical_pixels_per_division * dy
        # mark the central position (v, i = 0) with a thicker line
        if dy == st.vertical_axis_divisions // 2:
            lc = WHITE
        else:
            lc = LIGHT_GREY
        pygame.draw.line(background_surface, lc, (0, y), (xmax, y), 1)
    return background_surface


def draw_lines(screen, lines):
    # can handle up to six lines
    colours = [ GREEN, YELLOW, MAGENTA, CYAN, RED, BLUE ]
    try:
        for i in range(len(lines)):
            pygame.draw.lines(screen, colours[i], False, lines[i], 2)
    except:
        pass


class WFS_Counter:

    def __init__(self):
        self.counter = 0           # number of waveforms since last posting
        self.time = time.time()    # keep track of time in milliseconds
        self.posted = self.time    # time when the wfs/s was lasted posted to screen

    # called whenever we update the waveform on screen 
    def increment_wfs(self):
        self.counter = self.counter + 1

    # called when a refresh event occurs (image isn't always updated)
    def refresh_wfs(self, texts):
        # time check 
        self.time = time.time()
        # if the time has increased by at least 1.0 second, update the wfm/s text
        elapsed = self.time - self.posted
        if elapsed >= 1.0:
            texts.set_text(T_WFS, f'{round(self.counter/elapsed)} wfm/s')
            self.posted = self.time
            self.counter = 0
 

def get_screen_hardware_size():
    i = pygame.display.Info()
    return i.current_w, i.current_h


def is_data_available(f, t):
    # f file object, t time in seconds
    # unfortunately this test won't work on windows, so we return a default response
    is_available = True
    if sys.platform == 'linux':
        # wait at most 't' seconds for new data to appear
        r, _, _ = select.select( [f], [], [], t)
        if len(r) == 0:   
           is_available = False 
    return is_available


class Lines:
    # working points buffer, persistent across multiple calls to read_lines()
    ps = []

    # lines history buffer
    # future extension is to use this buffer for electrical event history
    # (eg triggered by power fluctuation etc)
    lines_history = ['' for i in range(LINES_BUFFER_SIZE+1)]

    # this function will perform best if the source process (eg trigger.py) flushes its
    # output buffer every frame. That way, the 'is_data_available()' function will succeed
    # when there is a complete new frame available, rather than half-way through a frame.
    def read_lines(self, f, wfs):
        xp = 0
        x_max = st.x_pixels - 1
        # the loop will exit
        # (a) there is no more data waiting to be read, 
        # (b) if the time coordinate 'goes backwards', or
        # (c) if the line is empty and can't be split()
        while is_data_available(f, 0.02): 
            try:
                ws = f.readline().split()
                x = int(ws[0])
                if x < xp:
                    break       # exit now if x (time) coordinate is lower than previous one
                ws = ws[1:]
                for i in range(len(ws)):
                    try:
                        self.ps[i].append((x, int(ws[i])))   # extend an existing line
                    except IndexError:
                        self.ps.append( [(x, int(ws[i]))] )  # or add another line if it doesn't exist yet
            except:
                break           # exit if we have any other type of error with the input data
            xp = x
        # if we got a complete capture, save it as last item in history
        # and increment the wfs counter
        if self.ps != [] and self.ps[0][-1][0] == x_max:
            self.lines_history[LINES_BUFFER_SIZE] = self.ps
            wfs.increment_wfs()
            self.ps = []
        return self.lines_history[LINES_BUFFER_SIZE]

    def save_lines(self):
        self.lines_history = self.lines_history[1:]
        self.lines_history.append('')

    def get_lines(self, index = LINES_BUFFER_SIZE):
        if (index < 0) or (index > LINES_BUFFER_SIZE):
            index = LINES_BUFFER_SIZE
        return self.lines_history[index]

    def __init__(self):
        pass


def main():
    global st, capturing, ui_groups, ui_updater

    # initialise pygame
    #application = thorpy.Application(PI_SCREEN_SIZE, 'pqm-hellebores')
    pygame.init()
    pygame.display.set_caption('pqm-hellebores')

    # fullscreen on Pi, but not on laptop
    # also make the mouse pointer invisible on Pi, as we will use the touchscreen
    # we can't make the pointer inactive using the pygame flags because we need it working
    # to return correct coordinates from the touchscreen
    if get_screen_hardware_size() == PI_SCREEN_SIZE:
        screen    = pygame.display.set_mode(PI_SCREEN_SIZE, flags=pygame.FULLSCREEN)
    else:
        screen    = pygame.display.set_mode(PI_SCREEN_SIZE)

    # initialise thorpy
    thorpy.set_default_font(FONT, FONT_SIZE)
    thorpy.init(screen, thorpy.theme_classic)

    # get settings from settings.json
    st = settings.Settings(None)

    # create objects that hold the state of the UI
    background_surface = draw_background(st)
    texts     = Texts()
    wfs       = WFS_Counter()
    ui_groups = create_ui_groups(st, texts)

    # start with the main group enabled
    ui_updater = ui_groups['main'].get_updater()

    # set up the initial text states
    texts.set_text(T_RUNSTOP, "Running")

    # set up lines object
    lines = Lines()
    
    # initialise flags
    capturing = True        # allow/stop update of the lines on the screen
    running   = True        # program runs until this flag is cleared

    # main loop
    while running:
        # hack to make the cursor invisible while still responding
        # pygame.mouse.set_cursor((8,8),(0,0),(0,0,0,0,0,0,0,0),(0,0,0,0,0,0,0,0))
        events = pygame.event.get()
        for e in events:
            if (e.type == pygame.QUIT) or (e.type == pygame.KEYDOWN and e.key == pygame.K_q):
                running = False
        refresh_reaction(lines, screen, background_surface, wfs)
        wfs.refresh_wfs(texts)
        if capturing:
            ui_groups['datetime'].set_text(time.ctime())
        #ui_groups['datetime'].draw()
        ui_updater.update(events=events)
        pygame.display.flip()

    pygame.quit()



if __name__ == '__main__':
    main()


