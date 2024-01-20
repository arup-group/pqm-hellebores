#!/usr/bin/env python3

# figlet
#           _               _                                           
# _ __ __ _(_)_ __      ___| |__   ___   ___  ___  ___ _ __ _ __  _   _ 
#| '__/ _` | | '_ \    / __| '_ \ / _ \ / _ \/ __|/ _ \ '__| '_ \| | | |
#| | | (_| | | | | |  | (__| | | | (_) | (_) \__ \  __/ | _| |_) | |_| |
#|_|  \__,_|_|_| |_|___\___|_| |_|\___/ \___/|___/\___|_|(_) .__/ \__, |
#                 |_____|                                  |_|    |___/ 
#

# library imports
import thorpy
import pygame
import time
import sys
import os
import math
import random

# local import
import settings



WINDOW_SIZE = (430, 500)
FONT = 'font/RobotoMono-Medium.ttf'
FONT_SIZE = 12
BACKGROUND_COLOUR = (200, 200, 50)


def sample(i, fs, noise):
    """Iterator, list of tuples (freqency, magitude, phase) and noise magnitude."""
    global st
    t = i*st.interval/1000.0       # convert iterator to time axis position
    s = 0
    for f in fs:
        (freq, mag, ph) = f
        s = s + mag*math.sin(math.pi*(2*freq*t + ph/180.))
    #s = s + noise*(random.random()-0.5)
    return s

def generate_samples():
    """Generates a block of n samples to bring us up to date wrt to system clock."""
    global st, sample_index, time_zero

    def scale(scale_factor, sample):
        """convert to 16 bit integer. Note that after conversion, negative
           numbers are expressed in 2s complement form."""
        return int(scale_factor*sample) & 0xffff

    new_time_mark = time.time()*1000.0
    n = int((new_time_mark - time_zero)/st.interval) - sample_index
    # to avoid stalling the ui, don't attempt to print more
    # than 1000 samples in one go: jump forward and return early instead
    if n > 1000:
        sample_index = sample_index + n 
        return

    f = 50
    while n > 0:
        c0 = scale(1.0, sample(sample_index, [(f, 25000.0, 0.0)], 100.0))
        c1 = scale(1.0, sample(sample_index, [(f, 8000.0, 0.0), (3*f, 3000.0, 30.0/3)], 10.0))
        c2 = scale(1.0, sample(sample_index, [(f, 200.0, 0.0)], 5.0))
        c3 = scale(1.0, sample(sample_index, [(f, 5000.0, 0.0)], 10.0))
        # update the running total
        sample_index = sample_index + 1
        n = n - 1
        print(f"{sample_index & 0xffff:04x} {c0:04x} {c1:04x} {c2:04x} {c3:04x}")
    return


def before_refresh(screen, preset_dropdownlistbutton, textinputs):
    """Function called just before screen refresh"""
    global current_preset
    #screen.fill(BACKGROUND_COLOUR)
    check_preset = preset_dropdownlistbutton.get_value()
    if check_preset != current_preset:
        load_settings_from_preset(check_preset, textinputs)
        current_preset = check_preset
    generate_samples()


def load_settings_from_preset(preset, textinputs):
    """Pushes preset settings into controls"""
    preset_settings = { 'One':   { 'supply':  [230, 50, 2, 90, 2, -90, 2, 180, 2],
                                   'load':    [2, 0, 50, 60, 30, -60, 10, 0, 2],
                                   'leakage': [0.1, 90] },

                        'Two':   { 'supply':  [230, 50, 5, 45, 5, -45, 5, 180, 2],
                                   'load':    [5, 0, 50, 30, 30, -30, 10, 0, 2],
                                   'leakage': [0.01, 90] },

                        'Three': { 'supply':  [120, 60, 2, 90, 2, -90, 2, 180, 2],
                                   'load':    [2, 0, 50, 60, 30, -60, 10, 0, 2],
                                   'leakage': [0.1, 90] },

                        'Four':  { 'supply':  [230, 50, 2, 90, 2, -90, 2, 180, 2],
                                   'load':    [2, 0, 50, 60, 30, -60, 10, 0, 2],
                                   'leakage': [0.1, 90] } }
 
    # we iterate over the values and the TextInput elements in turn
    # and set the value of each element to the preset
    required_settings = preset_settings[preset]
    
    for e, v in zip(textinputs['supply'], required_settings['supply']):
        e.value = str(v)
    for e, v in zip(textinputs['load'], required_settings['load']):
        e.value = str(v)
    for e, v in zip(textinputs['leakage'], required_settings['leakage']):
        e.value = str(v)


