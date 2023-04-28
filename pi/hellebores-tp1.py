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
import random
import sys
import os
import select
import json



def get_settings():
    global time_axis_divisions, vertical_axis_divisions, horizontal_pixels_per_division,\
               vertical_pixels_per_division, time_axis_pre_trigger_divisions, interval
    try:
        f = open("settings.json", "r")
        js = json.loads(f.read())
        f.close()
        time_axis_divisions               = js['time_axis_divisions']
        vertical_axis_divisions           = js['vertical_axis_divisions']
        horizontal_pixels_per_division    = js['horizontal_pixels_per_division']
        vertical_pixels_per_division      = js['vertical_pixels_per_division']
        time_axis_pre_trigger_divisions   = js['time_axis_pre_trigger_divisions']
        interval                          = 1000.0 / js['sample_rate']
        return js
    except:
        print("hellebores.py, get_settings(): couldn't read settings.json, using defaults.", file=sys.stderr)
        time_axis_divisions               = 10
        vertical_axis_divisions           = 8
        horizontal_pixels_per_division    = 70
        vertical_pixels_per_division      = 60
        time_axis_pre_trigger_divisions   = 2
        interval                          = 1000.0 / 7812.5
        return {}

def save_settings(js):
    try:
        f = open('settings.json', 'w')
        f.write(json.dumps(js))
        f.close()
    except:
        print("hellebores.py, save_settings(): couldn't write settings.json.", file=sys.stderr)

       
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
BUTTON_SIZE = (100,50) 
TEXT_SIZE = (100,12)


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
    

def initialise_buttons():
    buttons = []
    for s in ['Run/Stop', 'Mode', 'Horizontal', 'Vertical', 'Options', 'About']:
        button = thorpy.make_button(s)
        button.set_size(BUTTON_SIZE)
        buttons.append(button)
    return buttons


class Texts:
    # array of thorpy text objects
    texts = []

    def __init__(self):
        for s in range(0,7):
            # the dummy text here is needed to allocate pixels
            # and to make all the text left aligned
            t = thorpy.make_text('XXXXXXXXX')  
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


def initialise_uibox(buttons, texts):
    # create the user interface object, and add reactions to it
    uibox = thorpy.Box(elements=[*buttons, *texts])
    uibox.add_reaction(thorpy.Reaction(reacts_to=thorpy.constants.THORPY_EVENT, \
                       reac_func=start_stop_reaction, \
                       event_args={"el": buttons[B_RUNSTOP], "id": thorpy.constants.EVENT_UNPRESS}))

    uibox.add_reaction(thorpy.Reaction(reacts_to=thorpy.constants.THORPY_EVENT, \
                       reac_func=about_box_reaction, \
                       event_args={"el": buttons[B_ABOUT], "id": thorpy.constants.EVENT_UNPRESS}))

    uibox.set_size(CONTROLS_BOX_SIZE)
    uibox.set_topleft((PI_SCREEN_SIZE[0]-CONTROLS_BOX_SIZE[0],0))
    return uibox


def initialise_dispatching(uibox, screen):
    # a menu object is needed for events dispatching
    menu = thorpy.Menu(uibox) 

    # set the screen to be the display surface
    for element in menu.get_population():
        element.surface = screen

    # We do not actually launch the menu (menu.play()) because it creates an embedded
    # event loop, while we need to have a free running loop in this application,
    # to maximise the display refresh rate.
    # So instead, we process events manually inside the main() function.
    return menu


def start_stop_reaction(event):
   global capturing
   if capturing == True:
       capturing = False
       texts.set_text(T_RUNSTOP, "Stopped")
   else:
       capturing = True
       texts.set_text(T_RUNSTOP, "Running")
       

def about_box_reaction(event):
   thorpy.launch_blocking_alert(title="hellebores.py",
                               text="Power quality meter, v0.01",
                               ok_text="Ok, I've read",
                               font_size=12,
                               font_color=RED)


def process_events(menu):
    global running
    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
            running = False
        menu.react(event)


