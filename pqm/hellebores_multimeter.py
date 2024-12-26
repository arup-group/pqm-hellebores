import sys
import thorpy
import pygame
from hellebores_constants import *
from hellebores_controls import *


# text message cell enumerations
T_RUNSTOP       = 0
T_RANGE_WARNING = 1


class Multimeter:

    def __init__(self, st, app_actions):
        self.multimeter_display = []
        self.st = st
        self.ann = Annunciators(st, app_actions)
        # this will contain the text objects to push readings into, keyed by analysis result key
        self.multimeter_value_objects = {}
        self.app_actions = app_actions
        # create an empty background to draw onto
        self.multimeter_background = pygame.Surface(SCOPE_BOX_SIZE)
        self.multimeter_background.fill(GREY)
        # create the controls
        self.multimeter_controls = self.create_multimeter_controls()
        # create the readings
        self.create_multimeter_display()
        # all the elements
        self.multimeter_elements = [ self.multimeter_controls, self.multimeter_display ]


    def update_annunciators(self):
        self.ann.update_annunciators()


    def refresh(self, buffer, screen):
        """display all the readings"""
        screen.blit(self.multimeter_background, (0,0))
        if self.st.run_mode == 'running':
            self.update_multimeter_display(buffer.cs)
        self.multimeter_display.draw()

           
    def create_multimeter_controls(self):
        """Multimeter controls, on right of screen"""
        button_setup = [
            ('Run/Stop', self.app_actions.start_stop),
            ('Mode', lambda: self.app_actions.set_updater('mode')), 
            ('Range', lambda: self.app_actions.set_updater('current_sensitivity')), 
            ('Clear', lambda: self.app_actions.set_updater('clear')),
            ('Options', lambda: self.app_actions.set_updater('options'))
            ]
        buttons = [ configure_button(BUTTON_SIZE, bt, bf) for bt, bf in button_setup ]
        ts = self.ann.get_text_objects()[:2]   # first two annunciators only
        # Now add the multimeter controls
        multimeter_controls = thorpy.Box([ *ts, *buttons ])
        multimeter_controls.set_topright(*CONTROLS_BOX_POSITION)
        multimeter_controls.set_bck_color(LIGHT_GREY)
        for e in multimeter_controls.get_all_descendants():
            e.hand_cursor = False    
        return multimeter_controls


    def update_multimeter_display(self, readings):
        """Takes a set of analysis results and pushes them into the display."""
        valid_keys = self.multimeter_value_objects.keys()
        # push readings into display text fields
        for key in readings:
            if key in valid_keys:
                tp_value, padding, decimals, display_scaling = self.multimeter_value_objects[key]
                tp_value.set_text(f'{readings[key]*display_scaling:7.{decimals}f}'.rjust(padding),\
                        adapt_parent=False)


    def update_position(self, p_move=(0,0)):
        self._item_position = (self._item_position[0] + p_move[0], self._item_position[1] + p_move[1])

    
    def add_ui_text(self, text='999.9', text_length=10, font_size=FONT_SIZE, font_colour=WHITE, \
        scale_factor=1, dp_fix=1, value_key=None, p_offset=(0,0), p_move=(0,0)):
        """Creates a text object for describing or displaying values of results. Default
        text parameters in the function prototype can be changed when calling. p_offset is a position
        offset that applies temporarily, whereas p_move fixes a change to the insertion point that will
        affect subsequent calls."""
        tp_text = thorpy.Text(text.rjust(text_length))
        tp_text.set_font_size(font_size)
        tp_text.set_font_color(font_colour)
        tp_text.set_topleft(self._item_position[0] + p_offset[0], self._item_position[1] + p_offset[1])
        # if it's a value field, add a lookup for the multimeter value object
        if value_key:
            self.multimeter_value_objects[ value_key ] = (tp_text, text_length, dp_fix, scale_factor)
        # save a reference to the text object in a list of text objects
        self._hd_items.append(tp_text)
        # update insertion point for next item, if required
        self.update_position(p_move)


    def create_multimeter_display(self):
        """Multimeter display, on main part of screen"""
        #
        # Voltage /Vrms            Voltage maximum /Vrms            Energy accumulator /kWh
        #                          Voltage minimum /Vrms            Reactive energy accumulator /kVARh
        # Current /Arms            Current maximum /Arms            Apparent energy accumulator /kVAh
        #                          Current minimum /Arms            Accumulation time /hr
        # Power /W                 Power maximum /W                 Crest factor /1
        #                          Power minimum /W                 Frequency /Hz
        # Reactive power /VAR      Reactive power maximum /VAR      THDv /%
        #                          Reactive power minimum /VAR      THDi /% 
        # Apparent power /VA       Apparent power maximum /VA       Earth leakage /mA 
        #                          Apparent power minimum /VA       
        # Power factor /1          
        #                         
        # Format of the table is:
        # analysis key, label text, width and height, font size, number of characters,
        # vertical padding, number of decimal places, display scaling factor for value.

        # variable to store list of thorpy text objects while we are building them
        self._hd_items = []
        # set first insertion position to origin
        self._item_position = (0,0)

        # Column 1 
        self.add_ui_text(text='Voltage rms /V', text_length=32)
        self.add_ui_text(text_length=7, font_size=LARGE_FONT_SIZE, font_colour=GREEN, \
            value_key='rms_voltage', p_offset=(0,6), p_move=(0,86))

        self.add_ui_text(text='Current rms /V', text_length=32)
        self.add_ui_text(text_length=7, font_size=LARGE_FONT_SIZE, font_colour=YELLOW, \
            dp_fix=3, value_key='rms_current', p_offset=(0,6), p_move=(0,86))

        self.add_ui_text(text='Power /W', text_length=32)
        self.add_ui_text(text_length=7, font_size=LARGE_FONT_SIZE, font_colour=MAGENTA, \
            dp_fix=2, value_key='mean_power', p_offset=(0,6), p_move=(0,86))

        self.add_ui_text(text='Reactive power /VAR', text_length=32)
        self.add_ui_text(text_length=7, font_size=LARGE_FONT_SIZE, font_colour=ORANGE, \
            dp_fix=2, value_key='mean_volt_ampere_reactive', p_offset=(0,6), p_move=(0,86))

        self.add_ui_text(text='Apparent power /VA', text_length=32)
        self.add_ui_text(text_length=7, font_size=LARGE_FONT_SIZE, font_colour=ORANGE, \
            dp_fix=2, value_key='mean_volt_ampere', p_offset=(0,6), p_move=(0,86))

        # Column 2
        self.update_position((220,-430))

        self.add_ui_text(text='Vmax rms /V', text_length=24)
        self.add_ui_text(text_length=24, font_colour=GREEN, \
            value_key='rms_voltage_max', p_offset=(0,18), p_move=(0,38))

        self.add_ui_text(text='Vmin rms /V', text_length=24)
        self.add_ui_text(text_length=24, font_colour=GREEN, \
            value_key='rms_voltage_min', p_offset=(0,18), p_move=(0,48))

        self.add_ui_text(text='Imax rms /V', text_length=24)
        self.add_ui_text(text_length=24, font_colour=YELLOW, \
            dp_fix=3, value_key='rms_current_max', p_offset=(0,18), p_move=(0,38))

        self.add_ui_text(text='Imin rms /V', text_length=24)
        self.add_ui_text(text_length=24, font_colour=YELLOW, \
            dp_fix=3, value_key='rms_current_min', p_offset=(0,18), p_move=(0,48))

        self.add_ui_text(text='Pmax /W', text_length=24)
        self.add_ui_text(text_length=24, font_colour=MAGENTA, \
            dp_fix=2, value_key='mean_power_max', p_offset=(0,18), p_move=(0,38))

        self.add_ui_text(text='Pmin /W', text_length=24)
        self.add_ui_text(text_length=24, font_colour=MAGENTA, \
            dp_fix=2, value_key='mean_power_min', p_offset=(0,18), p_move=(0,48))

        self.add_ui_text(text='RPmax /VAR', text_length=24)
        self.add_ui_text(text_length=24, font_colour=ORANGE, \
            dp_fix=2, value_key='mean_volt_ampere_reactive_max', p_offset=(0,18), p_move=(0,38))

        self.add_ui_text(text='RPmin /VAR', text_length=24)
        self.add_ui_text(text_length=24, font_colour=ORANGE, \
            dp_fix=2, value_key='mean_volt_ampere_reactive_min', p_offset=(0,18), p_move=(0,48))

        self.add_ui_text(text='APmax /VA', text_length=24)
        self.add_ui_text(text_length=24, font_colour=ORANGE, \
            dp_fix=2, value_key='mean_volt_ampere_max', p_offset=(0,18), p_move=(0,38))

        self.add_ui_text(text='APmin /VA', text_length=24)
        self.add_ui_text(text_length=24, font_colour=ORANGE, \
            dp_fix=2, value_key='mean_volt_ampere_min', p_offset=(0,18), p_move=(0,48))

        # Column 3

        self.update_position((240,-430))

        self.add_ui_text(text='Energy /Wh', text_length=24)
        self.add_ui_text(text_length=24, font_colour=ORANGE, \
            dp_fix=3, value_key='watt_hour', p_offset=(0,18), p_move=(0,38))

        self.add_ui_text(text='Reactive energy /VARh', text_length=24)
        self.add_ui_text(text_length=24, font_colour=ORANGE, \
            dp_fix=3, value_key='volt_ampere_reactive_hour', p_offset=(0,18), p_move=(0,38))

        self.add_ui_text(text='Apparent energy /VAh', text_length=24)
        self.add_ui_text(text_length=24, font_colour=ORANGE, \
            dp_fix=3, value_key='volt_ampere_hour', p_offset=(0,18), p_move=(0,38))

        self.add_ui_text(text='Accumulation time /hr', text_length=24)
        self.add_ui_text(text_length=24, font_colour=ORANGE, \
            dp_fix=3, value_key='hours', p_offset=(0,18), p_move=(0,78))

        self.add_ui_text(text='Power factor /1', text_length=24)
        self.add_ui_text(text_length=24, font_colour=ORANGE, \
            dp_fix=2, value_key='power_factor', p_offset=(0,18), p_move=(0,38))

        self.add_ui_text(text='Crest factor /1', text_length=24)
        self.add_ui_text(text_length=24, font_colour=YELLOW, \
            dp_fix=2, value_key='crest_factor_current', p_offset=(0,18), p_move=(0,38))

        self.add_ui_text(text='Frequency /Hz', text_length=24)
        self.add_ui_text(text_length=24, font_colour=ORANGE, \
            dp_fix=2, value_key='frequency', p_offset=(0,18), p_move=(0,38))

        self.add_ui_text(text='THD(v) /%', text_length=24)
        self.add_ui_text(text_length=24, font_colour=GREEN, \
            dp_fix=2, value_key='total_harmonic_distortion_voltage_percentage', p_offset=(0,18), p_move=(0,38))

        self.add_ui_text(text='THD(i) /%', text_length=24)
        self.add_ui_text(text_length=24, font_colour=YELLOW, \
            dp_fix=2, value_key='total_harmonic_distortion_current_percentage', p_offset=(0,18), p_move=(0,38))

        self.add_ui_text(text='Earth leakage /mA', text_length=24)
        self.add_ui_text(text_length=24, font_colour=CYAN, \
            scale_factor=1000, dp_fix=3, value_key='rms_leakage_current', p_offset=(0,18), p_move=(0,38))

        # insert all text elements into a group, then position group in display

        self.multimeter_display = thorpy.Group( self._hd_items, mode=None, gap=0, margins=(0,0) )
        self.multimeter_display.set_topleft(*METER_POSITION)



