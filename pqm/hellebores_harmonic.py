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
    def create_ui_display_texts(self, definitions):
        ui_display_texts = []
        x = 0                  # x pixel offset
        # definitions contains a list of text object definitions, by column then by item
        # we iterate through the list of lists
        for column in definitions:
            y = 0              # y pixel offset
            x_inc = 0          # x increment to next column
            for t in column:
                # allows explicit relative re-positioning
                if 'reposition' in t:
                    (x_inc, y_inc) = t['reposition']
                    x += x_inc
                    y += y_inc
                    continue
                x_inc = max(x_inc, t['pixels'][0])
                y_inc = t['pixels'][1] + t['v_pad']
                # create the text object
                tp_text = thorpy.Text(t['text'].rjust(t['text_length']))
                tp_text.set_size(t['pixels'])
                tp_text.set_font_size(t['font_size'])
                tp_text.set_font_color(t['font_colour'])
                tp_text.set_topleft(x,y)
                ui_display_texts.append(tp_text)
                # if it's a variable, add a lookup for the multimeter value object
                if 'value_key' in t.keys():
                    self.harmonic_value_objects[ t['value_key'] ] = (tp_text, t['text_length'], t['dp_fix'], \
                        t['scale_factor'])
                # reposition ready for next item in column
                y = y + y_inc
            # reposition for next column
            x = x + x_inc
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
        # Format: in dictionary form for ease of reading.
        # For a label field, can omit the scale_factor, dp_fix and value_key elements
        # { text: 'Voltage rms /V', text_length: 20, pixels: (224,18), v_pad: 0,\
        # font_size: FONT_SIZE, font_colour: YELLOW, scale_factor: 1, dp_fix: 1, value_key: 'rms_voltage' } 
        #
        # initialise array of columns to hold definition of display texts
        definitions = [ [] for i in range(10) ]

        definitions[0].append( {'text': 'Voltage rms /V', 'text_length': 16, 'pixels': (140,18), 'v_pad': 0, \
            'font_size': FONT_SIZE, 'font_colour': WHITE } )
        definitions[1].append( {'text': '999.9', 'text_length': 10, 'pixels': (60,18), 'v_pad': 0, \
            'font_size': FONT_SIZE, 'font_colour': YELLOW, 'scale_factor': 1, 'dp_fix': 1, \
            'value_key': 'rms_voltage' } )

        definitions[0].append( {'text': 'Frequency /Hz', 'text_length': 16, 'pixels': (140,18), 'v_pad': 0, \
            'font_size': FONT_SIZE, 'font_colour': WHITE } )
        definitions[1].append( {'text': '999.9', 'text_length': 10, 'pixels': (60,18), 'v_pad': 0, \
            'font_size': FONT_SIZE, 'font_colour': YELLOW, 'scale_factor': 1, 'dp_fix': 1, \
            'value_key': 'frequency' } )

        definitions[0].append( {'text': 'THD(v) /%', 'text_length': 16, 'pixels': (140,18), 'v_pad': 0, \
            'font_size': FONT_SIZE, 'font_colour': WHITE } )
        definitions[1].append( {'text': '999.9', 'text_length': 10, 'pixels': (60,18), 'v_pad': 0, \
            'font_size': FONT_SIZE, 'font_colour': YELLOW, 'scale_factor': 1, 'dp_fix': 1, \
            'value_key': 'total_harmonic_distortion_voltage_percentage' } )

        definitions[0].append( {'text': 'THD(i) /%', 'text_length': 16, 'pixels': (140,18), 'v_pad': 10, \
            'font_size': FONT_SIZE, 'font_colour': WHITE } )
        definitions[1].append( {'text': '999.9', 'text_length': 10, 'pixels': (60,18), 'v_pad': 10, \
            'font_size': FONT_SIZE, 'font_colour': YELLOW, 'scale_factor': 1, 'dp_fix': 1, \
            'value_key': 'total_harmonic_distortion_current_percentage' } )

        definitions[0].append( {'text': 'Harmonic voltage magnitudes (as % of Voltage RMS)', 'text_length': 52, \
            'pixels': (412,18), 'v_pad': 10, 'font_size': FONT_SIZE, 'font_colour': WHITE } )

        definitions[0].append( {'reposition': (0,0) } )
        definitions[1].append( {'reposition': (0,28) } )
        for i in range(0,11):
            definitions[0].append( {'text': f'h{i}', 'text_length': 8, 'pixels': (70,18), 'v_pad': 10, \
                'font_size': FONT_SIZE, 'font_colour': WHITE } )
            definitions[1].append( {'text': '999.99', 'text_length': 6, 'pixels': (60,18), 'v_pad': 10, \
                'font_size': FONT_SIZE, 'font_colour': YELLOW, 'scale_factor': 1, 'dp_fix': 1, \
                'value_key': f'harmonic_voltage_percentages_{i}' } )

        #definitions[2].append( {'text': '', 'text_length': 1, 'pixels': (60,18), 'v_pad': 100, \
        #    'font_size': FONT_SIZE, 'font_colour': WHITE } )
        definitions[2].append( {'reposition': (0,138) } )
        definitions[3].append( {'reposition': (0,138) } )
        for i in range(11,21):
            definitions[2].append( {'text': f'h{i}', 'text_length': 8, 'pixels': (70,18), 'v_pad': 10, \
                'font_size': FONT_SIZE, 'font_colour': WHITE } )
            definitions[3].append( {'text': '999.99', 'text_length': 6, 'pixels': (60,18), 'v_pad': 10, \
                'font_size': FONT_SIZE, 'font_colour': YELLOW, 'scale_factor': 1, 'dp_fix': 1, \
                'value_key': f'harmonic_voltage_percentages_{i}' } )

        definitions[4].append( {'reposition': (0,138) } )
        definitions[5].append( {'reposition': (0,138) } )
        for i in range(21,31):
            definitions[4].append( {'text': f'h{i}', 'text_length': 8, 'pixels': (70,18), 'v_pad': 10, \
                'font_size': FONT_SIZE, 'font_colour': WHITE } )
            definitions[5].append( {'text': '999.99', 'text_length': 6, 'pixels': (60,18), 'v_pad': 10, \
                'font_size': FONT_SIZE, 'font_colour': YELLOW, 'scale_factor': 1, 'dp_fix': 1, \
                'value_key': f'harmonic_voltage_percentages_{i}' } )

        definitions[6].append( {'reposition': (0,138) } )
        definitions[7].append( {'reposition': (0,138) } )
        for i in range(31,41):
            definitions[6].append( {'text': f'h{i}', 'text_length': 8, 'pixels': (70,18), 'v_pad': 10, \
                'font_size': FONT_SIZE, 'font_colour': WHITE } )
            definitions[7].append( {'text': '999.99', 'text_length': 6, 'pixels': (60,18), 'v_pad': 10, \
                'font_size': FONT_SIZE, 'font_colour': YELLOW, 'scale_factor': 1, 'dp_fix': 1, \
                'value_key': f'harmonic_voltage_percentages_{i}' } )

        definitions[8].append( {'reposition': (0,138) } )
        definitions[9].append( {'reposition': (0,138) } )
        for i in range(41,51):
            definitions[8].append( {'text': f'h{i}', 'text_length': 8, 'pixels': (70,18), 'v_pad': 10, \
                'font_size': FONT_SIZE, 'font_colour': WHITE } )
            definitions[9].append( {'text': '999.99', 'text_length': 6, 'pixels': (60,18), 'v_pad': 10, \
                'font_size': FONT_SIZE, 'font_colour': YELLOW, 'scale_factor': 1, 'dp_fix': 1, \
                'value_key': f'harmonic_voltage_percentages_{i}' } )

        harmonic_display = thorpy.Group( self.create_ui_display_texts(definitions), mode=None, gap=0, margins=(0,0) )
        harmonic_display.set_topleft(*METER_POSITION)
        return harmonic_display


