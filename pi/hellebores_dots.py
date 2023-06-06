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
VERY_LIGHT_GREY = (150, 150, 150)
PI_SCREEN_SIZE = (800,480)
SCOPE_BOX_SIZE = (700,480)
CONTROLS_BOX_SIZE = (100,480)        # main buttons and status texts
CONTROLS_BOX_POSITION = (800,0)      # top right corner
SETTINGS_BOX_SIZE = (500,400)        # 'dialog' boxes
SETTINGS_BOX_POSITION = (690,100)    # top right corner
BUTTON_SIZE = (90,50) 
ARROW_BUTTON_SIZE = (90,50)
TEXT_SIZE = (90,16)
TEXT2_SIZE = (120,16)
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
T_TIMEDIV     = 2
T_VOLTSDIV    = 3
T_AMPSDIV     = 4
T_WATTSDIV    = 5
T_LEAKDIV     = 6


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


def configure_switch_button(value, callback_function):
    button = thorpy.SwitchButton(value, size=BUTTON_SIZE, \
                 drag_size=(BUTTON_SIZE[0]//3, BUTTON_SIZE[1]//2))
    button.set_bck_color(VERY_LIGHT_GREY, 'normal')
    button.set_bck_color(VERY_LIGHT_GREY, 'hover')
    button.set_font_color(WHITE)
    button.at_unclick = callback_function
    return button

def configure_arrow_button(direction, callback_function):
    button = thorpy.ArrowButton(direction, BUTTON_SIZE) 
    button.set_bck_color(VERY_LIGHT_GREY, 'normal')
    button.set_bck_color(VERY_LIGHT_GREY, 'hover')
    button.set_font_color(WHITE)
    button.at_unclick = callback_function
    return button
 
def configure_button(text, callback_function):
    button = thorpy.Button(text) 
    button.set_bck_color(VERY_LIGHT_GREY, 'normal')
    button.set_bck_color(VERY_LIGHT_GREY, 'hover')
    button.set_font_color(WHITE)
    button.set_size(BUTTON_SIZE)
    button.at_unclick = callback_function
    return button
    
def create_main_controls(texts):
    #####
    # Main controls, on right of screen
    #####
    button_setup = [ ('Run/Stop', lambda: start_stop_reaction(texts)),\
                     ('Mode', mode_reaction), \
                     ('Horizontal', horizontal_reaction), \
                     ('Vertical', vertical_reaction), \
                     ('Trigger', trigger_reaction), \
                     ('Options', options_reaction) ]
    buttons = [ configure_button(bt, bf) for bt, bf in button_setup ]
 
    main = thorpy.Box([ *texts.get()[0:2], *buttons, *texts.get()[2:] ])
    main.set_bck_color(LIGHT_GREY)
    for e in main.get_all_descendants():
        e.hand_cursor = False    
    return main


def create_vertical(st):
    #####
    # Vertical controls
    #####
    def update_voltage_range(voltages, offset):
        voltages.change_range(offset)
        voltage_display.set_text(f'{voltages.get_value()} V/div', adapt_parent=False)
        st.voltage_display_index = voltages.get_index()
        st.send_to_all()

    def update_current_range(currents, offset):
        currents.change_range(offset)
        current_display.set_text(f'{currents.get_value()} A/div', adapt_parent=False)
        st.current_display_index = currents.get_index()
        st.send_to_all() 

    def update_power_range(powers, offset):
        powers.change_range(offset)
        power_display.set_text(f'{powers.get_value()} W/div', adapt_parent=False)
        st.power_display_index = powers.get_index()
        st.send_to_all()

    def update_leakage_current_range(leakage_currents, offset):
        leakage_currents.change_range(offset)
        leakage_current_display.set_text(f'{leakage_currents.get_value()*1000.0} mA/div', adapt_parent=False)
        st.earth_leakage_current_display_index = leakage_currents.get_index()
        st.send_to_all()

    def flip_display_switch(channel, switch_status):
        if channel == 'voltage':
            st.voltage_display_status = switch_status
        elif channel == 'current':
            st.current_display_status = switch_status
        elif channel == 'power':
            st.power_display_status = switch_status
        elif channel == 'leakage':
            st.earth_leakage_current_display_status = switch_status
        else:
            print('hellebores.py: flip_display_switch() channel not recognised.', file=sys.stderr)
        st.send_to_all()

    button_done = configure_button('Done', back_to_main_reaction)

    voltages                  = Range_controller(st.voltage_display_ranges, st.voltage_display_index)
    voltage_onoff             = configure_switch_button(st.voltage_display_status, \
                                    lambda: flip_display_switch('voltage', voltage_onoff.value))
    voltage_display           = thorpy.Text(f'{voltages.get_value()} V/div') 
    voltage_display.set_size(TEXT2_SIZE)
    voltage_down              = configure_arrow_button('up', \
                                    lambda: update_voltage_range(voltages, -1))
    voltage_up                = configure_arrow_button('down', \
                                    lambda: update_voltage_range(voltages, 1))

    currents                  = Range_controller(st.current_display_ranges, st.current_display_index)
    current_onoff             = configure_switch_button(st.current_display_status, \
                                    lambda: flip_display_switch('current', current_onoff.value))
    current_display           = thorpy.Text(f'{currents.get_value()} A/div')
    current_display.set_size(TEXT2_SIZE)
    current_down              = configure_arrow_button('up', \
                                    lambda: update_current_range(currents, -1))
    current_up                = configure_arrow_button('down', \
                                    lambda: update_current_range(currents, 1))
    
    powers                    = Range_controller(st.power_display_ranges, st.power_display_index)
    power_onoff               = configure_switch_button(st.power_display_status, \
                                    lambda: flip_display_switch('power', power_onoff.value))
    power_display             = thorpy.Text(f'{powers.get_value()} W/div')
    power_display.set_size(TEXT2_SIZE)
    power_down                = configure_arrow_button('up', \
                                    lambda: update_power_range(powers, -1))
    power_up                  = configure_arrow_button('down', \
                                    lambda: update_power_range(powers, 1))
  
    leakage_currents          = Range_controller(st.earth_leakage_current_display_ranges, \
                                                   st.earth_leakage_current_display_index)
    leakage_current_onoff     = configure_switch_button(st.earth_leakage_current_display_status, \
                                    lambda: flip_display_switch('leakage', leakage_current_onoff.value))
    leakage_current_display   = thorpy.Text(f'{leakage_currents.get_value()*1000.0} mA/div')
    leakage_current_display.set_size(TEXT2_SIZE)
    leakage_current_down      = configure_arrow_button('up', \
                                    lambda: update_leakage_current_range(leakage_currents, -1))
    leakage_current_up        = configure_arrow_button('down', \
                                    lambda: update_leakage_current_range(leakage_currents, 1))
 
    vertical = thorpy.TitleBox(text='Vertical', children=[button_done, \
                 thorpy.Group(elements=[voltage_display, voltage_down, voltage_up, voltage_onoff], \
                     mode='h'), \
                 thorpy.Group(elements=[current_display, current_down, current_up, current_onoff], \
                     mode='h'), \
                 thorpy.Group(elements=[power_display, power_down, power_up, power_onoff], \
                     mode='h'), \
                 thorpy.Group(elements=[leakage_current_display, leakage_current_down, \
                                            leakage_current_up, leakage_current_onoff], mode='h') ])
    for e in vertical.get_all_descendants():
        e.hand_cursor = False    
    return vertical


def create_horizontal(st):
    #####
    # Horizontal controls
    #####
    def update_time_range(times, offset):
        times.change_range(offset)
        time_display.set_text(f'{times.get_value()} ms/div', adapt_parent=False)
        st.time_display_index = times.get_index()
        st.send_to_all()

    button_done = configure_button('Done', back_to_main_reaction)

    times               = Range_controller(st.time_display_ranges, st.time_display_index)
    time_display        = thorpy.Text(f'{times.get_value()} ms/div') 
    time_display.set_size(TEXT2_SIZE)
    time_down           = configure_arrow_button('left', \
                              lambda: update_time_range(times, -1))
    time_up             = configure_arrow_button('right', \
                              lambda: update_time_range(times, 1))

    horizontal = thorpy.TitleBox(text='Horizontal', children=[button_done, \
             thorpy.Group(elements=[time_display, time_down, time_up], mode='h')])
    for e in horizontal.get_all_descendants():
        e.hand_cursor = False    
    return horizontal
 

def create_trigger(st):
    #####
    # Trigger controls
    #####
    # in freerun mode, trigger source is set to -1
    # in sync mode, trigger source is set to ch0 and level to 0.0 (Volts), rising slope
    # in inrush single mode, trigger source is set to ch3 and level to 0.1 (Watts), rising slope
    # inrush mode causes waveform update to stop on first trigger.
    def update_trigger_position(position, status):
        st.time_axis_pre_trigger_divisions = position
        draw_background(st)
        update_trigger_status(status)
        st.send_to_all()

    def update_trigger_slope(slope, status):
        st.trigger_slope = slope
        update_trigger_status(status)
        st.send_to_all()

    def update_trigger_mode(mode, status):
        if mode == 'freerun':
            st.trigger_channel = -1
            draw_background(st)
        elif mode == 'sync':
            st.trigger_channel = 0
            st.trigger_level = 0.0
        elif mode == 'inrush':
            st.trigger_channel = 2
            st.trigger_level = 0.1
        else:
            print('hellebores.py: update_trigger_condition(), invalid condition requested.', sys.stderr)
        st.trigger_mode = mode
        draw_background(st)
        update_trigger_status(status)
        st.send_to_all()

    def update_trigger_status(status):
        if st.trigger_mode == 'freerun':
            status.set_text(f'Free-run: the trigger is disabled.', adapt_parent=False)
        elif st.trigger_mode == 'sync':
            status.set_text(f'Sync: the trigger is enabled to find the {st.trigger_slope} edge of the voltage signal at magitude 0.0V.', adapt_parent=False)
        elif st.trigger_mode == 'inrush':
            status.set_text(f'Inrush: the trigger is enabled for single-shot current detection, magnitude +/- {st.trigger_level}A. Press Run/Stop to reset.', adapt_parent=False)
        else:
            print('hellebores.py: update_trigger_status(), invalid trigger_condition requested.', sys.stderr)
        status.set_max_text_width(280)

    # fill with temporary text so that the correct size is allocated for the enclosing box
    text_trigger_status = thorpy.Text('Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.')
    text_trigger_status.set_max_text_width(280)
    button_done = configure_button('Done', back_to_main_reaction)
    button_freerun = configure_button('Free-run', lambda: update_trigger_mode('freerun', text_trigger_status))
    button_sync = configure_button('Sync', lambda: update_trigger_mode('sync', text_trigger_status))
    button_inrush = configure_button('Inrush', lambda: update_trigger_mode('inrush', text_trigger_status))
    button_left = configure_button('Left', lambda: update_trigger_position(1, text_trigger_status))
    button_centre = configure_button('Centre', lambda: update_trigger_position(st.time_axis_divisions // 2, text_trigger_status))
    button_right = configure_button('Right', lambda: update_trigger_position(st.time_axis_divisions - 1, text_trigger_status))
    button_rising = configure_button('Rising', lambda: update_trigger_slope('rising', text_trigger_status))
    button_falling = configure_button('Falling', lambda: update_trigger_slope('falling', text_trigger_status))
    trigger = thorpy.TitleBox(text='Trigger', children=[button_done, \
        thorpy.Group(elements=[button_freerun, button_sync, button_inrush], mode='h'), \
        thorpy.Group(elements=[button_left, button_centre, button_right], mode='h'), \
        thorpy.Group(elements=[button_rising, button_falling], mode='h'), \
        text_trigger_status]) 
    for e in trigger.get_all_descendants():
        e.hand_cursor = False    
   # put the text status in after forming the box, so that the box dimensions are not affected by the text.
    update_trigger_status(text_trigger_status)
    return trigger

# More UI is needed for the following:
#
# Measurements-1 (summary)
# Measurements-2 (harmonics)
# Wifi setting
# Shell prompt
# Software update, rollback and Raspberry Pi OS update
# About (including software version, kernel version, uuid of Pi and Pico)
# Exit to desktop

def create_ui_groups(st, texts):
 
    ui_groups = {}

    ui_datetime = create_datetime()[0]
    ui_datetime.set_topleft(0,0)
    ui_groups['datetime'] = ui_datetime
 
    ui_main = create_main_controls(texts)
    ui_main.set_size(CONTROLS_BOX_SIZE)
    ui_main.set_topright(*CONTROLS_BOX_POSITION)
    ui_groups['main'] = thorpy.Group(elements=[ui_main], mode=None)

    ui_vertical = create_vertical(st)
    ui_vertical.set_topright(*SETTINGS_BOX_POSITION)
    ui_groups['vertical'] = thorpy.Group(elements=[ui_main, ui_vertical], mode=None)

    ui_horizontal = create_horizontal(st)
    ui_horizontal.set_topright(*SETTINGS_BOX_POSITION)
    ui_groups['horizontal'] = thorpy.Group(elements=[ui_main, ui_horizontal], mode=None)

    ui_trigger = create_trigger(st)
    ui_trigger.set_topright(*SETTINGS_BOX_POSITION)
    ui_groups['trigger'] = thorpy.Group(elements=[ui_main, ui_trigger], mode=None)

    return ui_groups


def start_stop_reaction(texts):
    global capturing
    capturing = not capturing
    texts.refresh()    

def mode_reaction():
    pass

def horizontal_reaction():
    global ui_groups, ui_current_updater
    ui_current_updater = ui_groups['horizontal'].get_updater() 

def vertical_reaction():
    global ui_groups, ui_current_updater
    ui_current_updater = ui_groups['vertical'].get_updater() 

def trigger_reaction():
    global ui_groups, ui_current_updater
    ui_current_updater = ui_groups['trigger'].get_updater()

def options_reaction():
    alert = thorpy.Alert(title="hellebores.py",
                         text="Power quality meter, v0.1",
                         ok_text="Ok, I've read")
    alert.set_draggable()
    alert.cannot_drag_outside = True
    for e in alert.get_all_descendants():
       if isinstance(e, thorpy.elements.Button):
           e.set_bck_color(VERY_LIGHT_GREY, 'normal')
           e.set_bck_color(VERY_LIGHT_GREY, 'hover')
           e.set_font_color(WHITE)
       e.hand_cursor = False
    alert.launch_nonblocking()

def back_to_main_reaction():
    global ui_groups, ui_current_updater
    ui_current_updater = ui_groups['main'].get_updater() 


class Texts:
    # array of thorpy text objects
    texts = []

    def set_colours(self):
        colours = [BLACK, WHITE, WHITE, GREEN, YELLOW, MAGENTA, CYAN]
        # grey out lines that are currently switched off
        colour_filter = [ True, True, True, st.voltage_display_status, \
                             st.current_display_status, st.power_display_status, \
                             st.earth_leakage_current_display_status ]
        for i in range(len(self.texts)):
            if colour_filter[i] == True:
                self.texts[i].set_font_color(colours[i])
            else:
                self.texts[i].set_font_color(DARK_GREY)

    def __init__(self, st, wfs):
        self.wfs = wfs              # make a note of the wfs object
        for s in range(7):
            t = thorpy.Text('')
            t.set_size(TEXT_SIZE)
            self.texts.append(t)
        self.refresh()
 
    def get(self):
        return self.texts

    def set(self, item, value):
        self.texts[item].set_text(value)

    def refresh(self):
        global capturing
        if capturing:
            self.texts[T_RUNSTOP].set_bck_color(GREEN)
            self.texts[T_RUNSTOP].set_text('Running', adapt_parent=False)
        else:
            self.texts[T_RUNSTOP].set_bck_color(RED)
            self.texts[T_RUNSTOP].set_text('Stopped', adapt_parent=False)
        self.set_colours()
        self.texts[T_WFS].set_text(f'{self.wfs.get()} wfm/s', adapt_parent=False)
        self.texts[T_TIMEDIV].set_text(f'{st.time_display_ranges[st.time_display_index]} ms/', adapt_parent=False)
        self.texts[T_VOLTSDIV].set_text(f'{st.voltage_display_ranges[st.voltage_display_index]} V/', adapt_parent=False)
        self.texts[T_AMPSDIV].set_text(f'{st.current_display_ranges[st.current_display_index]} A/', adapt_parent=False)
        self.texts[T_WATTSDIV].set_text(f'{st.power_display_ranges[st.power_display_index]} W/', adapt_parent=False)
        self.texts[T_LEAKDIV].set_text(f'{st.earth_leakage_current_display_ranges[st.earth_leakage_current_display_index]*1000} mA/', adapt_parent=False)


def draw_background(st):
    global background_surface
    xmax = SCOPE_BOX_SIZE[0] - 1
    ymax = SCOPE_BOX_SIZE[1] - 1

    # empty background
    background_surface = pygame.Surface(SCOPE_BOX_SIZE)
    background_surface.fill(GREY)

    # draw the graticule lines
    for dx in range(1, st.time_axis_divisions):
        x = st.horizontal_pixels_per_division * dx
        # mark the trigger position (t=0) with an emphasized line
        if (dx == st.time_axis_pre_trigger_divisions) and (st.trigger_channel != -1):
            lc = WHITE
        else:
            lc = LIGHT_GREY
        pygame.draw.line(background_surface, lc, (x, 0), (x, ymax), 1)
    for dy in range(1, st.vertical_axis_divisions):
        y = st.vertical_pixels_per_division * dy
        # mark the central position (v, i = 0) with an emphasized line
        if dy == st.vertical_axis_divisions // 2:
            lc = WHITE
        else:
            lc = LIGHT_GREY
        pygame.draw.line(background_surface, lc, (0, y), (xmax, y), 1)
    return background_surface



def draw_dots(lines, screen, background_surface):
    # can handle up to six lines...
    colours = [ GREEN, YELLOW, MAGENTA, CYAN, RED, BLUE ]
    screen.blit(background_surface, (0,0))
    linedata = lines.get_lines()
    display_status = [ st.voltage_display_status, st.current_display_status, st.power_display_status, \
                          st.earth_leakage_current_display_status ]
    try:
        pa = pygame.PixelArray(screen)
        for i in range(len(linedata)):
            if display_status[i] == True:
                for pixel in linedata[i]:
                    pa[pixel[0], pixel[1]] = colours[i]
                    pa[pixel[0]+1, pixel[1]] = colours[i]
                    pa[pixel[0], pixel[1]+1] = colours[i]
                    pa[pixel[0]+1, pixel[1]+1] = colours[i]
        pa.close()
    except ValueError:
        # the pygame.draw.lines will throw an exception if there are not at
        # least two points in each line - (sounds reasonable)
        sys.stderr.write(f'exception in hellebores.py: draw_dots(). linedata is: {linedata}.\n')

redraw_lines = draw_dots

def _redraw_lines(lines, screen, background_surface):
    # can handle up to six lines...
    colours = [ green, yellow, magenta, cyan, red, blue ]
    screen.blit(background_surface, (0,0))
    linedata = lines.get_lines()
    display_status = [ st.voltage_display_status, st.current_display_status, st.power_display_status, \
                          st.earth_leakage_current_display_status ]
    try:
        for i in range(len(linedata)):
            if display_status[i] == True:
                pygame.draw.lines(screen, colours[i], false, linedata[i], 2)
    except ValueError:
        # the pygame.draw.lines will throw an exception if there are not at
        # least two points in each line - (sounds reasonable)
        sys.stderr.write(f'exception in hellebores.py: redraw_lines(). linedata is: {linedata}.\n')


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
 

class Lines:
    # working points buffer for four lines
    ps = [ [],[],[],[] ] 

    # lines history buffer
    # future extension is to use this buffer for electrical event history
    # (eg triggered by power fluctuation etc)
    lines_history = [[] for i in range(LINES_BUFFER_SIZE+1)]

    def end_frame(self, capturing, wfs):
        if capturing:
            self.lines_history[LINES_BUFFER_SIZE] = self.ps
            wfs.increment()
        # reset the working buffer
        self.ps = [ [],[],[],[] ]

    def add_sample(self, sample):
        self.ps[0].append((sample[0], sample[1]))
        self.ps[1].append((sample[0], sample[2]))
        self.ps[2].append((sample[0], sample[3]))
        self.ps[3].append((sample[0], sample[4]))

    def read_lines(self, f, capturing, wfs):
        # the loop will exit if:
        # (a) there is no data currently waiting to be read, 
        # (b) negative x coordinate indicates last sample of current frame
        # (c) the x coordinate 'goes backwards' indicating a new frame has started
        # (d) the line is empty, can't be split() or any other kind of read error
        # returns 'True' if we have completed a new frame
        xp = -1                 # tracks previous 'x coordinate'
        while is_data_available(f, 0.05): 
            try:
                sample = [ int(w) for w in f.readline().split() ]
                if sample[-1] < 0:
                    # negative integer was appended to indicate end of frame...
                    # add current sample then end the frame
                    self.add_sample(sample)
                    self.end_frame(capturing, wfs)
                    return True
                elif sample[0] < xp:
                    # x coordinate has reset to indicate start of new frame...
                    # end the frame before adding current sample to a new one
                    self.end_frame(capturing, wfs)    
                    self.add_sample(sample)
                    return True
                else:
                    # an ordinary, non-special, sample
                    self.add_sample(sample)
                xp = sample[0]
            except:
                break   # break if we have any type of error with the input data
        return False

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
    global st, capturing, ui_groups, ui_current_updater, background_surface

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

    # get settings from settings.json
    st = settings.Settings(other_programs=['rain.py', 'reader.py', 'scaler.py', 'trigger.py', 'mapper.py'])

    # initialise flags
    capturing = True        # allow/stop update of the lines on the screen
    running   = True        # program runs until this flag is cleared

    # create objects that hold the state of the UI
    background_surface = draw_background(st)
    wfs       = WFS_Counter()
    texts     = Texts(st, wfs)
    ui_groups = create_ui_groups(st, texts)

    # start with the main group enabled
    ui_current_updater = ui_groups['main'].get_updater()

    # set up lines object
    lines = Lines()
    

    # main loop
    while running:
        # hack to make the cursor invisible while still responding
        if hide_mouse_pointer:
            pygame.mouse.set_cursor((8,8),(0,0),(0,0,0,0,0,0,0,0),(0,0,0,0,0,0,0,0))
        # we update all of the texts every second, not just the datetime
        if wfs.time_to_update():
            if capturing:
                ui_groups['datetime'].set_text(time.ctime())
            texts.refresh()
        # ALWAYS read new data, even if we are not capturing it, to keep the incoming data
        # pipeline flowing. If the read rate doesn't keep up with the pipe, then we will see 
        # artifacts on screen. Check the BUFFER led on PCB if performance problems are
        # suspected here.
        # The read_lines() function also implicitly manages display refresh speed when not
        # capturing, by waiting for a definite time for new data.
        got_new_frame = lines.read_lines(sys.stdin, capturing, wfs)
        # check if we should refresh the main display
        # note that when we are capturing we only refresh when we have something new 
        if (capturing and got_new_frame) or not capturing:
            redraw_lines(lines, screen, background_surface) 
            ui_groups['datetime'].draw()
        # here we process mouse/touch/keyboard events.
        events = pygame.event.get()
        for e in events:
            if (e.type == pygame.QUIT) or (e.type == pygame.KEYDOWN and e.key == pygame.K_q):
                running = False
        # ui_current_updater.update() is an expensive function, so we use the simplest possible
        # thorpy theme for performance
        ui_current_updater.update(events=events)
        # push all of our updated work into the active display framebuffer
        pygame.display.flip()
    pygame.quit()



if __name__ == '__main__':
    main()

