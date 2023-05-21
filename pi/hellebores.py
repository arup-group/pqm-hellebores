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
T_TIMEDIV     = 2
T_VOLTSDIV    = 3
T_AMPSDIV     = 4
T_WATTSDIV    = 5
T_LEAKDIV     = 6


def signal_other_processes(st):
    # send a signal to everyone to update their settings
    st.set_derived_settings()
    st.save_settings()
    if sys.platform == 'linux':
        # all running processes in the form 'python3 ./[something].py' will be signalled
        os.system("pkill --signal=SIGUSR1 -f 'python3 \./.*\.py'")
    else:
        print(f"hellebores.py: don't know how to send SIGUSR1 on {sys.platform}", file=sys.stderr)
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
    return main


def create_vertical(st):
    #####
    # Vertical controls
    #####
    def update_voltage_range(voltages, offset):
        voltages.change_range(offset)
        voltage_display.set_text(f'{voltages.get_value()} V/div', adapt_parent=False)
        st.voltage_display_index = voltages.get_index()
        signal_other_processes(st)

    def update_current_range(currents, offset):
        currents.change_range(offset)
        current_display.set_text(f'{currents.get_value()} A/div', adapt_parent=False)
        st.current_display_index = currents.get_index()
        signal_other_processes(st)

    def update_power_range(powers, offset):
        powers.change_range(offset)
        power_display.set_text(f'{powers.get_value()} W/div', adapt_parent=False)
        st.power_display_index = powers.get_index()
        signal_other_processes(st)

    def update_leakage_current_range(leakage_currents, offset):
        leakage_currents.change_range(offset)
        leakage_current_display.set_text(f'{leakage_currents.get_value()*1000.0} mA/div', adapt_parent=False)
        st.earth_leakage_current_display_index = leakage_currents.get_index()
        signal_other_processes(st)

    button_done = configure_button('Done', back_to_main_reaction)

    voltages                  = Range_controller(st.voltage_display_ranges, st.voltage_display_index)
    voltage_display           = thorpy.Text(f'{voltages.get_value()} V/div') 
    voltage_display.set_size(BUTTON_SIZE)
    voltage_down              = configure_arrow_button('up', \
                                    lambda: update_voltage_range(voltages, -1))
    voltage_up                = configure_arrow_button('down', \
                                    lambda: update_voltage_range(voltages, 1))

    currents                  = Range_controller(st.current_display_ranges, st.current_display_index)
    current_display           = thorpy.Text(f'{currents.get_value()} A/div')
    current_display.set_size(BUTTON_SIZE)
    current_down              = configure_arrow_button('up', \
                                    lambda: update_current_range(currents, -1))
    current_up                = configure_arrow_button('down', \
                                    lambda: update_current_range(currents, 1))
    
    powers                    = Range_controller(st.power_display_ranges, st.power_display_index)
    power_display             = thorpy.Text(f'{powers.get_value()} W/div')
    power_display.set_size(BUTTON_SIZE)
    power_down                = configure_arrow_button('up', \
                                    lambda: update_power_range(powers, -1))
    power_up                  = configure_arrow_button('down', \
                                    lambda: update_power_range(powers, 1))
  
    leakage_currents          = Range_controller(st.earth_leakage_current_display_ranges, \
                                                   st.earth_leakage_current_display_index)
    leakage_current_display   = thorpy.Text(f'{leakage_currents.get_value()*1000.0} mA/div')
    leakage_current_display.set_size(BUTTON_SIZE)
    leakage_current_down      = configure_arrow_button('up', \
                                    lambda: update_leakage_current_range(leakage_currents, -1))
    leakage_current_up        = configure_arrow_button('down', \
                                    lambda: update_leakage_current_range(leakage_currents, 1))
 
    vertical = thorpy.TitleBox(text='Vertical', children=[button_done, \
                 thorpy.Group(elements=[voltage_display, voltage_down, voltage_up], mode='h'), \
                 thorpy.Group(elements=[current_display, current_down, current_up], mode='h'), \
                 thorpy.Group(elements=[power_display, power_down, power_up], mode='h'),
                 thorpy.Group(elements=[leakage_current_display, leakage_current_down, leakage_current_up], mode='h') ])
    return vertical


