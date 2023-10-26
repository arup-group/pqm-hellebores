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
    # array of thorpy text objects
    texts = []
    multimeter_background = None
    current_range = 'full'

    def __init__(self, st, app_actions):
        self.st = st
        self.app_actions = app_actions
        for s in range(12):
            t = thorpy.Text('')
            t.set_size(TEXT_SIZE)
            if s==0:
                t.set_font_color(BLACK)
            else:
                t.set_font_color(WHITE)
            self.texts.append(t)
        self.draw_background()

    def set_text(self, item, value):
        self.texts[item].set_text(value)

    def draw_texts(self, capturing):
        if capturing:
            self.texts[T_RUNSTOP].set_bck_color(GREEN)
            self.texts[T_RUNSTOP].set_text('Running', adapt_parent=False)
        else:
            self.texts[T_RUNSTOP].set_bck_color(RED)
            self.texts[T_RUNSTOP].set_text('Stopped', adapt_parent=False)

    def draw_background(self):
        # empty background
        self.multimeter_background = pygame.Surface(SCOPE_BOX_SIZE)
        self.multimeter_background.fill(GREY)

    def refresh(self, buffer, screen):
        # display all the readings
        screen.blit(self.multimeter_background, (0,0))

    def create_multimeter_controls(self):
        """Multimeter controls, on right of screen"""
        button_setup = [
            ('Run/Stop', self.app_actions.start_stop),
            ('Mode', lambda: self.app_actions.set_updater('mode')), 
            ('Range', lambda: self.app_actions.set_updater('current_range')), 
            ('Options', lambda: self.app_actions.set_updater('options'))
            ]
        buttons = [ configure_button(BUTTON_SIZE, bt, bf) for bt, bf in button_setup ]
        multimeter_controls = thorpy.Box([ *self.texts[0:2], *buttons, *self.texts[2:] ])
        multimeter_controls.set_topright(*CONTROLS_BOX_POSITION)
        multimeter_controls.set_bck_color(LIGHT_GREY)
        for e in multimeter_controls.get_all_descendants():
            e.hand_cursor = False    
        return multimeter_controls

