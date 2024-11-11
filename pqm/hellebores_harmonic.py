import sys
import thorpy
import pygame
from hellebores_constants import *
from hellebores_controls import *


# text message cell enumerations
T_RUNSTOP       = 0
T_RANGE_WARNING = 1


class Harmonic:

    # TODO
    # rename self.texts to self.status_texts to be more descriptive

    def __init__(self, st, app_actions):
        self.texts = []                # list of status text elements
        self.harmonic_controls = []    # control buttons
        self.harmonic_display = []     # harmonic display (labels and values)
        self.harmonic_elements = []    # self.harmonic_controls + self.harmonic_display
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
        # create the text objects for labels and readings
        self.create_harmonic_display()
        # combine all the elements
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
            tp_text, text_length, dp_fix, scale_factor = self.harmonic_value_objects[key]
            tp_text.set_text(f'{value*scale_factor:7.{dp_fix}f}'.rjust(text_length), adapt_parent=False)


        # push readings into display text fields
        for key in readings:
            # implement harmonic_current_percentages once voltage percentages are working correctly!
            #if key == 'harmonic_voltage_percentages' or key == 'harmonic_current_percentages':
            if key == 'harmonic_voltage_percentages':
                # we have to extend the key by the harmonic order (the input value is an array)
                for i in range(51):
                    set_value(f'{key}_{i}', readings[key][i])
            elif key in valid_keys:
                set_value(key, readings[key])



    # { text: 'Voltage rms /V', text_length: 20, pixels: (224,18), v_pad: 0,\
    # font_size: FONT_SIZE, font_colour: YELLOW, scale_factor: 1, dp_fix: 1, value_key: 'rms_voltage' } 
    def add_ui_text(self, definition, value_field=False, v_inc=0):
        # create the text object
        tp_text = thorpy.Text(definition['text'].rjust(definition['text_length']))
        tp_text.set_size(definition['pixels'])
        tp_text.set_font_size(definition['font_size'])
        tp_text.set_font_color(definition['font_colour'])
        # if it's a value field, add a lookup for the multimeter value object
        if value_field:
            self.harmonic_value_objects[ definition['value_key'] ] = (tp_text, definition['text_length'], \
                definition['dp_fix'], definition['scale_factor'])
            tp_text.set_topleft(self.item_position[0] + self.value_offset[0], self.item_position[1] + self.value_offset[1])
        else:
            tp_text.set_topleft(*self.item_position)
        # save a reference to the text object in a list of text objects
        self._hd_items.append(tp_text)
        # increment row position
        self.item_position = (self.item_position[0], self.item_position[1] + v_inc)
        

    def create_harmonic_display(self):
        """Harmonic display, on main part of screen.
        Push thorpy text objects into self.harmonic_display"""
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
 
        # variable to store list of thorpy text objects while we are building them
        self._hd_items = []
        # set dimensional offsets to zero
        self.item_position = (0, 0)
        #
        # Format: in dictionary form for ease of reading.
        # For a label field, can omit the scale_factor, dp_fix and value_key elements
        # { text: 'Voltage rms /V', text_length: 20, pixels: (224,18), v_pad: 0,\
        # font_size: FONT_SIZE, font_colour: YELLOW, scale_factor: 1, dp_fix: 1, value_key: 'rms_voltage' } 
        #
        self.value_offset = (140,0)
        self.add_ui_text( {'text': 'Voltage rms /V', 'text_length': 16, 'pixels': (140,18), \
            'font_size': FONT_SIZE, 'font_colour': WHITE } )
        self.add_ui_text( {'text': '999.9', 'text_length': 10, 'pixels': (80,18), \
                'font_size': FONT_SIZE, 'font_colour': YELLOW, \
                'scale_factor': 1, 'dp_fix': 1, 'value_key': 'rms_voltage' }, value_field=True, v_inc=18 )

        self.add_ui_text( {'text': 'Frequency /Hz', 'text_length': 16, 'pixels': (140,18), \
            'font_size': FONT_SIZE, 'font_colour': WHITE } )
        self.add_ui_text( {'text': '999.9', 'text_length': 10, 'pixels': (80,18), \
                'font_size': FONT_SIZE, 'font_colour': YELLOW, \
                'scale_factor': 1, 'dp_fix': 1, 'value_key': 'frequency' }, value_field=True, v_inc=18 )

        self.add_ui_text( {'text': 'THD(v) /%', 'text_length': 16, 'pixels': (140,18), \
            'font_size': FONT_SIZE, 'font_colour': WHITE } )
        self.add_ui_text( {'text': '999.9', 'text_length': 10, 'pixels': (80,18), \
                'font_size': FONT_SIZE, 'font_colour': YELLOW, \
                'scale_factor': 1, 'dp_fix': 1, 'value_key': 'total_harmonic_distortion_voltage_percentage' }, \
                 value_field=True, v_inc=18 )

        self.add_ui_text( {'text': 'THD(i) /%', 'text_length': 16, 'pixels': (140,18), \
            'font_size': FONT_SIZE, 'font_colour': WHITE } )
        self.add_ui_text( {'text': '999.9', 'text_length': 10, 'pixels': (80,18), \
                'font_size': FONT_SIZE, 'font_colour': YELLOW, \
                'scale_factor': 1, 'dp_fix': 1, 'value_key': 'total_harmonic_distortion_current_percentage' }, \
                value_field=True, v_inc=28 )

        self.add_ui_text( {'text': 'Harmonic voltage magnitudes (% of Voltage RMS)', 'text_length': 49, \
            'pixels': (388,18), 'v_pad': 30, 'font_size': FONT_SIZE, 'font_colour': WHITE } )

        self.item_position = (self.item_position[0], self.item_position[1] + 28)
        self.value_offset = (70,0)
        for i in range(0,11):
            self.add_ui_text( {'text': f'h{i}', 'text_length': 8, 'pixels': (70,18), \
                'font_size': FONT_SIZE, 'font_colour': WHITE } )
            self.add_ui_text( {'text': '999.99', 'text_length': 6, 'pixels': (60,18), \
                'font_size': FONT_SIZE, 'font_colour': YELLOW, 'scale_factor': 1, 'dp_fix': 1, \
                'value_key': f'harmonic_voltage_percentages_{i}' }, value_field=True, v_inc=28 )
        self.item_position = (self.item_position[0] + 130, self.item_position[1] - 280)

        #definitions[2].append( {'text': '', 'text_length': 1, 'pixels': (60,18), 'v_pad': 100, \
        #    'font_size': FONT_SIZE, 'font_colour': WHITE } )
        for i in range(11,21):
            self.add_ui_text( {'text': f'h{i}', 'text_length': 8, 'pixels': (70,18), \
                'font_size': FONT_SIZE, 'font_colour': WHITE } )
            self.add_ui_text( {'text': '999.99', 'text_length': 6, 'pixels': (60,18), \
                'font_size': FONT_SIZE, 'font_colour': YELLOW, 'scale_factor': 1, 'dp_fix': 1, \
                'value_key': f'harmonic_voltage_percentages_{i}' }, value_field=True, v_inc=28 )
        self.item_position = (self.item_position[0] + 130, self.item_position[1] - 280)

        for i in range(21,31):
            self.add_ui_text( {'text': f'h{i}', 'text_length': 8, 'pixels': (70,18), \
                'font_size': FONT_SIZE, 'font_colour': WHITE } )
            self.add_ui_text( {'text': '999.99', 'text_length': 6, 'pixels': (60,18), \
                'font_size': FONT_SIZE, 'font_colour': YELLOW, 'scale_factor': 1, 'dp_fix': 1, \
                'value_key': f'harmonic_voltage_percentages_{i}' }, value_field=True, v_inc=28 )
        self.item_position = (self.item_position[0] + 130, self.item_position[1] - 280)

        for i in range(31,41):
            self.add_ui_text( {'text': f'h{i}', 'text_length': 8, 'pixels': (70,18), \
                'font_size': FONT_SIZE, 'font_colour': WHITE } )
            self.add_ui_text( {'text': '999.99', 'text_length': 6, 'pixels': (60,18), \
                'font_size': FONT_SIZE, 'font_colour': YELLOW, 'scale_factor': 1, 'dp_fix': 1, \
                'value_key': f'harmonic_voltage_percentages_{i}' }, value_field=True, v_inc=28 )
        self.item_position = (self.item_position[0] + 130, self.item_position[1] - 280)

        for i in range(41,51):
            self.add_ui_text( {'text': f'h{i}', 'text_length': 8, 'pixels': (70,18), \
                'font_size': FONT_SIZE, 'font_colour': WHITE } )
            self.add_ui_text( {'text': '999.99', 'text_length': 6, 'pixels': (60,18), \
                'font_size': FONT_SIZE, 'font_colour': YELLOW, 'scale_factor': 1, 'dp_fix': 1, \
                'value_key': f'harmonic_voltage_percentages_{i}' }, value_field=True, v_inc=28 )

        self.harmonic_display = thorpy.Group( self._hd_items, mode=None, gap=0, margins=(0,0) )
        self.harmonic_display.set_topleft(*METER_POSITION)


