import thorpy
import pygame
import time
from hellebores_constants import *
from version import Version


###
###
# Controls class for retaining 'up/down' adjustment of values within a range
###
###

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


###
###
# Class for holding and manipulating status annunciators
###
###

class Annunciators:
    # Individual annunciator state enumerations
    A_RUN        = 0
    A_SYNC       = 1
    A_FREERUN    = 2
    A_INRUSH     = 3
    A_STOP       = 4
    A_FULL       = 5
    A_LOWRANGE   = 6
    A_TBASE      = 7
    A_VON        = 8
    A_VOFF       = 9
    A_ION        = 10
    A_IOFF       = 11
    A_PON        = 12
    A_POFF       = 13
    A_ELON       = 14
    A_ELOFF      = 15

    def __init__(self, st, app_actions):
        self.states = [None] * 16  # list of states that select
                                   # text object and format for each
                                   # required state
        self.st = st
        self.app_actions = app_actions
        self.configure_annunciators()


    def add(self, states):
        """Set up an individual annunciator and add it to the list."""
        # states is a list of tuples containing state name, foreground
        # and background colours and format string for each state
        # Example: [ (self.A_RUN,BLACK,GREEN,'Running'), \
        #            (self.A_WAIT,BLACK,ORANGE,'Wait'),
        #            (self.A_STOP,BLACK,RED,'Stopped') ]
        t = thorpy.Text('')    # make a new GUI text object
        t.set_size(TEXT_SIZE)
        for s in states:
            name, foreground_colour, background_colour, template = s
            self.states[name] = (t, foreground_colour, background_colour, template)


    def set(self, name, value=''):
        """Set specific annunciator to a selected state and (optional) text value."""
        # Example call:
        # annunciators.set_annunciator(VON,'20')
        t, foreground_colour, background_colour, template = self.states[name]
        t.set_font_color(foreground_colour)
        t.set_bck_color(background_colour)
        t.set_text(template.format(value), adapt_parent=False)


    def get_text_objects(self):
        """Get the list of Thorpy text objects that will be displayed."""
        text_objects = []
        for s in self.states:
            t = s[0]
            # don't add duplicates of the text object
            if t not in text_objects:
                text_objects.append(t)
        return text_objects


    def configure_annunciators(self):
        """Configure annunciators with available modes and template text."""
        self.add([ (self.A_RUN,BLACK,GREEN,'Run'),
                   (self.A_SYNC,BLACK,GREEN,'Sync'),
                   (self.A_FREERUN,BLACK,GREEN,'Freerun'),
                   (self.A_INRUSH,BLACK,ORANGE,'Inrush'),
                   (self.A_STOP,BLACK,RED,'Stopped') ])
        self.add([ (self.A_FULL,WHITE,LIGHT_GREY,''),
                   (self.A_LOWRANGE,WHITE,ORANGE,'LOW RANGE') ])
        self.add([ (self.A_TBASE,WHITE,LIGHT_GREY,'{0} ms/') ])
        self.add([ (self.A_VON,SIGNAL_COLOURS[0],LIGHT_GREY,'{0} V/'),
                   (self.A_VOFF,GREY,LIGHT_GREY,'{0} V/') ])
        self.add([ (self.A_ION,SIGNAL_COLOURS[1],LIGHT_GREY,'{0} A/'),
                   (self.A_IOFF,GREY,LIGHT_GREY,'{0} A/') ])
        self.add([ (self.A_PON,SIGNAL_COLOURS[2],LIGHT_GREY,'{0} W/'),
                   (self.A_POFF,GREY,LIGHT_GREY,'{0} W/') ])
        self.add([ (self.A_ELON,SIGNAL_COLOURS[3],LIGHT_GREY,'{0} mA/'),
                   (self.A_ELOFF,GREY,LIGHT_GREY,'{0} mA/') ])


    def update_annunciators(self):
        """Update the text and colours of the annunciators in line with the latest
        status information."""
        if self.st.run_mode == 'running':
            if self.app_actions.ui.mode == 'waveform':
                if self.st.trigger_mode == 'sync':
                    self.set(self.A_SYNC)
                elif self.st.trigger_mode == 'freerun':
                    self.set(self.A_FREERUN)
                elif self.st.trigger_mode == 'inrush':
                    self.set(self.A_INRUSH)
            else:
                self.set(self.A_RUN)
        else:
            self.set(self.A_STOP)
        self.set(self.A_FULL if self.st.current_sensor=='full' else self.A_LOWRANGE)
        self.set(self.A_TBASE, self.st.time_display_ranges[self.st.time_display_index])
        self.set(self.A_VON if self.st.voltage_display_status else self.A_VOFF,
                    self.st.voltage_display_ranges[self.st.voltage_display_index])
        self.set(self.A_ION if self.st.current_display_status else self.A_IOFF,
                    self.st.current_display_ranges[self.st.current_display_index])
        self.set(self.A_PON if self.st.power_display_status else self.A_POFF,
                    self.st.power_display_ranges[self.st.power_display_index])
        self.set(self.A_ELON if self.st.earth_leakage_current_display_status
                    else self.A_ELOFF, self.st.earth_leakage_current_display_ranges
                        [self.st.earth_leakage_current_display_index] * 1000.0)



