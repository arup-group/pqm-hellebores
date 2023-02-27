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
# from pygame.locals import *

CAPTURE_BUFFER = '/tmp/capture_buffer'    # this is a fifo that we read data from
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
MAGENTA = (255, 0, 255)
GRAY = (150, 150, 150)
SCREEN = (800,480)
SCOPE_BOX = (700,480)
CONTROLS_BOX = (100,480)
BUTTON_SIZE = (100,50) 
TEXT_SIZE = (100,12)

pygame.init()
pygame.display.set_caption('pqm-hellebores')

# text message cell enumerations
T_RUNSTOP = 0
T_WFS = 1
T_UNDEF2 = 2
T_UNDEF3 = 3
T_UNDEF4 = 4
T_UNDEF5 = 5


def initialise_buttons():
    buttons = []
    for s in ['Run/Stop', 'Mode', 'Logging', 'Scales', 'Options', 'About']:
        button = thorpy.make_button(s)
        button.set_size(BUTTON_SIZE)
        buttons.append(button)
    return buttons


def initialise_texts():
    texts = []
    for s in range(0,7):
        text = thorpy.make_text('123456789')  # the dummy text here allocates pixels
        text.set_size(TEXT_SIZE)
        texts.append(text)
    return texts


# update text message string
def set_text_string(item, value):
    set_text_string.texts[item].set_text(value)
# initialise local variable, assigned in main()
set_text_string.texts = []


def clear_texts():
    for t in set_text_string.texts:
        t.set_text('')


def initialise_uibox(buttons, texts):
    # create the user interface object, and add reactions to it
    uibox = thorpy.Box(elements=[*buttons, *texts])
    uibox.add_reaction(thorpy.Reaction(reacts_to=thorpy.constants.THORPY_EVENT, \
                       reac_func=start_stop_reaction, \
                       event_args={"el": buttons[0], "id": thorpy.constants.EVENT_UNPRESS}))

    uibox.add_reaction(thorpy.Reaction(reacts_to=thorpy.constants.THORPY_EVENT, \
                       reac_func=about_box_reaction, \
                       event_args={"el": buttons[5], "id": thorpy.constants.EVENT_UNPRESS}))

    uibox.set_size(CONTROLS_BOX)
    uibox.set_topleft((SCREEN[0]-CONTROLS_BOX[0],0))
    return uibox


def initialise_dispatching(uibox, screen):
    # a menu object is needed for events dispatching
    menu = thorpy.Menu(uibox) 

    # set the screen to be the display surface
    for element in menu.get_population():
        element.surface = screen

    # we do not launch the menu because it creates a hidden event loop
    # while we need to have a free running loop in pygame.
    #menu.play() #launch the menu
    return menu


def start_stop_reaction(event):
   global capturing
   if capturing == True:
       capturing = False
       set_text_string(T_RUNSTOP, "Stopped")
   else:
       capturing = True
       set_text_string(T_RUNSTOP, "Running")
       

def about_box_reaction(event):
   thorpy.launch_blocking_alert(title="hellebores.py",
                               text="Power quality meter, v0.01",
                               ok_text="Ok, I've read",
                               font_size=12,
                               font_color=(255,0,0))




def get_capture(points1, points2, points3):
    T_DIV = 0.005    # standard scope time/div
    FREQ = 60.0
    for s in range(0, SCOPE_BOX[0]):
        t = T_DIV*10.0*s/SCOPE_BOX[0]
        points1.append((s, 50.0*math.sin(2.0*math.pi*FREQ*t) + 20.0*(random.random() - 0.5)))
        points2.append((s, 50.0*math.sin(2.0*math.pi*FREQ*t) + 20.0*(random.random() - 0.5)))
        points3.append((s, points1[s][1]*points2[s][1]))
    return points1, points2, points3


def to_screen_coordinates(points1, points2, points3):
    plot1 = []
    plot2 = []
    plot3 = []
    for t in range(0, len(points1)):
        # invert y axis in plot coordinates, which increase from top of the display downwards
        plot1.append((t, 100-int(points1[t][1])))
        plot2.append((t, 400-int(points2[t][1])))
        plot3.append((t, 250-int(0.05*points3[t][1])))
    return plot1, plot2, plot3


def open_fifo():
    try:
        f = open(CAPTURE_BUFFER, "r")
        return f
    except:
        print("Couldn't open the fifo capture_buffer")
        sys.exit(1)


def get_capture_from_file(f):
    FRAME_LENGTH = 540
    counter = 0
    frame = []
    try:
        while counter<=FRAME_LENGTH:
            i, v1, v2, v3, v4 = readline(f).split()
            frame.append((i,v1,v2,v3,v4)) 
            counter = counter+1
    except:
        print("Couldn't read from capture buffer.")
    return frame


def process_events(menu):
    global running
    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
            running = False
        menu.react(event)


def draw_lines(screen, lines):
    # draw updated lines 
    screen.fill(GRAY)
    pygame.draw.lines(screen, GREEN, False, lines[0], 2)
    pygame.draw.lines(screen, YELLOW, False, lines[1], 2)
    pygame.draw.lines(screen, MAGENTA, False, lines[2], 2)
    

def refresh_lines():
    # update line data
    line1, line2, line3 = to_screen_coordinates(*get_capture([],[],[]))
    return (line1, line2, line3)


def refresh_wfs():
    # refresh the information box every second
    new_seconds = int(time.time())
    if new_seconds != refresh_wfs.seconds:
        refresh_wfs.seconds = new_seconds
        set_text_string(T_WFS, str(refresh_wfs.frames) + ' wfm/s')
        refresh_wfs.frames = 0 

    # this allows us to see the number of waveform updates/second
    refresh_wfs.frames = refresh_wfs.frames + 1
    
refresh_wfs.frames=0
refresh_wfs.seconds=int(time.time())



def main():
    global capturing, running

    # initialise UI
    screen    = pygame.display.set_mode(SCREEN)       # flags=pygame.FULLSCREEN
    buttons   = initialise_buttons()
    texts     = initialise_texts()
    uibox     = initialise_uibox(buttons, texts)
    menu      = initialise_dispatching(uibox, screen)

    # set a local variable at set_text_string() to point to texts
    set_text_string.texts = texts
    # now set up the initial text states
    clear_texts()
    set_text_string(T_RUNSTOP, "Running")
    
    # initialise flags
    running = True          # the loop will run continuously until this is set to False
    capturing = True        # allow/stop update of the lines on the screen

#    f = open_fifo()
    while running:
        process_events(menu)
        
        # update information
        if capturing:
            lines = refresh_lines()
        refresh_wfs()
        
        # redraw the buffer
        draw_lines(screen, lines)
        uibox.blit()
        # uibox.update()  # enable this only if required
        
        # update the display
        pygame.display.update()

    pygame.quit()



if __name__ == '__main__':
    main()


