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

WINDOW_SIZE = (1000, 700)
FONT = 'font/RobotoMono-Medium.ttf'
FONT_SIZE = 12
BACKGROUND_COLOUR = (155, 155, 155)

def before_refresh(screen, ui_group):
    screen.fill(BACKGROUND_COLOUR)
    for e in ui_group.get_all_descendants():
        # get rid of leading and trailing whitespace on text cells
        if type(e) == thorpy.elements.TextInput:
            e.set_value(e.get_value().strip())
            #e.refresh_surfaces()

def main():

   # initialise pygame
    pygame.init()
    pygame.display.set_caption('rain_chooser')
    screen    = pygame.display.set_mode(WINDOW_SIZE)

    # initialise thorpy
    thorpy.set_default_font(FONT, FONT_SIZE)
    thorpy.init(screen, thorpy.theme_simple)

    # set up the UI objects and group them
    frequency = thorpy.Labelled('Frequency:          ',
                  thorpy.TextInput('50    ', placeholder='freq'))

    v0        = thorpy.Labelled('Voltage DC offset:  ',
                  thorpy.TextInput('0     ', placeholder='dc'))

    v1        = thorpy.Group([
                  thorpy.Labelled('Voltage fundamental:',
                    thorpy.TextInput('230   ', placeholder='v1')),
                  thorpy.Labelled('Phase:              ',
                    thorpy.TextInput('0     ', placeholder='ph'))],
                  mode='h', margins=(0,0))

    v3        = thorpy.Group([
                  thorpy.Labelled('Voltage h3 %:       ',
                    thorpy.TextInput('0     ', placeholder='v3 %')),
                  thorpy.Labelled('Phase:              ',
                    thorpy.TextInput('0     ', placeholder='ph'))],
                  mode='h', margins=(0,0))

    v5        = thorpy.Group([
                  thorpy.Labelled('Voltage h5 %:       ',
                    thorpy.TextInput('0     ', placeholder='v5 %')),
                  thorpy.Labelled('Phase:              ',
                    thorpy.TextInput('0     ', placeholder='ph'))],
                  mode='h', margins=(0,0))

    v7        = thorpy.Group([
                  thorpy.Labelled('Voltage h7 %:       ',
                    thorpy.TextInput('0     ', placeholder='v7 %')),
                  thorpy.Labelled('Phase:              ',
                    thorpy.TextInput('0     ', placeholder='ph'))],
                  mode='h', margins=(0,0))



    supply    = thorpy.TitleBox('Supply', [frequency, v0, v1, v3, v5, v7])
    ui_group         = thorpy.Group([supply], mode='v', align='left')

    player = ui_group.get_updater()
    player.launch(lambda: before_refresh(screen, ui_group))
    pygame.quit()



if __name__ == '__main__':
    main()


