import sys
import thorpy
import pygame
from hellebores_constants import *
from hellebores_controls import *


# text message cell enumerations
T_RUNSTOP       = 0
T_RANGE_WARNING = 1


class Harmonics:

    def __init__(self, st, app_actions):
        self.texts = []
        self.st = st
        self.harmonic_magnitudes = []
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
        # Now add the multimeter controls
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
        # push readings into display text fields
        for key in readings:
            if key in valid_keys:
                tp_value, getter, padding, decimals, display_scaling = self.harmonic_value_objects[key]
                tp_value.set_text(f'{readings[key]*display_scaling:7.{decimals}f}'.rjust(padding),\
                        adapt_parent=False)

    def create_harmonic_display(self):
        """Harmonic display, on main part of screen"""
        #  Voltage rms /V       Power factor /1
        #  Frequency /Hz        Crest factor /1
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
        # analysis key, label text, width and height, font size, number of characters,
        # vertical padding, number of decimal places, display scaling factor for value.
        column_1        = [ ('rms_voltage', 'Voltage rms /V',
                                224, 20, FONT_SIZE, 28, 0, 1, 1),
                            ('frequency', 'Frequency /Hz',
                                224, 20, FONT_SIZE, 28, 0, 1, 1),
                            ('total_harmonic_distortion_voltage_percentage', 'THD(v) /%',
                                224, 20, FONT_SIZE, 28, 0, 1, 1),
                            ('', 'Harmonic voltage /%',
                                224, 20, FONT_SIZE, 28, 0, 1, 1) ]
        for i in range(0,11):
            column_1.append((lambda results: results.harmonic_voltage_percentages[i], f'h{i}',
                                 224, 20, FONT_SIZE, 28, 0, 1, 1))

        column_2        = [ ('rms_voltage_max', 'Vmax rms /V',
                                224, 20, FONT_SIZE, 28, 0, 1, 1),
                            ('rms_voltage_min', 'Vmin rms /V',
                                224, 20, FONT_SIZE, 28, 10, 1, 1),
                            ('rms_current_max', 'Imax rms /A',
                                224, 20, FONT_SIZE, 28, 0, 3, 1),
                            ('rms_current_min', 'Imin rms /A',
                                224, 20, FONT_SIZE, 28, 10, 3, 1),
                            ('mean_power_max', 'Pmax /W',
                                224, 20, FONT_SIZE, 28, 0, 2, 1),
                            ('mean_power_min', 'Pmin /W',
                                224, 20, FONT_SIZE, 28, 10, 2, 1),
                            ('mean_volt_ampere_reactive_max', 'RPmax /VAR',
                                224, 20, FONT_SIZE, 28, 0, 2, 1),
                            ('mean_volt_ampere_reactive_min', 'RPmin /VAR',
                                224, 20, FONT_SIZE, 28, 10, 2, 1),
                            ('mean_volt_ampere_max', 'APmax /VA',
                                224, 20, FONT_SIZE, 28, 0, 2, 1),
                            ('mean_volt_ampere_min', 'APmin /VA',
                                224, 20, FONT_SIZE, 28, 10, 2, 1) ]

        column_3        = [ ('watt_hour', 'Energy /Wh',
                                224, 20, FONT_SIZE, 28, 0, 3, 1),
                            ('volt_ampere_reactive_hour', 'Reactive energy /VARh',
                                224, 20, FONT_SIZE, 28, 0, 3, 1),
                            ('volt_ampere_hour', 'Apparent energy /VAh',
                                224, 20, FONT_SIZE, 28, 0, 3, 1),
                            ('hours', 'Accumulation time /hr',
                                224, 20, FONT_SIZE, 28, 40, 3, 1),
                            ('power_factor', 'Power factor /1',
                                224, 20, FONT_SIZE, 28, 0, 2, 1),
                            ('crest_factor_current', 'Crest factor /1',
                                224, 20, FONT_SIZE, 28, 0, 2, 1),
                            ('frequency', 'Frequency /Hz',
                                224, 20, FONT_SIZE, 28, 0, 2, 1),
                            ('rms_leakage_current', 'Earth leakage /mA',
                                224, 20, FONT_SIZE, 28, 0, 3, 1000),
                            ('total_harmonic_distortion_voltage_percentage', 'THD(v) /%',
                                224, 20, FONT_SIZE, 28, 0, 2, 1),
                            ('total_harmonic_distortion_current_percentage', 'THD(i) /%',
                                224, 20, FONT_SIZE, 28, 0, 2, 1) ]

        tp_texts = []
        label_h = 18
        label_font_size = FONT_SIZE
        for column, x in zip([column_1, column_2, column_3], [0, 200, 440]):
            y = 0
            for item in column:
                key, label, w, value_h, value_font_size, pad_size, gap_h, decimals, display_scaling = item
                # create the label
                if x==0:
                    pad = 36
                else:
                    pad = 28
                tp_label = thorpy.Text(label.rjust(pad))
                tp_label.set_size((w,label_h))
                tp_label.set_font_size(label_font_size)
                tp_label.set_font_color(WHITE)
                tp_label.set_topleft(x,y)
                tp_texts.append(tp_label)
                y = y + label_h
                # and then initial text for the value
                tp_value = thorpy.Text('999.999'.rjust(pad_size))
                tp_value.set_size((w,value_h))
                tp_value.set_font_size(value_font_size)
                tp_value.set_font_color(YELLOW)
                tp_value.set_topleft(x,y)
                tp_texts.append(tp_value)
                y = y + value_h + gap_h
                # add lookup of multimeter value object, with getter lambda function, required text padding,
                # keyed by analysis key
                self.value_updater.append((tp_value, getter_lambda, pad_size, decimals, display_scaling))

        multimeter_column_1 = thorpy.Group(tp_texts[:10], mode=None)
        multimeter_column_2 = thorpy.Group(tp_texts[10:30], mode=None)
        multimeter_column_3 = thorpy.Group(tp_texts[30:], mode=None)
        multimeter_display = thorpy.Group([multimeter_column_1, multimeter_column_2, multimeter_column_3],
                                   mode='h', gap=0, margins=(0,0))
        multimeter_display.set_topleft(*METER_POSITION)
        return multimeter_display
