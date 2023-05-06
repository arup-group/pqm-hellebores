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
SETTINGS_BOX_POSITION = (400,100)
BUTTON_SIZE = (86,50) 
ARROW_BUTTON_SIZE = (80,50)
TEXT_SIZE = (100,16)
FONT = 'dejavusansmono'
FONT_SIZE = 14

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
B_OPTIONS     = 4
B_ABOUT       = 5


# text message cell enumerations
T_RUNSTOP     = 0
T_WFS         = 1
T_UNDEF2      = 2
T_UNDEF3      = 3
T_UNDEF4      = 4
T_UNDEF5      = 5



def signal_other_processes():
    # send a signal to everyone to update their settings
    if sys.platform == 'linux':
        os.system("pkill -f --signal=SIGUSR1 'python3 ./rain.py'")
        os.system("pkill -f --signal=SIGUSR1 'python3 ./reader.py'")
        os.system("pkill -f --signal=SIGUSR1 'python3 ./scaler.py'")
        os.system("pkill -f --signal=SIGUSR1 'python3 ./trigger.py'")
        os.system("pkill -f --signal=SIGUSR1 'python3 ./mapper.py'")
    

def create_controls():
    global st

    # Main controls, on right of screen

    button_runstop       = thorpy.Button('Run/Stop')
    button_runstop.set_size(BUTTON_SIZE)
    button_runstop.at_unclick    = start_stop_reaction

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


    controls = {}
    controls['main']     = [ button_runstop, \
                             button_mode, \
                             button_horizontal, \
                             button_vertical, \
                             button_trigger, \
                             button_options ]

    class Range_controller:
        ranges = []
        range_selector = 0
        maximum_range = 1

        def __init__(self, required_ranges):
            self.ranges = required_ranges
            self.maximum_range = len(required_ranges) - 1

        def selected(self):
            return self.ranges[self.range_selector]

        def change_range(self, offset):
            if offset == 1:
                self.range_selector = min(self.maximum_range, self.range_selector+1)
            elif offset == -1:
                self.range_selector = max(0, self.range_selector-1)
            else:
                sys.stderr.write("Range_controller.change_range: can only change range by +1 or -1.") 


    def update_voltage_range(voltages, offset):
        voltages.change_range(offset)
        display_voltage.set_text(f'{voltages.selected()} V/div')
        st.voltage_axis_per_division = voltages.selected()
        st.save_settings()
        signal_other_processes()

    def update_current_range(currents, offset):
        currents.change_range(offset)
        current_display.set_text(f'{currents.selected()} A/div')
        st.current_axis_per_division = currents.selected()
        st.save_settings()
        signal_other_processes()

    def update_power_range(powers, offset):
        powers.change_range(offset)
        power_display.set_text(f'{powers.selected()} W/div')
        st.power_axis_per_division = powers.selected()
        st.save_settings()
        signal_other_processes()

    def update_leakage_current_range(leakage_currents, offset):
        leakage_currents.change_range(offset)
        leakage_current_display.set_text(f'{leakage_currents.selected()*1000.0} mA/div')
        st.earth_leakage_current_axis_per_division = leakage_currents.selected()
        st.save_settings()
        signal_other_processes()


    button_done          = thorpy.Button('Done')
    button_done.set_size(BUTTON_SIZE)
    button_done.at_unclick       = back_to_main_reaction

    voltages                  = Range_controller([50,100])
    display_voltage           = thorpy.Text(f'{voltages.selected()} V/div') 
    down_voltage              = thorpy.ArrowButton('up', ARROW_BUTTON_SIZE)
    down_voltage.at_unclick   = lambda: update_voltage_range(voltages, -1)
    up_voltage                = thorpy.ArrowButton('down', ARROW_BUTTON_SIZE)
    up_voltage.at_unclick     = lambda: update_voltage_range(voltages, 1)
 
    currents                  = Range_controller([0.001,0.002,0.005,0.01,0.02,0.05,0.1,0.2,0.5,1.0,2.0])
    current_display           = thorpy.Text(f'{currents.selected()} A/div')
    current_down              = thorpy.ArrowButton('up', ARROW_BUTTON_SIZE)
    current_down.at_unclick   = lambda: update_current_range(currents, -1)
    current_up                = thorpy.ArrowButton('down', ARROW_BUTTON_SIZE)
    current_up.at_unclick     = lambda: update_current_range(currents, 1)
    
    powers                    = Range_controller([0.1,0.2,0.5,1.0,2.0,5.0,10.0,20.0,50.0,100.0,200.0,500.0])
    power_display             = thorpy.Text(f'{powers.selected()} W/div')
    power_down                = thorpy.ArrowButton('up', ARROW_BUTTON_SIZE)
    power_down.at_unclick     = lambda: update_power_range(powers, -1)
    power_up                  = thorpy.ArrowButton('down', ARROW_BUTTON_SIZE)
    power_up.at_unclick       = lambda: update_power_range(powers, 1)
  
    leakage_currents          = Range_controller([0.00001,0.00002,0.00005,0.0001,0.0002,0.0005,0.001,0.002])
    leakage_current_display   = thorpy.Text(f'{leakage_currents.selected()*1000.0} mA/div')
    leakage_current_down      = thorpy.ArrowButton('up', ARROW_BUTTON_SIZE)
    leakage_current_down.at_unclick     = lambda: update_leakage_current_range(leakage_currents, -1)
    leakage_current_up        = thorpy.ArrowButton('down', ARROW_BUTTON_SIZE)
    leakage_current_up.at_unclick       = lambda: update_leakage_current_range(leakage_currents, 1)


    controls['vertical']       = [thorpy.TitleBox(text='Vertical', children=[button_done, \
        thorpy.Group(elements=[display_voltage, down_voltage, up_voltage], mode='h'), \
        thorpy.Group(elements=[current_display, current_down, current_up], mode='h'), \
        thorpy.Group(elements=[power_display, power_down, power_up], mode='h'),
        thorpy.Group(elements=[leakage_current_display, leakage_current_down, leakage_current_up], mode='h') ])]
                              
