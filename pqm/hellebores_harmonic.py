import sys
import thorpy
import pygame
from hellebores_constants import *
from hellebores_controls import *


# text message cell enumerations
T_RUNSTOP       = 0
T_RANGE_WARNING = 1


class Harmonic:

    def __init__(self, st, app_actions):
        self.texts = []
        # this will hold a lookup of ui value objects, keyed by reading key
        self.harmonic_value_objects = {}
        # store a local copy of st and app_actions
        self.st = st
        self.app_actions = app_actions
        # create an empty background to draw onto
        self.harmonic_background = pygame.Surface(SCOPE_BOX_SIZE)
        self.harmonic_background.fill(GREY)
        # create the controls
        self.harmonic_controls = self.create_harmonic_controls()
        # create the readings
        self.harmonic_display = self.create_harmonic_display()
        # all the elements
        self.harmonic_elements = [ self.harmonic_controls, self.harmonic_display ]

    def set_text(self, item, value):
        self.texts[item].set_text(value)

    def draw_texts(self, capturing):
        if self.st.current_sensor=='low':
            self.texts[T_RANGE_WARNING].set_bck_color(ORANGE)
            self.texts[T_RANGE_WARNING].set_text('LOW RANGE', adapt_parent=False)
        else:
            self.texts[T_RANGE_WARNING].set_bck_color(LIGHT_GREY)
            self.texts[T_RANGE_WARNING].set_text('', adapt_parent=False)
        if capturing:
            self.texts[T_RUNSTOP].set_bck_color(GREEN)
            self.texts[T_RUNSTOP].set_text('Running', adapt_parent=False)
        else:
            self.texts[T_RUNSTOP].set_bck_color(RED)
            self.texts[T_RUNSTOP].set_text('Stopped', adapt_parent=False)

    def refresh(self, capturing, buffer, screen, datetime):
        """display all the readings"""
        screen.blit(self.harmonic_background, (0,0))
        if capturing:
            self.update_harmonic_display(buffer.cs)
        self.harmonic_display.draw()
        datetime.draw()

    def create_harmonic_controls(self):
        """Multimeter controls, on right of screen"""
        control_texts = []
        for s in range(2):
            t = thorpy.Text('')
            t.set_size(TEXT_SIZE)
            t.set_font_color(BLACK)
            control_texts.append(t)
        button_setup = [
            ('Run/Stop', self.app_actions.start_stop),
            ('Mode', lambda: self.app_actions.set_updater('mode')),
            ('Range', lambda: self.app_actions.set_updater('current_sensitivity')),
            ('Clear', lambda: self.app_actions.set_updater('clear')),
            ('Options', lambda: self.app_actions.set_updater('options'))
            ]
        buttons = [ configure_button(BUTTON_SIZE, bt, bf) for bt, bf in button_setup ]
        # Now add the harmonic controls
        harmonic_controls = thorpy.Box([ *control_texts[:2], *buttons, *control_texts[2:] ])
        harmonic_controls.set_topright(*CONTROLS_BOX_POSITION)
        harmonic_controls.set_bck_color(LIGHT_GREY)
        for e in harmonic_controls.get_all_descendants():
            e.hand_cursor = False
        self.texts = control_texts
        return harmonic_controls

    def update_harmonic_display(self, readings):
        """Takes a set of analysis results and pushes them into the display."""
        valid_keys = self.harmonic_value_objects.keys()
        
        # set the value into the display object
        def set_value(key, value):
            tp_value, value_characters, decimals, display_scaling = self.harmonic_value_objects[key]
            tp_value.set_text(f'{value*display_scaling:7.{decimals}f}'.rjust(value_characters),\
                adapt_parent=False)

        # push readings into display text fields
        for key in readings:
            if key == 'harmonic_voltage_percentages' or key == 'harmonic_current_percentages':
                # we have to extend the key by the harmonic order (the input value is an array)
                for i in range(51):
                    set_value(f'{key}_{i}', readings[key][i])
            elif key in valid_keys:
                set_value(key, readings[key])


    def create_ui_display_texts(self, definitions, x):
        ui_display_texts = []
        y = 0
        for item in definitions:
            key, label, w, label_h, label_font_size, value_h, value_font_size, label_characters, value_characters, gap_h, decimals, display_scaling = item
            # create the label object
            tp_label = thorpy.Text(label.rjust(label_characters))
            tp_label.set_size((w,label_h))
            tp_label.set_font_size(label_font_size)
            tp_label.set_font_color(WHITE)
            tp_label.set_topleft(x,y)
            ui_display_texts.append(tp_label)
            y = y + label_h
            # create the value object 
            tp_value = thorpy.Text('999.999'.rjust(value_characters))
            tp_value.set_size((w,value_h))
            tp_value.set_font_size(value_font_size)
            tp_value.set_font_color(YELLOW)
            tp_value.set_topleft(x,y)
            ui_display_texts.append(tp_value)
            y = y + value_h + gap_h
            # add lookup of multimeter value object, with parameters for text format
            # keyed by analysis key
            self.harmonic_value_objects[key] = (tp_value, value_characters, decimals, display_scaling)
        return ui_display_texts


    def create_harmonic_display(self):
        """Harmonic display, on main part of screen"""
        #  Voltage rms /V
        #  Frequency /Hz
        #  THDv /%h1
        #  Harmonic voltage /%
        #  h0
        #  h1        h11        h21        h31        h41
        #  h2        h12        h22        h32        h42
        #  h3        h13        h23        h33        h43
        #  h4        h14        h24        h34        h44
        #  h5        h15        h25        h35        h45
        #  h6        h16        h26        h36        h46
        #  h7        h17        h27        h37        h47
        #  h8        h18        h28        h38        h48
        #  h9        h19        h29        h39        h49
        #  h10       h20        h30        h40        h50
        #
        # Format of the table is:
        # analysis key, label text, width, label height, label font size, value height, value font size,
        # number of label characters, number of value characters, vertical padding,
        # number of decimal places, display scaling factor for value.
        column_1        = [ ('rms_voltage', 'Voltage rms /V',
                                224, 18, FONT_SIZE, 20, FONT_SIZE, 28, 28, 0, 1, 1),
                            ('frequency', 'Frequency /Hz',
                                224, 18, FONT_SIZE, 20, FONT_SIZE, 28, 28, 0, 1, 1),
                            ('total_harmonic_distortion_voltage_percentage', 'THD(v) /%',
                                224, 18, FONT_SIZE, 20, FONT_SIZE, 28, 28, 0, 1, 1),
                            ('', 'Harmonic voltage /%',
                                224, 18, FONT_SIZE, 20, FONT_SIZE, 28, 28, 0, 1, 1) ]
        for i in range(0,11):
            column_1.append((f'harmonic_voltage_percentages_{i}', f'h{i}',
                                 224, 18, FONT_SIZE, 20, FONT_SIZE, 28, 28, 0, 1, 1))

        column_2        = [ ('', '', 224, 18, FONT_SIZE, 100, FONT_SIZE, 28, 28, 0, 1, 1) ]
        for i in range(11,21):
            column_2.append(('harmonic_voltage_percentages_{i}', f'h{i}',
                                 224, 18, FONT_SIZE, 20, FONT_SIZE, 28, 28, 0, 1, 1))

        column_3        = [ ('', '', 224, 18, FONT_SIZE, 100, FONT_SIZE, 28, 28, 0, 1, 1) ]
        for i in range(21,31):
            column_3.append(('harmonic_voltage_percentages_{i}', f'h{i}',
                                 224, 18, FONT_SIZE, 20, FONT_SIZE, 28, 28, 0, 1, 1))

        column_4        = [ ('', '', 224, 18, FONT_SIZE, 100, FONT_SIZE, 28, 28, 0, 1, 1) ]
        for i in range(31,41):
            column_4.append(('harmonic_voltage_percentages_{i}', f'h{i}',
                                 224, 18, FONT_SIZE, 20, FONT_SIZE, 28, 28, 0, 1, 1))

        column_5        = [ ('', '', 224, 18, FONT_SIZE, 100, FONT_SIZE, 28, 28, 0, 1, 1) ]
        for i in range(41,51):
            column_5.append(('harmonic_voltage_percentages_{i}', f'h{i}',
                                 224, 18, FONT_SIZE, 20, FONT_SIZE, 28, 28, 0, 1, 1))
        
        # create harmonic measurement display object
        harmonic_display = thorpy.Group([ thorpy.Group(self.create_ui_display_texts(column_1, 0), mode=None),
                                          thorpy.Group(self.create_ui_display_texts(column_2, 60), mode=None), 
                                          thorpy.Group(self.create_ui_display_texts(column_3, 120), mode=None),  
                                          thorpy.Group(self.create_ui_display_texts(column_4, 180), mode=None),   
                                          thorpy.Group(self.create_ui_display_texts(column_5, 240), mode=None) ],
                                        mode='h', gap=0, margins=(0,0))
        harmonic_display.set_topleft(*METER_POSITION)
        return harmonic_display




