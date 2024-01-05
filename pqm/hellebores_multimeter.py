import sys
import thorpy
import pygame
from hellebores_constants import *
from hellebores_controls import *


# text message cell enumerations
T_RUNSTOP     = 0
T_WFS         = 1
T_TIMEDIV     = 2
T_VOLTSDIV    = 3
T_AMPSDIV     = 4
T_WATTSDIV    = 5
T_LEAKDIV     = 6


class Multimeter:

    def __init__(self, st, app_actions):
        self.texts = []
        self.st = st
        self.app_actions = app_actions
        # create an empty background to draw onto
        self.multimeter_background = pygame.Surface(SCOPE_BOX_SIZE)
        self.multimeter_background.fill(GREY)
        # create the controls
        self.multimeter_controls = self.create_multimeter_controls()
        # create the readings
        self.multimeter_readings = self.create_multimeter_readings()
        # all the elements
        self.multimeter_elements = [ self.multimeter_controls, self.multimeter_readings ]

    def set_text(self, item, value):
        self.texts[item].set_text(value)

    def draw_texts(self, capturing):
        if capturing:
            self.texts[T_RUNSTOP].set_bck_color(GREEN)
            self.texts[T_RUNSTOP].set_text('Running', adapt_parent=False)
        else:
            self.texts[T_RUNSTOP].set_bck_color(RED)
            self.texts[T_RUNSTOP].set_text('Stopped', adapt_parent=False)

    def refresh(self, buffer, screen):
        # display all the readings
        screen.blit(self.multimeter_background, (0,0))

    def create_multimeter_controls(self):
        """Multimeter controls, on right of screen"""
        control_texts = []
        for s in range(4):
            t = thorpy.Text('')
            t.set_size(TEXT_SIZE)
            if s==0:
                t.set_font_color(BLACK)
            else:
                t.set_font_color(WHITE)
            control_texts.append(t)
        button_setup = [
            ('Run/Stop', self.app_actions.start_stop),
            ('Mode', lambda: self.app_actions.set_updater('mode')), 
            ('Range', lambda: self.app_actions.set_updater('current_range')), 
            ('Options', lambda: self.app_actions.set_updater('options'))
            ]
        buttons = [ configure_button(BUTTON_SIZE, bt, bf) for bt, bf in button_setup ]
        # Now add the multimeter controls
        multimeter_controls = thorpy.Box([ *control_texts[0:2], *buttons, *control_texts[2:] ])
        multimeter_controls.set_topright(*CONTROLS_BOX_POSITION)
        multimeter_controls.set_bck_color(LIGHT_GREY)
        for e in multimeter_controls.get_all_descendants():
            e.hand_cursor = False    
        self.texts = control_texts
        return multimeter_controls

    def create_multimeter_readings(self):
        """Multimeter readings, on main part of screen"""
        reading_texts = []
        for s in [ ('230.01 ', TEXT_METER_SIZE, FONT_METER_SIZE, YELLOW),
                   ('  0.534', TEXT_METER_SIZE, FONT_METER_SIZE, YELLOW),
                   (' 20.344', TEXT_METER_SIZE, FONT_METER_SIZE, YELLOW),
                   (' 34.234', TEXT_METER_SIZE, FONT_METER_SIZE, YELLOW),
                   ('  0.762', TEXT_METER_SIZE, FONT_METER_SIZE, YELLOW),
                   ('  0.452', TEXT_METER_SIZE, FONT_METER_SIZE, YELLOW),
                   ('V  ', TEXT_METER_LABEL_SIZE, FONT_SIZE, WHITE),
                   ('A  ', TEXT_METER_LABEL_SIZE, FONT_SIZE, WHITE),
                   ('W  ', TEXT_METER_LABEL_SIZE, FONT_SIZE, WHITE),
                   ('VA ', TEXT_METER_LABEL_SIZE, FONT_SIZE, WHITE),
                   ('PF ', TEXT_METER_LABEL_SIZE, FONT_SIZE, WHITE),
                   ('kWh', TEXT_METER_LABEL_SIZE, FONT_SIZE, WHITE) ]:
            t = thorpy.Text(s[0])
            t.set_size(s[1])
            t.set_font_size(s[2])
            t.set_font_color(s[3])
            reading_texts.append(t)
        multimeter_readings = thorpy.Group(reading_texts, mode='grid', gap=0, margins=(0,0), ny=6)
        multimeter_readings.set_topleft(*METER_POSITION)
        return multimeter_readings