#    buttons['main']           = [ thorpy.Button('Run/Stop', func = start_stop_reaction),\
#                                  thorpy.Button('Mode', func = mode_reaction),\
#                                  thorpy.Button('Horizontal', func = horizontal_reaction),\
#                                  thorpy.Button('Vertical', func = vertical_reaction),\
#                                  thorpy.Button('Trigger', func = trigger_reaction),\
#                                  thorpy.Button('Options', func = about_box_reaction) ]
#
#    buttons['mode']           = [ thorpy.Button('Back', func = back_reaction),\
#                                  thorpy.Button('Waveform', func = mode_reaction),\
#                                  thorpy.Button('Meter', func = horizontal_reaction),\
#                                  thorpy.Button('Harmonics', func = vertical_reaction),\
#                                  thorpy.Button('Logging', func = options_reaction) ]
#
#    buttons['horizontal']     = [ thorpy.Button('Back', func = back_reaction),\
#                                  thorpy.Button('< Zoom >', func = horizontal_zoom_reaction),\
#                                  thorpy.Button('> Expand <', func = horizontal_expand_reaction),\
#                                  thorpy.Button('t0 >', func = time_right_reaction),\
#                                  thorpy.Button('< t0', func = time_left_reaction),\
#                                  thorpy.Button('Trigger', func = trigger_reaction) ]
#
#    buttons['trigger']        = [ thorpy.Button('Back', func = back_reaction),\
#                                  thorpy.Button('Trigger channel', func = trigger_channel_reaction),\
#                                  thorpy.Button('Trigger level', func = trigger_level_reaction),\
#                                  thorpy.Button('Trigger direction', func = trigger_direction_reaction) ]
#                            
#    buttons['vertical']       = [ thorpy.Button('Back', func = back_reaction),\
#                                  thorpy.Button('< Zoom >', func = vertical_zoom_reaction),\
#                                  thorpy.Button('> Expand <', func = vertical_expand_reaction) ]
#                            
#    buttons['options']        = [ thorpy.Button('Back', func = back_reaction),\
#                                  thorpy.Button('Wifi', func = wifi_reaction),\
#                                  thorpy.Button('Shell', func = shell_reaction),\
#                                  thorpy.Button('Exit', func = exit_reaction) ]


    return controls


def alive_func():
   print("I'm alive.")

def mode_reaction():
   pass

def horizontal_reaction():
   pass

def vertical_reaction():
    global ui_groups, ui_updater
    ui_updater = ui_groups['vertical'].get_updater() 


def trigger_reaction():
   pass

def options_reaction():
   pass

def back_reaction():
   pass

def horizontal_zoom_reaction():
   pass

def horizontal_expand_reaction():
   pass

def time_right_reaction():
   pass

def time_left_reaction():
   pass

def trigger_channel_reaction():
   pass

def trigger_level_reaction():
   pass

def trigger_direction_reaction():
   pass

def vertical_zoom_reaction():
   pass

def vertical_expand_reaction():
   pass

def trigger_direction_reaction():
   pass

def wifi_reaction():
   pass

def shell_reaction():
   pass

def exit_reaction():
   pass

def back_to_main_reaction():
    global ui_groups, ui_updater
    ui_updater = ui_groups['main'].get_updater() 


class Texts:
    # array of thorpy text objects
    texts = []

    def __init__(self):
        for s in range(0,7):
            # the dummy text here is needed to allocate pixels
            # and to make all the text left aligned
            t = thorpy.Text('')
            t.set_size(TEXT_SIZE)
            self.texts.append(t)
        #self.clear_texts()

    def get_texts(self):
        return self.texts

    # update text message string
    def set_text(self, item, value):
        self.texts[item].set_text(value)


    def clear_texts(self):
        for t in self.texts:
            t.set_text('')


