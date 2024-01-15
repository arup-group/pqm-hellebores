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
import select

WINDOW_SIZE = (430, 650)
FONT = 'font/RobotoMono-Medium.ttf'
FONT_SIZE = 12
BACKGROUND_COLOUR = (200, 200, 50)

current_preset=None




def make_sample(i, t, f):
    t = t/1000.0       # seconds
    c0 = int(25000.0*math.sin(2.0*math.pi*f*t) + 1.0*(random.random()-0.5))
    c1 = int(8000.0*math.sin(2.0*math.pi*f*t) + 2.0*(random.random()-0.5))
    c2 = int(200.0*math.sin(2.0*math.pi*f*t) + 5.0*(random.random()-0.5))
    c3 = int(5000.0*math.sin(2.0*math.pi*f*t) + 1.0*(random.random()-0.5))
    # the '& 0xffff' truncates negative numbers to fit in 16 bits
    return (i & 0xffff, c0 & 0xffff, c1 & 0xffff, c2 & 0xffff, c3 & 0xffff)


def before_refresh(screen, preset_dropdownlistbutton, textinputs):
    """Function called just before screen refresh"""
    global current_preset
    screen.fill(BACKGROUND_COLOUR)
    check_preset = preset_dropdownlistbutton.get_value()
    if check_preset != current_preset:
        load_settings_from_preset(check_preset, textinputs)
        current_preset = check_preset
    sys.stdout.write('.')
    sys.stdout.flush()


def load_settings_from_preset(preset, textinputs):
    """Pushes preset settings into controls"""
    preset_settings = { 'One':   { 'supply':  [230, 50, 2, 90, 2, -90, 2, 180, 2],
                                   'load':    [2, 0, 50, 60, 30, -60, 10, 0, 2],
                                   'leakage': [0.1, 90, 2] },

                        'Two':   { 'supply':  [230, 50, 5, 45, 5, -45, 5, 180, 2],
                                   'load':    [5, 0, 50, 30, 30, -30, 10, 0, 2],
                                   'leakage': [0.01, 90, 2] },

                        'Three': { 'supply':  [120, 60, 2, 90, 2, -90, 2, 180, 2],
                                   'load':    [2, 0, 50, 60, 30, -60, 10, 0, 2],
                                   'leakage': [0.1, 90, 2] },

                        'Four':  { 'supply':  [230, 50, 2, 90, 2, -90, 2, 180, 2],
                                   'load':    [2, 0, 50, 60, 30, -60, 10, 0, 2],
                                   'leakage': [0.1, 90, 2] } }
 
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
                     [('Voltage h7 %:', '0'), ('Phase:', '0')],
                     [('Noise %:', '0')] ]
    supply_textinputs, supply_titlebox = create_input_elements(supply_setup, 'Supply')
    supply_titlebox.stick_to(preset, self_side='top', other_side='bottom')

    load_setup =   [ [('Current /A:', '0'), ('Phase:', '0')],
                     [('Current h3 %:', '0'), ('Phase:', '0')],
                     [('Current h5 %:', '0'), ('Phase:', '0')],
                     [('Current h7 %:', '0'), ('Phase:', '0')], 
                     [('Noise %:', '0')] ]
    load_textinputs, load_titlebox = create_input_elements(load_setup, 'Load')
    load_titlebox.stick_to(supply_titlebox, self_side='top', other_side='bottom')

    leakage_setup =[ [('Leakage /mA:', '0'), ('Phase:', '0')],
                     [('Noise %:', '0')] ]
    leakage_textinputs, leakage_titlebox = create_input_elements(leakage_setup, 'Leakage current')
    leakage_titlebox.stick_to(load_titlebox, self_side='top', other_side='bottom')

    # make groups of textinputs for manipulation later
    textinputs = { 'supply': supply_textinputs,
                   'load': load_textinputs,
                   'leakage': leakage_textinputs }
    all_ui = thorpy.Group([preset, supply_titlebox, load_titlebox, leakage_titlebox])
    
    return (all_ui, preset_dropdownlistbutton, textinputs)


def main():

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
    player.launch(lambda: before_refresh(screen, preset_dropdownlistbutton, textinputs))
    pygame.quit()



if __name__ == '__main__':
    main()


