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

    def refresh(self, buffer, screen, datetime):
        # display all the readings
        screen.blit(self.multimeter_background, (0,0))
        self.multimeter_readings.draw()
        datetime.draw()

    def left_pad(self, texts, width):
        pad = ' ' * width
        # update strings in place
        for i in range(len(texts)):
            texts[i] = (pad + texts[i])[-width:]
            
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
        #
        # Voltage /Vrms            Voltage maximum /Vrms            Voltage inst. maximum /V
        #                          Voltage minimum /Vrms            Voltage inst. minimum /V
        # Current /Arms            Current maximum /Arms            Current inst. maximum /A
        #                          Current minimum /Arms            Current inst. minimum /A
        # Power /W                 Power maximum /W                 Power inst. maximum /W 
        #                          Power minimum /W                 Power inst. minimum /W
        # Reactive power /VAR      Reactive power maximum /VAR      Crest factor /1
        #                          Reactive power minimum /VAR      Frequency /Hz
        # Apparent power /VA       Apparent power maximum /VA       Energy accumulator /kWh
        #                          Apparent power minimum /VA       Reactive energy accumulator /kVAh
        # Power factor /1          THDv /%                          Accumulation time /hr
        #                          THDi /%

        field_labels_1        = [ 'Voltage rms /V',
                                  'Current rms /A',
                                  'Power /W',
                                  'Reactive power /VAR',
                                  'Apparent power /VA',
                                  'Power factor /1' ]
        self.left_pad(field_labels_1, 28)
        initial_values_1      = [ '999.999' for i in range(len(field_labels_1)) ]
        field_labels_2        = [ 'Voltage maximum rms /V',
                                  'Voltage minimum rms /V',
                                  'Current maximum rms /A'
                                  'Current minimum rms /A',
                                  'Power maximum /W',
                                  'Power minimum /W',
                                  'Reactive power maximum /VAR',
                                  'Reactive power minimum /VAR',
                                  'Apparent power maximum /VA',
                                  'Apparent power minimum /VA',
                                  'THD(v) /%',
                                  'THD(i) /%' ]
        initial_values_2      = [ '999.999' for i in range(len(field_labels_2)) ]
        field_labels_3        = [ 'Voltage maximum inst. /V',
                                  'Voltage minimum inst. /V',
                                  'Current maximum inst. /A',
                                  'Current minimum inst. /A',
                                  'Power maximum inst. /W',
                                  'Power minimum inst. /W',
                                  'Crest factor /1',
                                  'Frequency /Hz',
                                  'Energy cumulative /kWh',
                                  'Reactive energy cumulative /kVARh',
                                  'Accumulation time /hr' ]
        initial_values_3      = [ '999.999' for i in range(len(field_labels_3)) ]

        labels = []
        values = []
        for l,v in zip(field_labels_1, initial_values_1):
            label = thorpy.Text(l)
            value = thorpy.Text(v)
            #label.set_size(TEXT_METER_LABEL_SIZE)
            label.set_size((230,68))
            value.set_size(TEXT_METER_SIZE)
            label.set_font_size(FONT_SIZE)
            value.set_font_size(FONT_METER_SIZE)
            label.set_font_color(WHITE)
            value.set_font_color(YELLOW)
            labels.append(label)
            values.append(value)
           
        multimeter_column_1 = thorpy.Group(labels, mode='grid', nx=1, ny=6, align='center',
                                            gap=0, margins=(0,20))
        pad = thorpy.Text('')
        pad.set_size((0,20))
        #multimeter_reading_labels = thorpy.Group([pad] + meter_texts[6:], mode='v', align='center',
        #                                          gap=0, margins=(0,0))
        multimeter = thorpy.Group([multimeter_column_1], mode='h',
                                   gap=0, margins=(0,0))
        multimeter.set_topleft(*METER_POSITION)
        multimeter.set_size((200,200))
        return multimeter