def initialise_ui_groups(main, vertical, horizontal, trigger, options):
    ui_groups = {}
    
    ui_main = thorpy.Box(main)
    ui_main.set_size(CONTROLS_BOX_SIZE)
    ui_main.set_topleft(*CONTROLS_BOX_POSITION)
    ui_groups['main'] = ui_main

    ui_vertical = thorpy.Box(vertical)
    ui_vertical.set_topleft(*SETTINGS_BOX_POSITION)
    ui_groups['vertical'] = ui_vertical

    return ui_groups


def start_stop_reaction():
   global capturing
   if capturing == True:
       capturing = False
       texts.set_text(T_RUNSTOP, "Stopped")
   else:
       capturing = True
       texts.set_text(T_RUNSTOP, "Running")
       

def options_reaction():
    global screen, background_surface
    alert = thorpy.Alert(title="hellebores.py",
                         text="Power quality meter, v0.02",
                         ok_text="Ok, I've read")
    alert.set_draggable()
    alert.cannot_drag_outside = True
    alert.launch_nonblocking()


def refresh_reaction(points):
    global wfs, texts, capturing, screen, background_surface
    lines = points.read_points(sys.stdin)
    # update the screen only if capturing
    if capturing:
        if lines and len(lines[0]) > 1:
            # blit the screen with background image (graticule)
            screen.blit(background_surface, (0,0))
            draw_lines(screen, background_surface, lines)
            wfs.increment_wfs()


def draw_background():
    global st, background_surface
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


def draw_lines(screen, background_surface, lines):
   # can handle up to six lines
    colours = [ GREEN, YELLOW, MAGENTA, CYAN, RED, BLUE ]
    for i in range(len(lines)):
        pygame.draw.lines(screen, colours[i], False, lines[i], 2)





class WFS_Counter:
    global texts

    def __init__(self):
        self.counter = 0           # number of waveforms since last posting
        self.time = time.time()    # keep track of time in milliseconds
        self.posted = self.time    # time when the wfs/s was lasted posted to screen

    # called whenever we update the waveform on screen 
    def increment_wfs(self):
        self.counter = self.counter + 1

    # called when a refresh event occurs (image isn't always updated)
    def refresh_wfs(self):
        updated_text = False

        # time check 
        self.time = time.time()
        # if the time has increased by at least 1.0 second, update the wfm/s text
        elapsed = self.time - self.posted
        if elapsed >= 1.0:
            texts.set_text(T_WFS, f'{round(self.counter/elapsed)} wfm/s')
            self.posted = self.time
            self.counter = 0
            updated_text = True

        return updated_text
 

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


class Points:

    # working line buffer 
    ws = []

    def read_points(self, f):
        ps = []
        tp = 0
        # the loop will exit and the points list is returned if
        # (a) there is no more data waiting to be read, 
        # (b) if the time coordinate 'goes backwards', or
        # (c) if the line is empty or not correctly formatted
        while is_data_available(f, 1.0): 
            try:
                if self.ws == []:
                    self.ws = f.readline().split()
                t = int(self.ws[0])
                if t < tp:
                    break       # exit now if time coordinate is lower than previous one
                self.ws = self.ws[1:]
                for i in range(len(self.ws)):
                    try:
                        ps[i].append((t, int(self.ws[i])))   # extend an existing line
                    except IndexError:
                        ps.append( [(t, int(self.ws[i]))] )  # or add another line if it doesn't exist yet
            except:
                break           # exit if we have any other type of error with the input data
            tp = t
            self.ws = f.readline().split()
        return ps

    def __init__(self):
        pass


def main():
    global st, running, capturing, texts, background_surface, ui_groups, ui_updater, screen, wfs

    # get settings from settings.json
    st = settings.Settings(draw_background)
    draw_background()

    # initialise UI
    # thorpy.Application doesn't behave well on Windows -- goes to full screen immediately
    # therefore using underlying pygame functions to initialise display
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

    thorpy.set_default_font(FONT, FONT_SIZE)
    thorpy.init(screen, thorpy.theme_classic)

    texts     = Texts()
    wfs       = WFS_Counter()
    controls  = create_controls()
    ui_groups = initialise_ui_groups([*controls['main'], *texts.get_texts()], \
                                     [*controls['vertical']], \
                                     None, \
                                     None, \
                                     None)
    ui_updater = ui_groups['main'].get_updater()

    # now set up the initial text states
    texts.set_text(T_RUNSTOP, "Running")

    # set up points object
    points = Points()
    
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
        refresh_reaction(points)
        wfs.refresh_wfs()
        ui_updater.update(events=events)
        pygame.display.flip()

    pygame.quit()



if __name__ == '__main__':
    main()


