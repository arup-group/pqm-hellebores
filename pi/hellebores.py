#!/usr/bin/env python3

# figlet
#  _          _ _      _                                       
# | |__   ___| | | ___| |__   ___  _ __ ___  ___   _ __  _   _ 
# | '_ \ / _ \ | |/ _ \ '_ \ / _ \| '__/ _ \/ __| | '_ \| | | |
# | | | |  __/ | |  __/ |_) | (_) | | |  __/\__ \_| |_) | |_| |
# |_| |_|\___|_|_|\___|_.__/ \___/|_|  \___||___(_) .__/ \__, |
#                                                 |_|    |___/ 
#

import thorpy
import pygame
import time
import sys
import os
import select
import settings



      
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
MAGENTA = (255, 0, 255)
CYAN = (0, 255, 255)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DARK_GREY = (30, 30, 30)
GREY = (75, 75, 75)
LIGHT_GREY = (100, 100, 100)
VERY_LIGHT_GREY = (150, 150, 150)
PI_SCREEN_SIZE = (800,480)
SCOPE_BOX_SIZE = (700,480)
CONTROLS_BOX_SIZE = (100,480)        # main buttons and status texts
CONTROLS_BOX_POSITION = (800,0)      # top right corner
SETTINGS_BOX_SIZE = (500,400)        # 'dialog' boxes
SETTINGS_BOX_POSITION = (690,100)    # top right corner
BUTTON_SIZE = (90,50) 
BUTTON_WIDE_SIZE = (180,50) 
TEXT_SIZE = (90,16)
TEXT_WIDE_SIZE = (120,16)
FONT = 'dejavusansmono'
FONT_SIZE = 14
SAMPLE_BUFFER_SIZE = 100 

# Default pygame font: freesansbold
# Ubuntu monospaced fonts:
# dejavusansmono
# ubuntumono
# bitstreamverasansmono
# nimbusmonops
# notosansmono
# notomono
 
# button enumerations
B_RUNSTOP     = 0
B_MODE        = 1
B_HORIZONTAL  = 2
B_VERTICAL    = 3
B_TRIGGER     = 4
B_OPTIONS     = 5


# text message cell enumerations
T_RUNSTOP     = 0
T_WFS         = 1
T_TIMEDIV     = 2
T_VOLTSDIV    = 3
T_AMPSDIV     = 4
T_WATTSDIV    = 5
T_LEAKDIV     = 6


class Range_controller:
    ranges = []
    range_selector = 0
    maximum_range = 1

    def __init__(self, required_ranges, initial_index):
        self.ranges = required_ranges
        self.range_selector = initial_index
        self.maximum_range = len(required_ranges) - 1

    def get_index(self):
        return self.range_selector

    def get_value(self):
        return self.ranges[self.range_selector]

    def change_range(self, offset):
        if offset == 1:
            self.range_selector = min(self.maximum_range, self.range_selector+1)
        elif offset == -1:
            self.range_selector = max(0, self.range_selector-1)
        else:
            print(
                "Range_controller.change_range: can only change range by +1 or -1.", 
                file=sys.stderr) 


def create_datetime():
    #####
    # Datetime display
    #####
    text_datetime = thorpy.Text(time.ctime())
    text_datetime.set_font_color(WHITE)
    return [ text_datetime ]

def configure_button_decorations(button, callback_function):
    button.set_bck_color(VERY_LIGHT_GREY, 'normal')
    button.set_bck_color(VERY_LIGHT_GREY, 'hover')
    button.set_font_color(WHITE)
    button.at_unclick = callback_function

