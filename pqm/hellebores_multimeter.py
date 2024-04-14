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
        # Voltage /Vrms            Voltage maximum /Vrms            Energy accumulator /kWh
        #                          Voltage minimum /Vrms            Reactive energy accumulator /kVAh
        # Current /Arms            Current maximum /Arms            Crest factor /1
        #                          Current minimum /Arms            Frequency /Hz 
        # Power /W                 Power maximum /W                 THDv /%                         
        #                          Power minimum /W                 THDi /%
        # Reactive power /VAR      Reactive power maximum /VAR      Accumulation time /hr 
        #                          Reactive power minimum /VAR     
        # Apparent power /VA       Apparent power maximum /VA       
        #                          Apparent power minimum /VA       
        # Power factor /1          
        #                         

        column_1        = [ ('Voltage rms /V',         300, 58, LARGE_FONT_SIZE, 10),
                            ('Current rms /A',         300, 58, LARGE_FONT_SIZE, 10),
                            ('Power /W',               300, 58, LARGE_FONT_SIZE, 10),
                            ('Reactive power /VAR',    300, 58, LARGE_FONT_SIZE, 10),
                            ('Apparent power /VA',     300, 58, LARGE_FONT_SIZE, 10) ]

        column_2        = [ ('Vmax rms /V',            224, 20, FONT_SIZE, 0),
                            ('Vmin rms /V',            224, 20, FONT_SIZE, 10),
                            ('Imax rms /A',            224, 20, FONT_SIZE, 0),
                            ('Imin rms /A',            224, 20, FONT_SIZE, 10),
                            ('Pmax /W',                224, 20, FONT_SIZE, 0),
                            ('Pmin /W',                224, 20, FONT_SIZE, 10),
                            ('RPmax /VAR',             224, 20, FONT_SIZE, 0),
                            ('RPmin /VAR',             224, 20, FONT_SIZE, 10),
                            ('APmax /VA',              224, 20, FONT_SIZE, 0),
                            ('APmin /VA',              224, 20, FONT_SIZE, 10) ]

        column_3        = [ ('Energy /kWh',            224, 20, FONT_SIZE, 0),
                            ('Reactive energy /kVARh', 224, 20, FONT_SIZE, 0),
                            ('Power factor /1',        224, 20, FONT_SIZE, 0),
                            ('Crest factor /1',        224, 20, FONT_SIZE, 0),
                            ('Frequency /Hz',          224, 20, FONT_SIZE, 0),
                            ('THD(v) /%',              224, 20, FONT_SIZE, 0),
                            ('THD(i) /%',              224, 20, FONT_SIZE, 0),
                            ('Accumulation time /hr',  224, 20, FONT_SIZE, 0) ]

        tp_texts = []
        label_h = 18 
        label_font_size = FONT_SIZE
        for column, x in zip([column_1, column_2, column_3], [0, 200, 440]):
            y = 0
            for item in column:
                text, w, value_h, value_font_size, gap_h = item
                # create the label
                if x==0:
                    pad = 36
                else:
                    pad = 28
                tp_label = thorpy.Text(text.rjust(pad))
                tp_label.set_size((w,label_h))
                tp_label.set_font_size(label_font_size)
                tp_label.set_font_color(WHITE)
                tp_label.set_topleft(x,y)
                tp_texts.append(tp_label)
                y = y + label_h
                # and then initial text for the value
                if value_font_size == LARGE_FONT_SIZE:
                    pad = 8
                else:
                    pad = 28 
                tp_value = thorpy.Text('999.999'.rjust(pad))
                tp_value.set_size((w,value_h))
                tp_value.set_font_size(value_font_size)
                tp_value.set_font_color(YELLOW)
                tp_value.set_topleft(x,y)
                tp_texts.append(tp_value)
                y = y + value_h + gap_h
           
        multimeter_column_1 = thorpy.Group(tp_texts[:10], mode=None)
        multimeter_column_2 = thorpy.Group(tp_texts[10:30], mode=None)
        multimeter_column_3 = thorpy.Group(tp_texts[30:], mode=None)
        multimeter = thorpy.Group([multimeter_column_1, multimeter_column_2, multimeter_column_3],
                                   mode='h', gap=0, margins=(0,0))
        multimeter.set_topleft(*METER_POSITION)
        return multimeter


