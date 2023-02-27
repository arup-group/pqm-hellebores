#!/usr/bin/env python3

# 
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
strings = ['Running', 'This.', 'is', 'some', 'test text', '12345678']


def initialise_buttons():
    global buttons
    buttons = []
    for s in ['Run/Stop', 'Mode', 'Logging', 'Scales', 'Options', 'About']:
        button = thorpy.make_button(s)
        button.set_size(BUTTON_SIZE)
        buttons.append(button)

def initialise_texts():
    global texts
    texts = []
    for s in range(0,7):
        text = thorpy.make_text('1234567890')
        text.set_size(TEXT_SIZE)
        texts.append(text)


def initialise_uibox():
    global buttons, texts
 
    # create the user interface object
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
       strings[0] = 'Stopped'
   else:
       capturing = True
       strings[0] = 'Running'


def about_box_reaction(event):
   thorpy.launch_blocking_alert(title="This is an about box!",
                               text="This is the text..",
                               ok_text="Ok, I've read",
                               font_size=12,
                               font_color=(255,0,0))


# update text message strings, called periodically
def set_text_strings(texts, strings):
    i=0
    for s in strings:
        texts[i].set_text(s)
        i=i+1


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


def refresh_lines(screen):
    # update line data
    plot1, plot2, plot3 = to_screen_coordinates(*get_capture([],[],[]))

    # regenerate display 
    screen.fill(GRAY)
    pygame.draw.lines(screen, GREEN, False, plot1, 2)
    pygame.draw.lines(screen, YELLOW, False, plot2, 2)
    pygame.draw.lines(screen, MAGENTA, False, plot3, 2)


def refresh_information_box():
    global strings, texts, seconds, frames

    # refresh the information box every second
    new_seconds = int(time.time())
    if new_seconds != seconds:
        seconds = new_seconds
        strings[1] = str(frames) + ' wfm/s'
        set_text_strings(texts, strings)
        frames = 0 

    # this allows us to see the number of waveform updates/second
    frames = frames + 1



def main():
    global buttons, texts, capturing, running, seconds, frames

    # initialise UI
    screen = pygame.display.set_mode(SCREEN)       # flags=pygame.FULLSCREEN
    initialise_buttons()
    initialise_texts()
    uibox = initialise_uibox()
    menu = initialise_dispatching(uibox, screen)

    # initialise flags and variables
    running = True
    capturing = True
    frames = 0
    seconds = int(time.time())

#    f = open_fifo()

    while running:
        process_events(menu)
        if capturing: 
            refresh_lines(screen)
        refresh_information_box()

        # update the display
        uibox.blit()
        # uibox.update()
        pygame.display.update()

    pygame.quit()



if __name__ == '__main__':
    main()