class WFS:

    def __init__(self):
        self.wfs          = 0    # last computed wfs
        self.counter      = 0    # number of waveforms since last posting
        self.update_time  = 0    # time when the wfs/s was lasted posted to screen
        self.create_text_object()

    # call whenever we update the waveform on screen
    def increment(self):
        self.counter += 1

    def update(self):
        # time now
        tn = time.time()
        # if the time has increased by at least 1.0 second, update the wfm/s text
        elapsed = tn - self.update_time
        if elapsed >= 1.0:
            self.wfs = round(self.counter/elapsed)
            self.tt.set_text(f'{self.wfs :3d} wf/s')
            self.update_time = tn
            self.counter = 0

    def create_text_object(self):
        """WFS display."""
        self.tt = thorpy.Text('')
        self.tt.set_font_color(WHITE)
        self.tt.set_topleft(*WFS_POSITION)

    def draw(self):
        self.tt.draw()


class Datetime:

    def __init__(self):
        self.time = time.ctime()
        self.create_text_object()

    def create_text_object(self):
        """Datetime display."""
        self.tt = thorpy.Text(' ' * 25)
        self.tt.set_font_color(WHITE)
        self.tt.set_topleft(*DATETIME_POSITION)

    def update(self):
        self.time = time.ctime()
        self.tt.set_text(self.time)

    def draw(self):
        self.tt.draw()

###
###
# Function definitions to create various button controls for insertion into the
# display.
###
###

def configure_button_decorations(button, callback_function):
    button.set_bck_color(VERY_LIGHT_GREY, 'normal')
    #button.set_bck_color(VERY_LIGHT_GREY, 'hover')
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
    button_waveform = configure_button(BUTTON_WIDE_SIZE, 'Waveform',\
        lambda: app_actions.set_updater('waveform'))
    button_multimeter = configure_button(BUTTON_WIDE_SIZE, 'Multimeter',\
        lambda: app_actions.set_updater('multimeter'))
    button_voltage_harmonics = configure_button(BUTTON_WIDE_SIZE, 'Voltage harmonics',\
        lambda: app_actions.set_updater('voltage_harmonic'))
    button_current_harmonics = configure_button(BUTTON_WIDE_SIZE, 'Current harmonics', \
        lambda: app_actions.set_updater('current_harmonic'))

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

def create_current_sensitivity(st, app_actions):
    """Range controls dialog"""

    def set_current_sensitivity(required_sensitivity):
        st.current_sensor = required_sensitivity
        st.send_to_all()
 
    button_done = configure_button(BUTTON_SIZE, 'Done', lambda: app_actions.set_updater('back'))
    button_full = configure_button(BUTTON_WIDE_SIZE, 'Full', lambda: set_current_sensitivity('full'))
    button_low = configure_button(BUTTON_WIDE_SIZE, 'Low', lambda: set_current_sensitivity('low'))

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
        # Here we switch physical sense channel, if necessary
        if st.current_display_ranges[st.current_display_index] <= 0.05:
            st.current_sensor = 'low'
        else:
            st.current_sensor = 'full'
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
        st.trigger_mode = mode
        waveform.draw_background()
        update_trigger_status(status)
        st.send_to_all()

    def update_trigger_status(status):
        if st.trigger_mode == 'freerun':
            status.set_text(
                f'Freerun: the trigger is disabled.',
                adapt_parent=False)
        elif st.trigger_mode == 'sync':
            status.set_text(
                f'Sync: the trigger is enabled to find the {st.trigger_slope}'
                f' edge of the voltage signal at magnitude 0.0V.',
                adapt_parent=False)
        elif st.trigger_mode == 'inrush':
            status.set_text(
                f'Inrush: the capture will stop when current '
                f'threshold +/- {st.inrush_trigger_level}A is exceeded. '
                f'Press Run/Stop to re-prime.',
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
        BUTTON_SIZE, 'Freerun',
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


def create_clear(buffer, app_actions):
    button_done = configure_button(
        BUTTON_SIZE, 'Done', lambda: app_actions.set_updater('back'))
    button_clear_maxmin = configure_button(
        BUTTON_WIDE_SIZE, 'Clear Max/Min', lambda: buffer.clear_analysis_bounds())
    button_clear_accumulators = configure_button(
        BUTTON_WIDE_SIZE, 'Clear Accumulators', lambda: buffer.clear_accumulators())
    
    clear = thorpy.TitleBox(
        text='Clear',
        children=[
            thorpy.Group(
                elements=[
                   button_done,
                    button_clear_maxmin,
                    button_clear_accumulators
                ], mode='v')
            ])
    for e in clear.get_all_descendants():
        e.hand_cursor = False    
    return clear


def create_options(waveform, app_actions):
    """Option controls dialog"""
    def about_box():
        alert = thorpy.Alert(
            title="hellebores.py",
            text=Version().about(),
            ok_text="Ok, I've read")
        alert.set_draggable()
        alert.cannot_drag_outside = True
        for e in alert.get_all_descendants():
            if isinstance(e, thorpy.elements.Button):
                e.set_bck_color(VERY_LIGHT_GREY, 'normal')
                #e.set_bck_color(VERY_LIGHT_GREY, 'hover')
                e.set_font_color(WHITE)
            if isinstance(e, thorpy.elements.Text):
                e.set_bck_color(LIGHTEST_GREY, 'normal')
                #e.set_bck_color(LIGHTEST_GREY, 'hover')
                e.set_font_color(BLACK)
            e.hand_cursor = False
        alert.launch_nonblocking()

    button_done = configure_button(
        BUTTON_SIZE, 'Done', lambda: app_actions.set_updater('back'))
    button_dots = configure_button(
        BUTTON_SIZE, 'Dots', lambda: waveform.plot_mode('dots'))
    button_lines = configure_button(
        BUTTON_SIZE, 'Lines', lambda: waveform.plot_mode('lines'))
    button_about = configure_button(
        BUTTON_SIZE, 'About...', about_box)
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
