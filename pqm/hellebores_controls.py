import thorpy
import pygame
import time
from hellebores_constants import *


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
    text_datetime.set_topleft(0,0)
    return text_datetime

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
    
def create_mode(app_actions):
    """Mode controls dialog"""
    button_waveform = configure_button(BUTTON_WIDE_SIZE, 'Waveform', lambda: app_actions.set_updater('waveform'))
    button_multimeter = configure_button(BUTTON_WIDE_SIZE, 'Multimeter', lambda: app_actions.set_updater('multimeter'))
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

def create_current_range(app_actions):
    """Range controls dialog"""
    button_done = configure_button(BUTTON_SIZE, 'Done', lambda: app_actions.set_updater('back'))
    button_full = configure_button(BUTTON_WIDE_SIZE, 'Full', lambda: app_actions.set_current_range('full'))
    button_low = configure_button(BUTTON_WIDE_SIZE, 'Low', lambda: app_actions.set_current_range('low'))

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

def create_horizontal(st, app_actions):
    """Horizontal controls dialog"""
    def update_time_range(times, offset):
        times.change_range(offset)
        time_display.set_text(f'{times.get_value()} ms/div',
            adapt_parent=False)
        st.time_display_index = times.get_index()
        st.send_to_all()

    button_done = configure_button(BUTTON_SIZE, 'Done', lambda: app_actions.set_updater('back'))

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
 

def create_vertical(st, app_actions):
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

    def flip_display_switch(st, channel, switch_status):
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

    button_done = configure_button(BUTTON_SIZE, 'Done', lambda: app_actions.set_updater('back'))

    voltages = Range_controller(
        st.voltage_display_ranges, st.voltage_display_index)
    voltage_onoff = configure_switch_button(
        BUTTON_SIZE,st.voltage_display_status,
        lambda: flip_display_switch(st, 'voltage', voltage_onoff.value))
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
        lambda: flip_display_switch(st, 'current', current_onoff.value))
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
        lambda: flip_display_switch(st, 'power', power_onoff.value))
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
        lambda: flip_display_switch(st, 'leakage', leakage_current_onoff.value))
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


def create_trigger(st, waveform, app_actions):
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
        BUTTON_SIZE, 'Done', lambda: app_actions.set_updater('back'))
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

def create_options(waveform, app_actions):
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
        BUTTON_SIZE, 'Done', lambda: app_actions.set_updater('back'))
    button_dots = configure_button(
        BUTTON_SIZE, 'Dots', lambda: waveform.plot_mode('dots'))
    button_lines = configure_button(
        BUTTON_SIZE, 'Lines', lambda: waveform.plot_mode('lines'))
    button_about = configure_button(
        BUTTON_SIZE, 'About...',about_box)
    button_software_update = configure_button(
        BUTTON_SIZE, 'Software\nupdate', lambda: app_actions.exit_application('software_update'))
    button_shutdown = configure_button(
        BUTTON_SIZE, 'SHUTDOWN', lambda: app_actions.exit_application('shutdown'))
    button_restart = configure_button(
        BUTTON_SIZE, 'RESTART', lambda: app_actions.exit_application('restart'))
    button_quit = configure_button(
        BUTTON_SIZE, 'QUIT', lambda: app_actions.exit_application('quit'))

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



def voltage_harmonics_reaction():
    pass

def current_harmonics_reaction():
    pass