def create_input_elements(requirements, title):
    # keep a list of the active elements in ui_items
    ui_textinputs = []
    # ui_groups holds a list of line 'groups'
    ui_groups = []
    for line in requirements:
       # make a temporary list of elements just for one line
       ui_line = []
       for (label, textinput) in line:
           ti = thorpy.TextInput(textinput, '')
           ti.set_size((50,30))
           ui_line.append(thorpy.Labelled(label.ljust(14), ti))
           ui_textinputs.append(ti)
       # now add the line as a horizontal group to the main list
       ui_groups.append(thorpy.Group(ui_line, mode='h'))
    ui_titlebox = thorpy.TitleBox(title, ui_groups)

    return (ui_textinputs, ui_titlebox)


def setup_ui(screen):
    # set up the UI objects and group them
    preset_dropdownlistbutton = thorpy.DropDownListButton(['One', 'Two', 'Three', 'Four'])
    preset_dropdownlistbutton.set_value('One')
    preset = thorpy.Labelled('Preset: ', preset_dropdownlistbutton)
    preset.stick_to(screen, self_side='top', other_side='top')

    supply_setup = [ [('Voltage /V:', '0'), ('Frequency:', '0')],
                     [('Voltage h3 %:', '0'), ('Phase:', '0')],
                     [('Voltage h5 %:', '0'), ('Phase:', '0')],
                     [('Voltage h7 %:', '0'), ('Phase:', '0')] ]
    supply_textinputs, supply_titlebox = create_input_elements(supply_setup, 'Supply')
    supply_titlebox.stick_to(preset, self_side='top', other_side='bottom')

    load_setup =   [ [('Current /A:', '0'), ('Phase:', '0')],
                     [('Current h3 %:', '0'), ('Phase:', '0')],
                     [('Current h5 %:', '0'), ('Phase:', '0')],
                     [('Current h7 %:', '0'), ('Phase:', '0')] ]
    load_textinputs, load_titlebox = create_input_elements(load_setup, 'Load')
    load_titlebox.stick_to(supply_titlebox, self_side='top', other_side='bottom')

    leakage_setup =[ [('Leakage /mA:', '0'), ('Phase:', '0')] ]
    leakage_textinputs, leakage_titlebox = create_input_elements(leakage_setup, 'Leakage current')
    leakage_titlebox.stick_to(load_titlebox, self_side='top', other_side='bottom')

    # make groups of textinputs for manipulation later
    textinputs = { 'supply': supply_textinputs,
                   'load': load_textinputs,
                   'leakage': leakage_textinputs }
    all_ui = thorpy.Group([preset, supply_titlebox, load_titlebox, leakage_titlebox])
    
    return (all_ui, preset_dropdownlistbutton, textinputs)


def main():
    # import constants from settings
    global st, current_preset, time_zero, sample_index
    st = settings.Settings()
    # we use the system clock to regulate how fast to print samples
    time_zero = int(time.time()*1000.0)
    sample_index = 0
    current_preset = None

    # initialise pygame
    pygame.init()
    pygame.display.set_caption('rain_chooser')
    screen = pygame.display.set_mode(WINDOW_SIZE)

    # initialise thorpy
    thorpy.set_default_font(FONT, FONT_SIZE)
    thorpy.init(screen, thorpy.theme_classic)

    # setup the ui
    all_ui, preset_dropdownlistbutton, textinputs = setup_ui(screen)

    # player is an object that knows how to draw itself
    player = all_ui.get_updater()

    # before_refresh is a callback that is called just before the screen is updated
    #player.launch(lambda: before_refresh(screen, preset_dropdownlistbutton, textinputs))

    # now loop, generating output and checking for user input events
    while True:

        # Check if anything happened in the UI
        events = pygame.event.get()
        if events != []:
            for e in events:
                if (e.type == pygame.QUIT) or (e.type == pygame.KEYDOWN and e.key == pygame.K_q):
                    pygame.quit()
                    sys.exit(0)

            check_preset = preset_dropdownlistbutton.get_value()
            if check_preset != current_preset:
                load_settings_from_preset(check_preset, textinputs)
                current_preset = check_preset
 
            screen.fill(BACKGROUND_COLOUR)
            all_ui.get_updater().update(events=events)

            # push all of our updated work into the active display framebuffer
            pygame.display.flip()

        # Push out some samples
        generate_samples()

    pygame.quit()

if __name__ == '__main__':
    main()