def configure_switch_button(size, value, callback_function):
    button = thorpy.SwitchButton(value, size, drag_size=(size[0]//3, size[1]//2))
    configure_button_decorations(button, callback_function)
    return button

def configure_arrow_button(size, direction, callback_function):
    button = thorpy.ArrowButton(direction, size) 
    configure_button_decorations(button, callback_function)
    return button
 
def configure_button(size, text, callback_function):
    button = thorpy.Button(text) 
    configure_button_decorations(button, callback_function)
    button.set_size(size)
    return button
    
def create_mode():
    """Mode controls dialog"""
    button_waveform = configure_button(BUTTON_WIDE_SIZE, 'Waveform', lambda: ui.set_updater('waveform'))
    button_multimeter = configure_button(BUTTON_WIDE_SIZE, 'Multimeter', lambda: ui.set_updater('multimeter'))
    button_voltage_harmonics = configure_button(
        BUTTON_WIDE_SIZE, 'Voltage harmonics', voltage_harmonics_reaction)
    button_current_harmonics = configure_button(
        BUTTON_WIDE_SIZE, 'Current harmonics', current_harmonics_reaction)

    mode = thorpy.TitleBox(
        text='Mode', children=[
            thorpy.Group(elements=[
                button_waveform,
                button_multimeter,
                button_voltage_harmonics,
                button_current_harmonics
                ],
                mode='v')
            ])
    for e in mode.get_all_descendants():
        e.hand_cursor = False    
    return mode

def create_current_range():
    """Range controls dialog"""
    button_done = configure_button(BUTTON_SIZE, 'Done', lambda: ui.set_updater('back'))
    button_full = configure_button(BUTTON_WIDE_SIZE, 'Full', lambda: ui.set_current_range('full'))
    button_low = configure_button(BUTTON_WIDE_SIZE, 'Low', lambda: ui.set_current_range('low'))

    current_range = thorpy.TitleBox(
        text='Current range', children=[
            thorpy.Group(elements=[
                button_done,
                button_full,
                button_low
                ],
                mode='v')
            ])
    for e in current_range.get_all_descendants():
        e.hand_cursor = False    
    return current_range

def create_horizontal():
    """Horizontal controls dialog"""
    def update_time_range(times, offset):
        times.change_range(offset)
        time_display.set_text(f'{times.get_value()} ms/div',
            adapt_parent=False)
        st.time_display_index = times.get_index()
        st.send_to_all()

    button_done = configure_button(BUTTON_SIZE, 'Done', lambda: ui.set_updater('back'))

    times = Range_controller(st.time_display_ranges, st.time_display_index)
    time_display = thorpy.Text(f'{times.get_value()} ms/div') 
    time_display.set_size(TEXT_WIDE_SIZE)
    time_down = configure_arrow_button(
        BUTTON_SIZE, 'left',
        lambda: update_time_range(times, -1))
    time_up = configure_arrow_button(
        BUTTON_SIZE, 'right', 
        lambda: update_time_range(times, 1))

    horizontal = thorpy.TitleBox(
        text='Horizontal', children=[
            button_done,
            thorpy.Group(
                elements=[
                    time_display,
                    time_down,
                    time_up
                    ],
                mode='h')
            ])
    for e in horizontal.get_all_descendants():
        e.hand_cursor = False    
    return horizontal
 

def create_vertical():
    """Vertical controls dialog"""
    def update_voltage_range(voltages, offset):
        voltages.change_range(offset)
        voltage_display.set_text(
            f'{voltages.get_value()} V/div', adapt_parent=False)
        st.voltage_display_index = voltages.get_index()
        st.send_to_all()

    def update_current_range(currents, offset):
        currents.change_range(offset)
        current_display.set_text(
            f'{currents.get_value()} A/div', adapt_parent=False)
        st.current_display_index = currents.get_index()
        st.send_to_all() 

    def update_power_range(powers, offset):
        powers.change_range(offset)
        power_display.set_text(
            f'{powers.get_value()} W/div', adapt_parent=False)
        st.power_display_index = powers.get_index()
        st.send_to_all()

    def update_leakage_current_range(leakage_currents, offset):
        leakage_currents.change_range(offset)
        leakage_current_display.set_text(
            f'{leakage_currents.get_value()*1000.0} mA/div', adapt_parent=False)
        st.earth_leakage_current_display_index = leakage_currents.get_index()
        st.send_to_all()

    def flip_display_switch(channel, switch_status):
        if channel == 'voltage':
            st.voltage_display_status = switch_status
        elif channel == 'current':
            st.current_display_status = switch_status
        elif channel == 'power':
            st.power_display_status = switch_status
        elif channel == 'leakage':
            st.earth_leakage_current_display_status = switch_status
        else:
            print(
                'hellebores.py: flip_display_switch() channel not recognised.',
                file=sys.stderr)
        st.send_to_all()

    button_done = configure_button(BUTTON_SIZE, 'Done', lambda: ui.set_updater('back'))

    voltages = Range_controller(
        st.voltage_display_ranges, st.voltage_display_index)
    voltage_onoff = configure_switch_button(
        BUTTON_SIZE,st.voltage_display_status,
        lambda: flip_display_switch('voltage', voltage_onoff.value))
    voltage_display = thorpy.Text(f'{voltages.get_value()} V/div') 
    voltage_display.set_size(TEXT_WIDE_SIZE)
    voltage_down = configure_arrow_button(
        BUTTON_SIZE, 'up', lambda: update_voltage_range(voltages, -1))
    voltage_up = configure_arrow_button(
        BUTTON_SIZE, 'down', lambda: update_voltage_range(voltages, 1))

    currents = Range_controller(
        st.current_display_ranges, st.current_display_index)
    current_onoff = configure_switch_button(
        BUTTON_SIZE, st.current_display_status,
        lambda: flip_display_switch('current', current_onoff.value))
    current_display = thorpy.Text(f'{currents.get_value()} A/div')
    current_display.set_size(TEXT_WIDE_SIZE)
    current_down = configure_arrow_button(
        BUTTON_SIZE, 'up', lambda: update_current_range(currents, -1))
    current_up = configure_arrow_button(
        BUTTON_SIZE, 'down', lambda: update_current_range(currents, 1))
    
    powers = Range_controller(
        st.power_display_ranges, st.power_display_index)
    power_onoff = configure_switch_button(
        BUTTON_SIZE, st.power_display_status,
        lambda: flip_display_switch('power', power_onoff.value))
    power_display = thorpy.Text(f'{powers.get_value()} W/div')
    power_display.set_size(TEXT_WIDE_SIZE)
    power_down = configure_arrow_button(
        BUTTON_SIZE, 'up', lambda: update_power_range(powers, -1))
    power_up = configure_arrow_button(
        BUTTON_SIZE, 'down',lambda: update_power_range(powers, 1))
  
    leakage_currents = Range_controller(
        st.earth_leakage_current_display_ranges,
        st.earth_leakage_current_display_index)
    leakage_current_onoff = configure_switch_button(
        BUTTON_SIZE,
        st.earth_leakage_current_display_status,
        lambda: flip_display_switch('leakage', leakage_current_onoff.value))
    leakage_current_display = thorpy.Text(f'{leakage_currents.get_value()*1000.0} mA/div')
    leakage_current_display.set_size(TEXT_WIDE_SIZE)
    leakage_current_down = configure_arrow_button(
        BUTTON_SIZE, 'up',
        lambda: update_leakage_current_range(leakage_currents, -1))
    leakage_current_up = configure_arrow_button(
        BUTTON_SIZE, 'down',
        lambda: update_leakage_current_range(leakage_currents, 1))
 
    vertical = thorpy.TitleBox(
        text='Vertical',
        children=[
            button_done,
            thorpy.Group(
                elements=[
                    voltage_display,
                    voltage_down,
                    voltage_up,
                    voltage_onoff
                    ],
                mode='h'),
            thorpy.Group(
                elements=[
                    current_display,
                    current_down,
                    current_up,
                    current_onoff
                    ],
                mode='h'),
            thorpy.Group(
                elements=[
                    power_display,
                    power_down,
                    power_up,
                    power_onoff
                    ],
                mode='h'),
            thorpy.Group(
                elements=[
                    leakage_current_display,
                    leakage_current_down,
                    leakage_current_up,
                    leakage_current_onoff
                    ],
                mode='h')
            ])
    for e in vertical.get_all_descendants():
        e.hand_cursor = False    
    return vertical


def create_trigger(waveform):
    """Trigger controls dialog"""
    #####
    # Trigger controls
    #####
    # in freerun mode, trigger source is set to -1
    # in sync mode, trigger source is set to ch0 and level to 0.0 (Volts), rising slope
    # in inrush single mode, trigger source is set to ch3 and level to 0.1 (Watts), rising slope
    # inrush mode causes waveform update to stop on first trigger.
    def update_trigger_position(position, status):
        st.time_axis_pre_trigger_divisions = position
        waveform.draw_background()
        update_trigger_status(status)
        st.send_to_all()

    def update_trigger_slope(slope, status):
        st.trigger_slope = slope
        update_trigger_status(status)
        st.send_to_all()

    def update_trigger_mode(mode, status):
        if mode == 'freerun':
            st.trigger_channel = -1
            waveform.draw_background()
        elif mode == 'sync':
            st.trigger_channel = 0
            st.trigger_level = 0.0
        elif mode == 'inrush':
            st.trigger_channel = 2
            st.trigger_level = 0.1
        else:
            print(
                'hellebores.py: update_trigger_mode(), invalid condition requested.',
                sys.stderr)
        st.trigger_mode = mode
        waveform.draw_background()
        update_trigger_status(status)
        st.send_to_all()

    def update_trigger_status(status):
        if st.trigger_mode == 'freerun':
            status.set_text(
                f'Free-run: the trigger is disabled.',
                adapt_parent=False)
        elif st.trigger_mode == 'sync':
            status.set_text(
                f'Sync: the trigger is enabled to find the {st.trigger_slope}' \
                ' edge of the voltage signal at magitude 0.0V.',
                adapt_parent=False)
        elif st.trigger_mode == 'inrush':
            status.set_text(
                f'Inrush: the trigger is enabled for single-shot current'
                'detection, magnitude +/- {st.trigger_level}A. Press Run/Stop to reset.',
                adapt_parent=False)
        else:
            print(
                'hellebores.py: update_trigger_status(), '
                'invalid trigger_condition requested.',
                sys.stderr)
        status.set_max_text_width(280)

    # fill with temporary text so that the correct size is allocated for the enclosing box
    text_trigger_status = thorpy.Text(
        'Lorem ipsum dolor sit amet, consectetur adipiscing elit, '
        'sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.')
    text_trigger_status.set_max_text_width(280)
    button_done = configure_button(
        BUTTON_SIZE, 'Done', lambda: ui.set_updater('back'))
    button_freerun = configure_button(
        BUTTON_SIZE, 'Free-run',
        lambda: update_trigger_mode('freerun', text_trigger_status))
    button_sync = configure_button(
        BUTTON_SIZE, 'Sync',
        lambda: update_trigger_mode('sync', text_trigger_status))
    button_inrush = configure_button(
        BUTTON_SIZE, 'Inrush',
        lambda: update_trigger_mode('inrush', text_trigger_status))
    button_left = configure_button(
        BUTTON_SIZE, 'Left',
        lambda: update_trigger_position(1, text_trigger_status))
    button_centre = configure_button(
        BUTTON_SIZE, 'Centre',
        lambda: update_trigger_position(st.time_axis_divisions // 2, text_trigger_status))
    button_right = configure_button(
        BUTTON_SIZE, 'Right',
        lambda: update_trigger_position(st.time_axis_divisions - 1, text_trigger_status))
    button_rising = configure_button(
        BUTTON_SIZE, 'Rising',
        lambda: update_trigger_slope('rising', text_trigger_status))
    button_falling = configure_button(
        BUTTON_SIZE, 'Falling',
        lambda: update_trigger_slope('falling', text_trigger_status))
    trigger = thorpy.TitleBox(
        text='Trigger',
        children=[
            button_done,
            thorpy.Group(
                elements=[
                    button_freerun,
                    button_sync,
                    button_inrush
                    ], mode='h'),
            thorpy.Group(
                elements=[
                    button_left,
                    button_centre,
                    button_right
                    ], mode='h'),
            thorpy.Group(
                elements=[
                    button_rising,
                    button_falling
                    ], mode='h'),
            text_trigger_status]) 
    for e in trigger.get_all_descendants():
        e.hand_cursor = False    
    # put the text status in after forming the box,
    # so that the box dimensions are not affected by the text.
    update_trigger_status(text_trigger_status)
    return trigger

def create_options(waveform):
    """Option controls dialog"""
    def about_box():
        alert = thorpy.Alert(
            title="hellebores.py",
            text="Power quality meter, v0.1",
            ok_text="Ok, I've read")
        alert.set_draggable()
        alert.cannot_drag_outside = True
        for e in alert.get_all_descendants():
           if isinstance(e, thorpy.elements.Button):
               e.set_bck_color(VERY_LIGHT_GREY, 'normal')
               e.set_bck_color(VERY_LIGHT_GREY, 'hover')
               e.set_font_color(WHITE)
           e.hand_cursor = False
        alert.launch_nonblocking()

    button_done = configure_button(
        BUTTON_SIZE, 'Done', lambda: ui.set_updater('back'))
    button_dots = configure_button(
        BUTTON_SIZE, 'Dots', lambda: waveform.plot_mode('dots'))
    button_lines = configure_button(
        BUTTON_SIZE, 'Lines', lambda: waveform.plot_mode('lines'))
    button_about = configure_button(
        BUTTON_SIZE, 'About...',about_box)
    button_software_update = configure_button(
        BUTTON_SIZE, 'Software\nupdate', lambda: exit_application('software_update'))
    button_shutdown = configure_button(
        BUTTON_SIZE, 'SHUTDOWN', lambda: exit_application('shutdown'))
    button_restart = configure_button(
        BUTTON_SIZE, 'RESTART', lambda: exit_application('restart'))
    button_quit = configure_button(
        BUTTON_SIZE, 'QUIT', lambda: exit_application('quit'))

    options = thorpy.TitleBox(
        text='Options',
        children=[
            button_done,
            thorpy.Group(
                elements=[
                    button_dots,
                    button_lines
                    ], mode='h'),
            thorpy.Group(
                elements=[
                    button_about,
                    button_software_update,
                    ], mode='h'),
            thorpy.Group(
                elements=[
                    button_restart,
                    button_shutdown,
                    button_quit
                    ], mode='h')
            ])
    for e in options.get_all_descendants():
        e.hand_cursor = False    
    return options



# More UI is needed for the following:
#
# Measurements-1 (summary)
# Measurements-2 (harmonics)
# Wifi setting
# Shell prompt
# Software update, rollback and Raspberry Pi OS update
# About (including software version, kernel version, uuid of Pi and Pico)
# Exit to desktop

# The instance of this class will hold all the user interface states or 'groups'
# that can be displayed together with the currently active selection
class UI_groups:
    elements = {}
    updater = None
    mode = 'waveform'
    current_range = 'full'
    instruments = {}

    def __init__(self, waveform, multimeter):
        self.instruments['waveform'] = waveform
        self.instruments['multimeter'] = multimeter

        self.elements['datetime'] = create_datetime()[0]
        self.elements['datetime'].set_topleft(0,0)

        # waveform group
        self.elements['waveform'] = waveform.create_waveform_controls()
        self.elements['waveform'].set_size(CONTROLS_BOX_SIZE)
        self.elements['waveform'].set_topright(*CONTROLS_BOX_POSITION)

        # multi-meter group
        self.elements['multimeter'] = multimeter.create_multimeter_controls()
        self.elements['multimeter'].set_size(CONTROLS_BOX_SIZE)
        self.elements['multimeter'].set_topright(*CONTROLS_BOX_POSITION)

        # voltage harmonic group
        #ui_voltage_harmonic = create_voltage_harmonic_controls(texts)
        #ui_voltage_harmonic.set_size(CONTROLS_BOX_SIZE)
        #ui_voltage_harmonic.set_topright(*CONTROLS_BOX_POSITION)
        #self.elements['voltage_harmonic'] = ui_voltage_harmonic

        # current harmonic group
        #ui_current_harmonic = create_current_harmonic_controls(texts)
        #ui_current_harmonic.set_size(CONTROLS_BOX_SIZE)
        #ui_current_harmonic.set_topright(*CONTROLS_BOX_POSITION)
        #self.elements['current_harmonic'] = ui_current_harmonic

        # control groups that overlay the main group when adjusting settings
        self.elements['mode'] = create_mode()
        self.elements['current_range'] = create_current_range()
        self.elements['vertical'] = create_vertical()
        self.elements['horizontal'] = create_horizontal()
        self.elements['trigger'] = create_trigger(waveform)
        self.elements['options'] = create_options(waveform)

        for k in ['mode', 'current_range', 'vertical', 'horizontal', 'trigger', 'options']:
            self.elements[k].set_topright(*SETTINGS_BOX_POSITION)

    def set_current_range(self, required_range):
        self.current_range = required_range

    # NEED TO DISPATCH TO OBJECT
    def refresh(self, buffer, screen):
        if self.mode == 'waveform':
            waveform.plot(buffer, screen) 
        elif self.mode == 'multimeter':
        else:
            print('UI_groups.refresh() not implemented in this mode.', file=sys.stderr)

    def draw_texts(self):
        if self.mode == 'waveform':

    def set_updater(self, elements_group):
        # for 'waveform', 'multimeter', 'voltage_harmonic', 'current_harmonic',
        # we retain the group in a 'mode' variable for recall after menu selections.
        try:
            if elements_group in ['waveform', 'multimeter', 'voltage_harmonic', 'current_harmonic']:
                # if we picked a different display mode, store it in 'self.mode'.
                self.mode = elements_group
                elements = [ 
                    self.elements[self.mode],
                    self.elements['datetime']
                    ]
            elif elements_group == 'back':
                # if we picked 'back', then just use the pre-existing mode
                elements = [
                    self.elements[self.mode],
                    self.elements['datetime']
                    ]
            else:
                # otherwise, use the pre-existing mode and add the selected overlay
                # elements to it.
                elements = [
                    self.elements[self.mode],
                    self.elements[elements_group],
                    self.elements['datetime']
                    ]
            self.updater = thorpy.Group(elements=elements, mode=None).get_updater()
        except:
            print(
                'UI_groups.set_updater(): group parameter not recognised.\n',
                file=sys.stderr)

    def get_updater(self):
        return self.updater 

    def get_element(self, element):
        return self.elements[element]


def start_stop_reaction():
    global capturing
    capturing = not capturing

def voltage_harmonics_reaction():
    pass

def current_harmonics_reaction():
    pass


class Waveform:
    # array of thorpy text objects
    texts = []
    waveform_background = None
    waveform_colours = [ GREEN, YELLOW, MAGENTA, CYAN ]
    text_colours = [BLACK, WHITE, WHITE] + waveform_colours

    def set_text_colours(self):
        # the boolean filter allows us to temporarily grey out lines
        # that are currently inactive/switched off
        colour_filter = [
            True,
            True,
            True,
            st.voltage_display_status,
            st.current_display_status,
            st.power_display_status,
            st.earth_leakage_current_display_status,
            ]
        colours = [ c if p == True else DARK_GREY for p, c in zip(colour_filter, self.text_colours) ]
        for i in range(len(self.texts)):
            self.texts[i].set_font_color(colours[i])

    def __init__(self, wfs):
        self.wfs = wfs              # make a local note of the wfs object
        for s in range(7):
            t = thorpy.Text('')
            t.set_size(TEXT_SIZE)
            self.texts.append(t)
        self.draw_texts()
        self.draw_background()
        # initial set up is lines
        self.plot_mode('lines')

    def set_text(self, item, value):
        self.texts[item].set_text(value)

    def draw_texts(self):
        self.set_text_colours()
        if capturing:
            self.texts[T_RUNSTOP].set_bck_color(GREEN)
            self.texts[T_RUNSTOP].set_text('Running', adapt_parent=False)
        else:
            self.texts[T_RUNSTOP].set_bck_color(RED)
            self.texts[T_RUNSTOP].set_text('Stopped', adapt_parent=False)
        self.texts[T_WFS].set_text(f'{self.wfs.get()} wfm/s', adapt_parent=False)
        self.texts[T_TIMEDIV].set_text(
            f'{st.time_display_ranges[st.time_display_index]} ms/',
            adapt_parent=False)
        self.texts[T_VOLTSDIV].set_text(
            f'{st.voltage_display_ranges[st.voltage_display_index]} V/',
            adapt_parent=False)
        self.texts[T_AMPSDIV].set_text(
            f'{st.current_display_ranges[st.current_display_index]} A/',
            adapt_parent=False)
        self.texts[T_WATTSDIV].set_text(
            f'{st.power_display_ranges[st.power_display_index]} W/',
            adapt_parent=False)
        elv = (st.earth_leakage_current_display_ranges
               [st.earth_leakage_current_display_index] * 1000)
        self.texts[T_LEAKDIV].set_text(f'{elv} mA/', adapt_parent=False)


    def draw_background(self):
        xmax = SCOPE_BOX_SIZE[0] - 1
        ymax = SCOPE_BOX_SIZE[1] - 1

        # empty background
        self.waveform_background = pygame.Surface(SCOPE_BOX_SIZE)
        self.waveform_background.fill(GREY)

        # draw the graticule lines
        for dx in range(1, st.time_axis_divisions):
            x = st.horizontal_pixels_per_division * dx
            # mark the trigger position (t=0) with an emphasized line
            if (dx == st.time_axis_pre_trigger_divisions) and (st.trigger_channel != -1):
                lc = WHITE
            else:
                lc = LIGHT_GREY
            pygame.draw.line(self.waveform_background, lc, (x, 0), (x, ymax), 1)
        for dy in range(1, st.vertical_axis_divisions):
            y = st.vertical_pixels_per_division * dy
            # mark the central position (v, i = 0) with an emphasized line
            if dy == st.vertical_axis_divisions // 2:
                lc = WHITE
            else:
                lc = LIGHT_GREY
            pygame.draw.line(self.waveform_background, lc, (0, y), (xmax, y), 1)


    # The plot function that will be used is configurable
    # plot_fn is set to point to either _plot_dots() or _plot_lines()
    def _plot_dots(self, screen, buffer, display_status):
        pa = pygame.PixelArray(screen)
        for i in range(len(buffer)):
            if display_status[i] == True:
                for pixel in buffer[i]:
                    pa[pixel[0], pixel[1]] = self.waveform_colours[i]
        pa.close()

    def _plot_lines(self, screen, buffer, display_status):
        for i in range(len(buffer)):
            if display_status[i] == True:
                pygame.draw.lines(screen, self.waveform_colours[i], False, buffer[i], 2)
    
    def plot(self, buffer, screen):
        # can handle up to six plots...
        screen.blit(self.waveform_background, (0,0))
        linedata = buffer.get_buffer()
        display_status = [
            st.voltage_display_status,
            st.current_display_status,
            st.power_display_status,
            st.earth_leakage_current_display_status
            ]
        try:
            self.plot_fn(screen, linedata, display_status)
        except (IndexError, ValueError):
            # the pygame.draw.lines will throw an exception if there are not at
            # least two points in each line - (sounds reasonable)
            print(
                f'exception in hellebores.py: plot_fn(). linedata is: {linedata}.\n',
                file=sys.stderr)

    def plot_mode(self, mode):
        if mode == 'dots':
            self.plot_fn = self._plot_dots
        elif mode == 'lines':
            self.plot_fn = self._plot_lines

    def create_waveform_controls(self):
        """Waveform controls, on right of screen"""
        button_setup = [
            ('Run/Stop', start_stop_reaction),
            ('Mode', lambda: ui.set_updater('mode')), 
            ('Horizontal', lambda: ui.set_updater('horizontal')), 
            ('Vertical', lambda: ui.set_updater('vertical')), 
            ('Trigger', lambda: ui.set_updater('trigger')), 
            ('Options', lambda: ui.set_updater('options'))
            ]
        buttons = [ configure_button(BUTTON_SIZE, bt, bf) for bt, bf in button_setup ]
        waveform = thorpy.Box([ *self.texts[0:2], *buttons, *self.texts[2:] ])
        waveform.set_bck_color(LIGHT_GREY)
        for e in waveform.get_all_descendants():
            e.hand_cursor = False    
        return waveform


class Multimeter:
    # array of thorpy text objects
    texts = []
    multimeter_background = None
    multimeter_colours = [ GREEN, YELLOW, MAGENTA, CYAN ]
    text_colours = [BLACK, WHITE, WHITE] + multimeter_colours
    current_range = 'full'

    def set_text_colours(self):
        # the boolean filter allows us to temporarily grey out lines
        # that are currently inactive/switched off
        colour_filter = [
            True,
            True,
            True,
            st.voltage_display_status,
            st.current_display_status,
            st.power_display_status,
            st.earth_leakage_current_display_status,
            ]
        colours = [ c if p == True else DARK_GREY for p, c in zip(colour_filter, self.text_colours) ]
        for i in range(len(self.texts)):
            self.texts[i].set_font_color(colours[i])

    def __init__(self):
        for s in range(7):
            t = thorpy.Text('')
            t.set_size(TEXT_SIZE)
            self.texts.append(t)
        self.draw_texts()
        self.draw_background()

    def set_text(self, item, value):
        self.texts[item].set_text(value)

    def draw_texts(self):
        self.set_text_colours()
        if capturing:
            self.texts[T_RUNSTOP].set_bck_color(GREEN)
            self.texts[T_RUNSTOP].set_text('Running', adapt_parent=False)
        else:
            self.texts[T_RUNSTOP].set_bck_color(RED)
            self.texts[T_RUNSTOP].set_text('Stopped', adapt_parent=False)
        self.texts[T_WFS].set_text(f'n/a wfm/s', adapt_parent=False)
        self.texts[T_TIMEDIV].set_text(
            f'{st.time_display_ranges[st.time_display_index]} ms/',
            adapt_parent=False)
        self.texts[T_VOLTSDIV].set_text(
            f'{st.voltage_display_ranges[st.voltage_display_index]} V/',
            adapt_parent=False)
        self.texts[T_AMPSDIV].set_text(
            f'{st.current_display_ranges[st.current_display_index]} A/',
            adapt_parent=False)
        self.texts[T_WATTSDIV].set_text(
            f'{st.power_display_ranges[st.power_display_index]} W/',
            adapt_parent=False)
        elv = (st.earth_leakage_current_display_ranges
               [st.earth_leakage_current_display_index] * 1000)
        self.texts[T_LEAKDIV].set_text(f'{elv} mA/', adapt_parent=False)


    def draw_background(self):
        xmax = SCOPE_BOX_SIZE[0] - 1
        ymax = SCOPE_BOX_SIZE[1] - 1

        # empty background
        self.multimeter_background = pygame.Surface(SCOPE_BOX_SIZE)
        self.multimeter_background.fill(GREY)


    def create_multimeter_controls(self):
        """Multimeter controls, on right of screen"""
        button_setup = [
            ('Run/Stop', start_stop_reaction),
            ('Mode', lambda: ui.set_updater('mode')), 
            ('Range', lambda: ui.set_updater('current_range')), 
            ('Options', lambda: ui.set_updater('options'))
            ]
        buttons = [ configure_button(BUTTON_SIZE, bt, bf) for bt, bf in button_setup ]
        multimeter_controls = thorpy.Box([ *self.texts[0:2], *buttons, *self.texts[2:] ])
        multimeter_controls.set_bck_color(LIGHT_GREY)
        for e in multimeter_controls.get_all_descendants():
            e.hand_cursor = False    
        return multimeter_controls


class WFS_Counter:

    def __init__(self):
        self.wfs          = 0    # last computed wfs
        self.counter      = 0    # number of waveforms since last posting
        self.update_time  = 0    # time when the wfs/s was lasted posted to screen

    # called whenever we update the waveform on screen 
    def increment(self):
        self.counter = self.counter + 1

    def time_to_update(self):
        # time now 
        tn = time.time()
        # if the time has increased by at least 1.0 second, update the wfm/s text
        elapsed = tn - self.update_time
        if elapsed >= 1.0:
            self.wfs = int(self.counter/elapsed)
            self.update_time = tn
            self.counter = 0
            return True
        else:
            return False
 
    def get(self):
        return self.wfs
        

def get_screen_hardware_size():
    i = pygame.display.Info()
    return i.current_w, i.current_h


# the version of is_data_available that we will use is determined
# once at runtime
if os.name == 'posix':
    # f is file object to test for reading, t is time in seconds
    # wait at most 't' seconds for new data to appear
    # element 0 of tuple will be an empty list unless there is data ready to read
    is_data_available = lambda f, t: select.select( [f], [], [], t)[0] != []
else:
    # unfortunately this test isn't easy to implement on windows
    # so we return a default 'True' response
    is_data_available = lambda f, t: True
 

class Sample_Buffer:
    # working points buffer for four lines
    ps = [ [],[],[],[] ] 

    # sample buffer history
    # future extension is to use this buffer for electrical event history
    # (eg triggered by power fluctuation etc)
    sample_buffer_history = [[] for i in range(SAMPLE_BUFFER_SIZE+1)]
    xp = -1                 # tracks previous 'x coordinate'

    def end_frame(self, capturing, wfs):
        if capturing:
            self.sample_buffer_history[SAMPLE_BUFFER_SIZE] = self.ps
            wfs.increment()
        # reset the working buffer
        self.ps = [ [],[],[],[] ]

    def add_sample(self, sample):
        self.ps[0].append((sample[0], sample[1]))
        self.ps[1].append((sample[0], sample[2]))
        self.ps[2].append((sample[0], sample[3]))
        self.ps[3].append((sample[0], sample[4]))

    def load_buffer(self, f, capturing, wfs):
        # the loop will exit if:
        # (a) there is no data currently waiting to be read, 
        # (b) negative x coordinate indicates last sample of current frame
        # (c) the x coordinate 'goes backwards' indicating a new frame has started
        # (d) the line is empty, can't be split() or any other kind of read error
        # (e) more than 1000 samples have been read (this keeps the UI responsive)
        # returns 'True' if we have completed a new frame
        sample_counter = 0
        while is_data_available(f, 0.05) and sample_counter < 1000: 
            try:
                ws = f.readline().split()
                sample = [ int(w) for w in ws[:5] ]
                if ws[-1] == '*END*':
                    # add current sample then end the frame
                    self.add_sample(sample)
                    self.end_frame(capturing, wfs)
                    self.xp = -1
                    return True
                elif sample[0] < self.xp:
                    # x coordinate has reset to indicate start of new frame...
                    # end the frame before adding current sample to a new one
                    self.end_frame(capturing, wfs)    
                    self.add_sample(sample)
                    self.xp = -1
                    return True
                else:
                    # an ordinary, non-special, sample
                    self.add_sample(sample)
                self.xp = sample[0]
                sample_counter = sample_counter + 1
            except:
                break   # break if we have any type of error with the input data
        return False

    def save_buffer(self):
        self.sample_buffer_history = self.sample_buffer_history[1:]
        self.sample_buffer_history.append('')

    def get_buffer(self, index = SAMPLE_BUFFER_SIZE):
        if (index < 0) or (index > SAMPLE_BUFFER_SIZE):
            index = SAMPLE_BUFFER_SIZE
        return self.sample_buffer_history[index]

    def __init__(self):
        pass


def exit_application(option='quit'):
    exit_codes = { 'quit': 0, 'restart': 2, 'software_update': 3, 'shutdown': 4, }
    pygame.quit()
    sys.exit(exit_codes[option])


def main():
    global capturing, ui, st

    # initialise pygame
    pygame.init()
    pygame.display.set_caption('pqm-hellebores')

    # fullscreen on Pi, but not on laptop
    # also make the mouse pointer invisible on Pi, as we will use the touchscreen
    # we can't make the pointer inactive using the pygame flags because we need it working
    # to return correct coordinates from the touchscreen
    if get_screen_hardware_size() == PI_SCREEN_SIZE:
        screen    = pygame.display.set_mode(PI_SCREEN_SIZE, flags=pygame.FULLSCREEN)
        hide_mouse_pointer = True
    else:
        screen    = pygame.display.set_mode(PI_SCREEN_SIZE)
        hide_mouse_pointer = False

    # initialise thorpy
    thorpy.set_default_font(FONT, FONT_SIZE)
    thorpy.init(screen, thorpy.theme_simple)

    # load configuration settings from settings.json into a settings object 'st'.
    # the list of 'other programs' is used to send signals when we change
    # settings in this program. We call st.send_to_all() and then
    # these programs are each told to re-read the settings file.
    st = settings.Settings(
        other_programs = [
            'rain.py',
            'reader.py',
            'scaler.py',
            'trigger.py',
            'mapper.py'
            ])

    # initialise flags
    capturing = True        # allow/stop update of the lines on the screen

    # create objects that hold the state of the UI
    wfs       = WFS_Counter()
    waveform  = Waveform(wfs)
    multimeter = Multimeter()
    ui        = UI_groups(waveform, multimeter)

    # start with the waveform group enabled
    ui.set_updater('waveform')

    # set up a sample buffer object
    buffer = Sample_Buffer()
    

    # main loop
    while True:
        # hack to make the cursor invisible while still responding to touch signals
        # would like to do this only once, rather than every trip round the loop
        if hide_mouse_pointer:
            pygame.mouse.set_cursor(
                (8,8), (0,0), (0,0,0,0,0,0,0,0), (0,0,0,0,0,0,0,0))
        # we update status texts and datetime every second
        if wfs.time_to_update():
            if capturing:
                ui.get_element('datetime').set_text(time.ctime())
            ui.draw_texts()

        # ALWAYS read new data, even if we are not capturing it, to keep the incoming data
        # pipeline flowing. If the read rate doesn't keep up with the pipe, then we will see 
        # artifacts on screen. Check if the BUFFER led on PCB is stalling if performance
        # problems are suspected here.
        # The load_buffer() function also implicitly manages display refresh speed when not
        # capturing, by waiting for a definite time for new data.
        got_new_frame = buffer.load_buffer(sys.stdin, capturing, wfs)
       
        # we don't use the event handler to schedule plotting updates, because it is not
        # efficient enough for high frame rates. Instead we plot explicitly when needed, every
        # time round the loop. 
        ui.refresh(buffer, screen)

        # here we process mouse/touch/keyboard events.
        events = pygame.event.get()
        for e in events:
            if (e.type == pygame.QUIT) or (e.type == pygame.KEYDOWN and e.key == pygame.K_q):
                exit_application('quit')
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_d:
                waveform.plot_mode('dots')
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_l:
                waveform.plot_mode('lines')
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_r:
                capturing = True
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_s:
                capturing = False

        # ui_current_updater.update() is an expensive function, so we use the simplest possible
        # thorpy theme to achieve highest performance/frame rate
        ui.get_updater().update(events=events)
        # push all of our updated work into the active display framebuffer
        pygame.display.flip()


if __name__ == '__main__':
    main()