def create_horizontal(st):
    #####
    # Horizontal controls
    #####
    def update_time_range(times, offset):
        times.change_range(offset)
        time_display.set_text(f'{times.get_value()} ms/div', adapt_parent=False)
        st.time_display_index = times.get_index()
        signal_other_processes(st)

    button_done = configure_button('Done', back_to_main_reaction)

    times               = Range_controller(st.time_display_ranges, st.time_display_index)
    time_display        = thorpy.Text(f'{times.get_value()} ms/div') 
    time_display.set_size(BUTTON_SIZE)
    time_down           = configure_arrow_button('left', \
                              lambda: update_time_range(times, -1))
    time_up             = configure_arrow_button('right', \
                              lambda: update_time_range(times, 1))
 
    return thorpy.TitleBox(text='Horizontal', children=[button_done, \
             thorpy.Group(elements=[time_display, time_down, time_up], mode='h')])
 

def create_trigger(st):
    #####
    # Trigger controls
    #####
    def update_trigger_position(trigger_positions, offset):
        trigger_positions.change_range(offset)
        trigger_position_display.set_text(f'{trigger_positions.get_value()} div', adapt_parent=False)
        st.trigger_position_index = trigger_positions.get_index()
        st.time_axis_pre_trigger_divisions = st.trigger_position_index
        draw_background(st)
        signal_other_processes(st)

    def update_trigger_level(trigger_levels, offset):
        trigger_levels.change_range(offset)
        trigger_level_display.set_text(f'{trigger_levels.get_value()} div', adapt_parent=False)
        st.trigger_level_index = trigger_levels.get_index()
        signal_other_processes(st)


    button_done = configure_button('Done', back_to_main_reaction)

    trigger_positions        = Range_controller(range(st.time_axis_divisions), st.trigger_position)
    trigger_position_display = thorpy.Text(f'{trigger_positions.get_value()} div')
    trigger_position_left    = configure_arrow_button('left', lambda: update_trigger_position(trigger_positions, -1))
    trigger_position_right   = configure_arrow_button('right', lambda: update_trigger_position(trigger_positions, 1))
    # need to add functions for level and channel likewise
    trigger_levels           = Range_controller(st.trigger_levels, st.trigger_level_index)
    trigger_level_display    = thorpy.Text(f'{trigger_levels.get_value()} div')
    trigger_level_up         = configure_arrow_button('up', lambda: update_trigger_level(trigger_levels, 1))
    trigger_level_down       = configure_arrow_button('down', lambda: update_trigger_level(trigger_levels, -1))
    trigger_channel          = thorpy.TogglablesPool('Channel', ('Voltage', 'Current', 'Power', 'Leakage'), 'Voltage', togglable_type='radio')
    trigger_direction        = thorpy.TogglablesPool('Direction', ('Rising', 'Falling'), 'Rising', togglable_type='radio')
    return thorpy.TitleBox(text='Trigger', children=[button_done, \
        thorpy.Group(elements=[trigger_position_display, trigger_position_left, trigger_position_right], mode='h'), \
        thorpy.Group(elements=[trigger_level_display, trigger_level_up, trigger_level_down], mode='h'), \
        thorpy.Group(elements=[trigger_channel, trigger_direction], mode='h')])


# More UI is needed for the following:
#
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
   global ui_groups, ui_current_updater
   ui_current_updater = ui_groups['horizontal'].get_updater() 

def vertical_reaction():
   global ui_groups, ui_current_updater
   ui_current_updater = ui_groups['vertical'].get_updater() 

def trigger_reaction():
   global ui_groups, ui_current_updater
   ui_current_updater = ui_groups['trigger'].get_updater()

def options_reaction():
   pass


def back_to_main_reaction():
    global ui_groups, ui_current_updater
    ui_current_updater = ui_groups['main'].get_updater() 