def draw_graticule(screen):
    xmax, ymax = SCOPE_BOX_SIZE
    for dx in range(1, time_axis_divisions):
        x = horizontal_pixels_per_division * dx
        # mark the trigger position (t=0) with a thicker line
        if dx == time_axis_pre_trigger_divisions:
            lt = 3
        else:
            lt = 1
        pygame.draw.line(screen, LIGHT_GREY, (x, 0), (x, ymax), lt)
    for dy in range(1, vertical_axis_divisions):
        y = vertical_pixels_per_division * dy
        # mark the central position (v, i = 0) with a thicker line
        if dy == vertical_axis_divisions // 2:
            lt = 3
        else:
            lt = 1
        pygame.draw.line(screen, LIGHT_GREY, (0, y), (xmax, y), lt)


def draw_lines(screen, background_surface, lines):
    # blit the screen with background image (graticule)
    screen.blit(background_surface, (0,0))
    # can handle up to six lines
    colours = [ GREEN, YELLOW, MAGENTA, CYAN, RED, BLUE ]
    for i in range(len(lines)):
        pygame.draw.lines(screen, colours[i], False, lines[i], 2)
            

def refresh_wfs():
    # refresh the information box every second
    t = int(time.time())
    if t != refresh_wfs.seconds:
        refresh_wfs.seconds = t
        texts.set_text(T_WFS, str(refresh_wfs.frames) + ' wfm/s')
        refresh_wfs.frames = 0 
    refresh_wfs.frames = refresh_wfs.frames + 1
    
refresh_wfs.frames=0
refresh_wfs.seconds=int(time.time())


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
 
    
def read_points(f):
    ps = []
    tp = 0
    # the loop will exit and the points list is returned if
    # (a) there is no more data to read, or
    # (b) if the time coordinate 'goes backwards'
    while is_data_available(f, 0.1):
        ws = f.readline().split()
        t = int(ws[0])
        if t < tp:
            break
        ws = ws[1:]
        for i in range(len(ws)):
            try:
                ps[i].append((t, int(ws[i])))   # extend an existing line
            except IndexError:
                ps.append( [(t, int(ws[i]))] )  # or add another line if it doesn't exist yet
        tp = t
    return ps

   
def main():
    global capturing, running, texts

    get_settings()

    # initialise UI
    pygame.init()
    pygame.display.set_caption('pqm-hellebores')

    # fullscreen on Pi, but not on laptop
    if get_screen_hardware_size() == PI_SCREEN_SIZE:
        screen    = pygame.display.set_mode(PI_SCREEN_SIZE, flags=pygame.FULLSCREEN)
    else:
        screen    = pygame.display.set_mode(PI_SCREEN_SIZE)
    buttons   = initialise_buttons()
    texts     = Texts()
    uibox     = initialise_uibox(buttons, texts.get_texts())
    menu      = initialise_dispatching(uibox, screen)

    # make the mouse pointer invisible
    # can't make the pointer inactive using the pygame flags because we need it working
    # to return correct coordinates from the touchscreen
    pygame.mouse.set_cursor((8,8),(0,0),(0,0,0,0,0,0,0,0),(0,0,0,0,0,0,0,0))

    # set up the background image
    background_surface = pygame.Surface(SCOPE_BOX_SIZE)
    background_surface.fill(GREY)
    draw_graticule(background_surface)

    # now set up the initial text states
    texts.clear_texts()
    texts.set_text(T_RUNSTOP, "Running")
    
    # initialise flags
    running = True          # the loop will run continuously until this is set to False
    capturing = True        # allow/stop update of the lines on the screen

    while running:
        
        # waveform display update
        if capturing:
            lines = read_points(sys.stdin)
            if lines and len(lines[0]) > 1:
                draw_lines(screen, background_surface, lines)

        # UI/buttons update
        process_events(menu)
        refresh_wfs()
        # uibox.update()  # enable this only if required
        uibox.blit()
        
        # update the display
        # this flips the re-drawn screen surface into the framebuffer (hardware)
        pygame.display.update()

    pygame.quit()



if __name__ == '__main__':
    main()


