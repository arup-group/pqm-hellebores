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

    def __init__(self, st, app_actions, harmonic_of_what):
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
        self.create_harmonic_display(harmonic_of_what)
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
            # harmonic voltages and currents are a special case, because the value is an array
            # but the text keys are referenced individually
            if key == 'harmonic_voltage_percentages' or key == 'harmonic_current_percentages':
                if f'{key}_0' in valid_keys:
                    # we have to extend the key by the harmonic order (the input value is an array)
                    for i in range(51):
                        set_value(f'{key}_{i}', readings[key][i])
            # the remainder of reading keys map directly into the corresponding text value fields
            elif key in valid_keys:
                set_value(key, readings[key])


    def add_ui_text(self, text='999.9', text_length=10, font_size=FONT_SIZE, font_colour=WHITE, \
        scale_factor=1, dp_fix=1, value_key=None, p_offset=(0,0), p_move=(0,0)):
        # create the text object
        if text != '':
            tp_text = thorpy.Text(text.rjust(text_length))
            tp_text.set_font_size(font_size)
            tp_text.set_font_color(font_colour)
            tp_text.set_topleft(self._item_position[0] + p_offset[0], self._item_position[1] + p_offset[1])
            # if it's a value field, add a lookup for the multimeter value object
            if value_key:
                self.harmonic_value_objects[ value_key ] = (tp_text, text_length, dp_fix, scale_factor)
            # save a reference to the text object in a list of text objects
            self._hd_items.append(tp_text)
        # update insertion point for next item, if required
        self._item_position = (self._item_position[0] + p_move[0], self._item_position[1] + p_move[1])
           

    def create_harmonic_display(self, harmonic_of_what):
        """Harmonic display, on main part of screen.
        Pushes a group of thorpy text objects into self.harmonic_display"""
        #  Voltage rms /V
        #  Frequency /Hz
        #  THD(v) /%
        #  THD(i) /%
        #
        #  Harmonic voltage magnitudes (% of Voltage rms)
        #
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
        # set first insertion position to origin
        self._item_position = (0, 0)
        #
        # adapt construction of display to voltage or current readings
        if harmonic_of_what == 'voltage':
            rms_label = 'Voltage rms /V'
            rms_value = 'rms_voltage'
            harmonic_table_label = 'Harmonic voltage magnitudes (% of Voltage rms)' 
            harmonic_value_root = 'harmonic_voltage_percentages'
            value_colour = GREEN
        elif harmonic_of_what == 'current':
            rms_label = 'Current rms /A'
            rms_value = 'rms_current'
            harmonic_table_label = 'Harmonic current magnitudes (% of Current rms)' 
            harmonic_value_root = 'harmonic_current_percentages'
            value_colour = YELLOW
        else:
            print(f'Harmonic.create_harmonic_display(): Incorrect harmonic table selector {harmonic_of_what}', \
                file=sys.stderr)

        self.add_ui_text(text=rms_label, text_length=16)
        self.add_ui_text(text_length=10, font_colour=value_colour, value_key=rms_value, \
            p_offset=(140,0), p_move=(0,18))

        self.add_ui_text(text='Frequency /Hz', text_length=16)
        self.add_ui_text(text_length=10, font_colour=ORANGE, value_key='frequency', \
            p_offset=(140,0), p_move=(0,18))

        self.add_ui_text(text='THD(v) /%', text_length=16)
        self.add_ui_text(text_length=10, font_colour=GREEN, \
            value_key='total_harmonic_distortion_voltage_percentage', \
            p_offset=(140,0), p_move=(0,18))

        self.add_ui_text(text='THD(i) /%', text_length=16)
        self.add_ui_text(text_length=10, font_colour=YELLOW, \
            value_key='total_harmonic_distortion_current_percentage', \
            p_offset=(140,0), p_move=(0,28))

        self.add_ui_text(text=harmonic_table_label, text_length=49, p_move=(0,28))

        for i in range(0,11):
            self.add_ui_text(text=f'h{i}', text_length=8)
            self.add_ui_text(text_length=6, font_colour=value_colour, \
                value_key=f'{harmonic_value_root}_{i}', p_offset=(70,0), p_move=(0,28))
        self.add_ui_text(text='', p_move=(130,-280))

        for i in range(11,21):
            self.add_ui_text(text=f'h{i}', text_length=8)
            self.add_ui_text(text_length=6, font_colour=value_colour, \
                value_key=f'{harmonic_value_root}_{i}', p_offset=(70,0), p_move=(0,28))
        self.add_ui_text(text='', p_move=(130,-280))

        for i in range(21,31):
            self.add_ui_text(text=f'h{i}', text_length=8)
            self.add_ui_text(text_length=6, font_colour=value_colour, \
                value_key=f'{harmonic_value_root}_{i}', p_offset=(70,0), p_move=(0,28))
        self.add_ui_text(text='', p_move=(130,-280))

        for i in range(31,41):
            self.add_ui_text(text=f'h{i}', text_length=8)
            self.add_ui_text(text_length=6, font_colour=value_colour, \
                value_key=f'{harmonic_value_root}_{i}', p_offset=(70,0), p_move=(0,28))
        self.add_ui_text(text='', p_move=(130,-280))

        for i in range(41,51):
            self.add_ui_text(text=f'h{i}', text_length=8)
            self.add_ui_text(text_length=6, font_colour=value_colour, \
                value_key=f'{harmonic_value_root}_{i}', p_offset=(70,0), p_move=(0,28))

        self.harmonic_display = thorpy.Group( self._hd_items, mode=None, gap=0, margins=(0,0) )
        self.harmonic_display.set_topleft(*METER_POSITION)


