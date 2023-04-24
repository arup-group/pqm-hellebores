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
BUTTON_SIZE = (92,50) 
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
    

def create_buttons():
    buttons = {}
    buttons['main']           = [ thorpy.make_button('Run/Stop', func = start_stop_reaction),\
                                  thorpy.make_button('Mode', func = mode_reaction),\
                                  thorpy.make_button('Horizontal', func = horizontal_reaction),\
                                  thorpy.make_button('Vertical', func = vertical_reaction),\
                                  thorpy.make_button('Trigger', func = trigger_reaction),\
                                  thorpy.make_button('Options', func = about_box_reaction) ]

    buttons['mode']           = [ thorpy.make_button('Back', func = back_reaction),\
                                  thorpy.make_button('Waveform', func = mode_reaction),\
                                  thorpy.make_button('Meter', func = horizontal_reaction),\
                                  thorpy.make_button('Harmonics', func = vertical_reaction),\
                                  thorpy.make_button('Logging', func = options_reaction) ]

    buttons['horizontal']     = [ thorpy.make_button('Back', func = back_reaction),\
                                  thorpy.make_button('< Zoom >', func = horizontal_zoom_reaction),\
                                  thorpy.make_button('> Expand <', func = horizontal_expand_reaction),\
                                  thorpy.make_button('t0 >', func = time_right_reaction),\
                                  thorpy.make_button('< t0', func = time_left_reaction),\
                                  thorpy.make_button('Trigger', func = trigger_reaction) ]

    buttons['trigger']        = [ thorpy.make_button('Back', func = back_reaction),\
                                  thorpy.make_button('Trigger channel', func = trigger_channel_reaction),\
                                  thorpy.make_button('Trigger level', func = trigger_level_reaction),\
                                  thorpy.make_button('Trigger direction', func = trigger_direction_reaction) ]
                            
    buttons['vertical']       = [ thorpy.make_button('Back', func = back_reaction),\
                                  thorpy.make_button('< Zoom >', func = vertical_zoom_reaction),\
                                  thorpy.make_button('> Expand <', func = vertical_expand_reaction) ]
                            
    buttons['options']        = [ thorpy.make_button('Back', func = back_reaction),\
                                  thorpy.make_button('Wifi', func = wifi_reaction),\
                                  thorpy.make_button('Shell', func = shell_reaction),\
                                  thorpy.make_button('Exit', func = exit_reaction) ]
    # set buttons to all be the same size                        
    for mode in buttons.keys():
        for button in buttons[mode]:
            button.set_size(BUTTON_SIZE)
    return buttons

def mode_reaction():
   1

def horizontal_reaction():
   1

def vertical_reaction():
   1

def trigger_reaction():
   1

def options_reaction():
   1

def back_reaction():
   1

def horizontal_zoom_reaction():
   1

def horizontal_expand_reaction():
   1

def time_right_reaction():
   1

def time_left_reaction():
   1

def trigger_channel_reaction():
   1

def trigger_level_reaction():
   1

def trigger_direction_reaction():
   1

def vertical_zoom_reaction():
   1

def vertical_expand_reaction():
   1

def trigger_direction_reaction():
   1

def wifi_reaction():
   1

def shell_reaction():
   1

def exit_reaction():
   1




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
    uibox.add_reaction(thorpy.ConstantReaction(thorpy.constants.THORPY_EVENT, \
                           refresh_reaction, {"id": thorpy.constants.EVENT_TIME}))
    uibox.add_reaction(thorpy.ConstantReaction(pygame.KEYDOWN, \
                           quit_reaction, {"key": pygame.K_q})) 
    uibox.set_size(CONTROLS_BOX_SIZE)
    uibox.set_topleft((PI_SCREEN_SIZE[0]-CONTROLS_BOX_SIZE[0],0))
    return uibox


def initialise_menu(uibox, screen):
    # a menu object is needed for events dispatching
    menu = thorpy.Menu(uibox, fps=120) 

    # set the screen to be the display surface
    for element in menu.get_population():
        element.surface = screen

    return menu


def start_stop_reaction():
   global capturing
   if capturing == True:
       capturing = False
       texts.set_text(T_RUNSTOP, "Stopped")
   else:
       capturing = True
       texts.set_text(T_RUNSTOP, "Running")
       

def about_box_reaction():
   thorpy.launch_nonblocking_alert(title="hellebores.py",
                               text="Power quality meter, v0.01",
                               ok_text="Ok, I've read",
                               font_size=12,
                               font_color=RED)
   print("A non-blocking alert was launched")


def refresh_reaction():
    global wfs, texts, capturing, screen, background_surface
    # update the wfs and corresponding display 
    if wfs.refresh_wfs() == True:
        texts.get_texts()[1].unblit_and_reblit()
    # update the lines only if capturing
    if capturing:
        lines = read_points(sys.stdin)
        if lines and len(lines[0]) > 1:
            # blit the screen with background image (graticule)
            screen.blit(background_surface, (0,0))
            draw_lines(screen, background_surface, lines)
            wfs.increment_wfs()
    # send to display surface and update framebuffer
    pygame.display.update()


def quit_reaction():
    global capturing
    capturing = False
    print("Quitting...", file=sys.stderr)    
    thorpy.functions.quit_menu_func() 


def draw_background():
    global st, background_surface
    xmax, ymax = SCOPE_BOX_SIZE

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
            texts.set_text(T_WFS, f'{round(self.counter/elapsed)} wfm/s          ')
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
 
    
def read_points(f):
    ps = []
    tp = 0
    # the loop will exit and the points list is returned if
    # (a) there is no more data waiting to be read, or
    # (b) if the time coordinate 'goes backwards'
    while is_data_available(f, 1.0):
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
    global st, capturing, texts, background_surface, uibox, texts, screen, wfs

    # get settings from settings.json
    st = settings.Settings(draw_background)
    draw_background()

    # initialise UI
    application = thorpy.Application(PI_SCREEN_SIZE, 'pqm-hellebores')

    # fullscreen on Pi, but not on laptop
    # also make the mouse pointer invisible on Pi, as we will use the touchscreen
    # we can't make the pointer inactive using the pygame flags because we need it working
    # to return correct coordinates from the touchscreen
    if get_screen_hardware_size() == PI_SCREEN_SIZE:
        screen    = pygame.display.set_mode(PI_SCREEN_SIZE, flags=pygame.FULLSCREEN)
        pygame.mouse.set_cursor((8,8),(0,0),(0,0,0,0,0,0,0,0),(0,0,0,0,0,0,0,0))
    else:
        screen    = pygame.display.set_mode(PI_SCREEN_SIZE)

    buttons   = create_buttons()
    texts     = Texts()
    wfs       = WFS_Counter()
    uibox     = initialise_uibox(buttons['main'], texts.get_texts())
    menu      = initialise_menu(uibox, screen)

    # now set up the initial text states
    texts.clear_texts()
    texts.set_text(T_RUNSTOP, "Running")
    
    # initialise flags
    capturing = True        # allow/stop update of the lines on the screen

    # start the thorpy event handler loop
    menu.play()
    application.quit()



if __name__ == '__main__':
    main()