class Texts:
    # array of thorpy text objects
    texts = []
    colours = [BLACK, WHITE, WHITE, GREEN, YELLOW, MAGENTA, CYAN]

    def __init__(self, st, wfs):
        self.wfs = wfs              # make a note of the wfs object
        for s in range(len(self.colours)):
            t = thorpy.Text('')
            t.set_size(TEXT_SIZE)
            if self.colours[s] != None:
                t.set_font_color(self.colours[s])
            self.texts.append(t)
        self.refresh()
 
    def get(self):
        return self.texts

    def refresh(self):
        global capturing
        if capturing:
            self.texts[T_RUNSTOP].set_bck_color(GREEN)
            self.texts[T_RUNSTOP].set_text('Running', adapt_parent=False)
        else:
            self.texts[T_RUNSTOP].set_bck_color(RED)
            self.texts[T_RUNSTOP].set_text('Stopped', adapt_parent=False)
        self.texts[T_WFS].set_text(f'{self.wfs.get()} wfm/s', adapt_parent=False)
        self.texts[T_TIMEDIV].set_text(f'{st.time_display_ranges[st.time_display_index]} ms/', adapt_parent=False)
        self.texts[T_VOLTSDIV].set_text(f'{st.voltage_display_ranges[st.voltage_display_index]} V/', adapt_parent=False)
        self.texts[T_AMPSDIV].set_text(f'{st.current_display_ranges[st.current_display_index]} A/', adapt_parent=False)
        self.texts[T_WATTSDIV].set_text(f'{st.power_display_ranges[st.power_display_index]} W/', adapt_parent=False)
        self.texts[T_LEAKDIV].set_text(f'{st.earth_leakage_current_display_ranges[st.earth_leakage_current_display_index]*1000} mA/', adapt_parent=False)

    # update text message string
    def set(self, item, value):
        self.texts[item].set_text(value)


def create_ui_groups(st, texts):
 
    ui_groups = {}

    ui_datetime = create_datetime()[0]
    ui_datetime.set_topleft(0,0)
    ui_groups['datetime'] = ui_datetime
 
    ui_main = create_main_controls(texts)
    ui_main.set_size(CONTROLS_BOX_SIZE)
    ui_main.set_topleft(*CONTROLS_BOX_POSITION)
    ui_groups['main'] = thorpy.Group(elements=[ui_main], mode=None)

    ui_vertical = create_vertical(st)
    ui_vertical.set_topleft(*SETTINGS_BOX_POSITION)
    ui_groups['vertical'] = thorpy.Group(elements=[ui_main, ui_vertical], mode=None)

    ui_horizontal = create_horizontal(st)
    ui_horizontal.set_topleft(*SETTINGS_BOX_POSITION)
    ui_groups['horizontal'] = thorpy.Group(elements=[ui_main, ui_horizontal], mode=None)

    ui_trigger = create_trigger(st)
    ui_trigger.set_topleft(*SETTINGS_BOX_POSITION)
    ui_groups['trigger'] = thorpy.Group(elements=[ui_main, ui_trigger], mode=None)

    return ui_groups


def start_stop_reaction(texts):
   global capturing
   capturing = not capturing
   texts.refresh()    


def options_reaction():
    alert = thorpy.Alert(title="hellebores.py",
                         text="Power quality meter, v0.03",
                         ok_text="Ok, I've read")
    alert.set_draggable()
    alert.cannot_drag_outside = True
    alert.launch_nonblocking()


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


def redraw_lines(lines, screen, background_surface):
    # can handle up to six lines...
    colours = [ GREEN, YELLOW, MAGENTA, CYAN, RED, BLUE ]
    screen.blit(background_surface, (0,0))
    linedata = lines.get_lines()
    try:
        for i in range(len(linedata)):
            pygame.draw.lines(screen, colours[i], False, linedata[i], 2)
    except ValueError:
        # the pygame.draw.lines will throw an exception if there are not at
        # least two points in each line - (sounds reasonable)
        sys.stderr.write('Exception in hellebores.py: redraw_lines().\n')


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
            self.wfs = round(self.counter/elapsed)
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

def is_data_available_linux(f, t):
    # f file object, t time in seconds
    # wait at most 't' seconds for new data to appear
    # r will be an empty list unless there is data ready to read
    r, _, _ = select.select( [f], [], [], t)
    return r != []

def is_data_available_windows(f, t):
    # unfortunately this test isn't easy to implement on windows
    # so we return a default 'True' response
    return True

# the version of is_data_available that we will use is selected
# once at runtime
if sys.platform == 'linux':
    is_data_available = is_data_available_linux
else:
    is_data_available = is_data_available_windows
 

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
    else:
        screen    = pygame.display.set_mode(PI_SCREEN_SIZE)

    # initialise thorpy
    thorpy.set_default_font(FONT, FONT_SIZE)
    thorpy.init(screen, thorpy.theme_simple)

    # get settings from settings.json
    st = settings.Settings()

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
        # pygame.mouse.set_cursor((8,8),(0,0),(0,0,0,0,0,0,0,0),(0,0,0,0,0,0,0,0))
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


