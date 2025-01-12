#!/usr/bin/env python3

# figlet
#           _               _                                           
# _ __ __ _(_)_ __      ___| |__   ___   ___  ___  ___ _ __ _ __  _   _ 
#| '__/ _` | | '_ \    / __| '_ \ / _ \ / _ \/ __|/ _ \ '__| '_ \| | | |
#| | | (_| | | | | |  | (__| | | | (_) | (_) \__ \  __/ | _| |_) | |_| |
#|_|  \__,_|_|_| |_|___\___|_| |_|\___/ \___/|___/\___|_|(_) .__/ \__, |
#                 |_____|                                  |_|    |___/ 
#

# library imports
import thorpy
import pygame
import time
import sys
import os
import math
import random
import copy

# local import
from settings import Settings


WINDOW_SIZE = (600, 500)
FONT = 'font/RobotoMono-Medium.ttf'
FONT_SIZE = 12
SLIDER_SIZE = 60
BACKGROUND_COLOUR = (250, 150, 150)
ROOT2 = math.sqrt(2)
DEFAULT_PRESET = 'Two'

def sample(i, fs):
    """i is integer sample number, fs is a list of tuples (frequency, magnitude, phase).
    For DC tuple, use (0, m, 0), ie set frequency to zero."""
    global st
    t = i*st.interval/1000.0       # convert iterator to time axis position
    s = 0
    for f in fs:
        freq, mag, ph = f
        if freq == 0:
            s = s + mag
        else:
            s = s + ROOT2*mag*math.sin(math.pi*(2.*freq*t + ph/180.))
    return s

def generate_samples(parameters):
    """Generates a block of n samples to bring us up to date wrt to system clock."""
    global st, sample_index, time_zero

    def scale(scale_factor, sample, trip):
        """convert to 16 bit integer. Note that after conversion, negative
           numbers are expressed in 2s complement form."""
        return int(scale_factor*sample + trip) & 0xffff

    # figure out how many new samples we need to generate
    new_time_mark = time.time()*1000.0
    n = int((new_time_mark - time_zero)/st.interval) - sample_index

    # to avoid stalling or hanging the process, don't attempt to print more
    # than 1000 samples in one go: drop them and return early instead
    if n > 1000:
        sample_index = sample_index + n 

    else:
        # retrieve the sample generating coefficients from the current parameters
        f = parameters.get('freq')
        v = [(0.0, parameters.get('v0'), 0.0),
             (f, parameters.get('v1'), 0.0),
             (f*3, parameters.get('v3'), parameters.get('v3_ph')),
             (f*5, parameters.get('v5'), parameters.get('v5_ph'))]
        i = [(0.0, parameters.get('i0'), 0.0),
             (f, parameters.get('i1'), parameters.get('i1_ph')),
             (f*3, parameters.get('i3'), parameters.get('i3_ph')),
             (f*5, parameters.get('i5'), parameters.get('i5_ph'))]
        el = [(f, parameters.get('el'), parameters.get('el_ph'))] 
    
        # generate new samples to bring us up-to-date with the clock
        for _ in range(n):
            # hardware scaling factors for each channel as per below
            # [4.07e-07, 2.44e-05, 0.00122, 0.0489]
            # to simulate the hardware, we scale the signals by the reciprocal of the scaling factor
            trip = parameters.get('trip')
            c3 = scale(1./0.0489, sample(sample_index, v), trip)
            c2 = scale(1./0.00122, sample(sample_index, i), trip)
            c1 = scale(1./2.44e-05, sample(sample_index, i), trip)
            c0 = scale(1./4.07e-07, sample(sample_index, el), trip)
            # update the running total
            sample_index = sample_index + 1
            # output samples in order of leakage current, low range current, full range current, voltage
            print(f"{c0:04x} {c1:04x} {c2:04x} {c3:04x}")

    # return the number of samples processed or incremented
    return n



class Parameters:
    """Holds the fixed and variable parameters that include the coefficients for the sample generator."""
    # labels for the individual parameters -- used to form dictionary lookups
    # for all the parameters that follow below
    labels     = ['trip','freq','v0','v1','v3','v5','v3_ph','v5_ph',
                  'i0', 'i1','i3','i5','i1_ph','i3_ph','i5_ph',
                  'el','el_ph']

    # preset settings that can be recalled by push button
    presets = {
        'One':    [ 0, 50, 0, 230, 0, 0, 0, 0,
                    0, 2, 0.5, 0.3, 30, -60, 180,
                    0.0003, 90 ],
        'Two':    [ 0, 50.05, 0, 230, 0, 0, 0, 0,
                    0, 0.1, 0.02, 0.03, -30, -60, 180,
                    0.0002, 90 ],
        'Three':  [ 0, 49.98, 0, 230, 0, 0, 0, 0,
                    0, 0.5, 0.2, 0.1, 30, -60, 180,
                    0.0002, 90 ],
        'Four':   [ 0, 60.1, 0, 120, 0, 0, 0, 0,
                    0, 1, 0.5, 0.3, 90, 60, -90,
                    0.0001, 90 ],
        'Trip+':  [ 32767, 0, 0, 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 0, 0, 0,
                    0, 0 ],
        'Trip-':  [ -32768, 0, 0, 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 0, 0, 0,
                    0, 0 ]
        }
     
    # a flag to show whether the sliders are horizontal or vertical
    directions = ['h','h','v','v','v','v','h','h',
                  'v','v','v','v','h','h','h',
                  'v','h']

    # the minimum and maximum values that correspond to a slider range
    ranges     = [ (-32768,32767),(30,70), (-400,400), (100,300), (0,100), (0,100), (-180,180), (-180,180),
                   (-5, 5), (0,5), (0,5), (0,5), (-180,180), (-180,180), (-180,180),
                   (0,0.010), (-180,180) ]

    # when displaying parameters as text, we round off to a fixed number of decimal places
    rounding   = [ 0, 2, 0, 0, 0, 0, 0, 0,
                   2, 1, 1, 1, 0, 0, 0,
                   4, 0 ]

    def __init__(self):
        """set up the dictionaries"""
        self.ranges_lookup = dict(zip(self.labels, self.ranges))
        self.directions_lookup = dict(zip(self.labels, self.directions))
        self.rounding_lookup = dict(zip(self.labels, self.rounding))
        self.load_presets('One')

    def load_presets(self, preset_name):
        """create new current settings from preset settings"""
        new_setting = copy.deepcopy(self.presets[preset_name])
        self.periodic_settings_lookup = dict(zip(self.labels, new_setting))

    # setter and getter for individual parameters
    def set(self, ref, value):
        self.periodic_settings_lookup[ref] = value

    def get(self, ref):
        # return a tuple of both the physical parameter and the slider parameter
        return self.periodic_settings_lookup[ref]

    def get_as_slider_position(self, ref):
        """convert the setting to a slider position"""
        v = self.get(ref)
        low, high = self.ranges_lookup[ref]
        slider_direction = self.directions_lookup[ref]
        if slider_direction == 'h':        
            slider_position = SLIDER_SIZE * (v - low)/(high - low)
        elif slider_direction == 'v':
            slider_position = SLIDER_SIZE * (high - v)/(high - low)
        return slider_position
 
    def set_from_slider_position(self, ref, slider_position):
        """figure out the physical value from the slider position, taking
        into account it's orientation"""
        low, high = self.ranges_lookup[ref]
        slider_direction = self.directions_lookup[ref]
        if slider_direction == 'h':        
            value = low + (high - low) * slider_position/SLIDER_SIZE
        elif slider_direction == 'v':
            value = high - (high - low) * slider_position/SLIDER_SIZE
        self.periodic_settings_lookup[ref] = round(value, self.rounding_lookup[ref])


def setup_ui(screen, parameters):
    """Create the UI objects that we need from the thorpy library. Also sets up callback functions
    for the buttons and sliders so that the settings are updated when these are pressed or touched."""
    inhibit_set_from_slider = False
    sliders = {}
    for ref in parameters.labels:
        sliders[ref] = thorpy.SliderWithText(
                             ref, 0, SLIDER_SIZE, 0, SLIDER_SIZE, thickness=8,
                             mode=parameters.directions_lookup[ref],
                             show_value_on_right_side=False, edit=False)

    supply = thorpy.TitleBox('Supply',
                [ sliders['freq'],
                  thorpy.Group([sliders['v0'], sliders['v1'], sliders['v3'], sliders['v5']], mode='h'),
                  thorpy.Group([sliders['v3_ph'], sliders['v5_ph']], mode='v') ])

    load  = thorpy.TitleBox('Load',
               [ thorpy.Group([sliders['i0'], sliders['i1'], sliders['i3'], sliders['i5']], mode='h'),
                 thorpy.Group([sliders['i1_ph'], sliders['i3_ph'], sliders['i5_ph']], mode='v') ])

    earth_leakage = thorpy.TitleBox('Earth Leakage',
                      [ thorpy.Group([sliders['el'], sliders['el_ph']], mode='v') ])

    # the dummy text forces the size of the object and therefore its centre position on screen
    text = thorpy.Text(' '*48 + '\n\n\n\n')

    def set_text(text, parameters):
        p = parameters
        new_text =   f"trip    : {p.get('trip')}\n" \
                   + f"freq    : {p.get('freq')}\n" \
                   + f"voltage : {p.get('v0')}V DC, {p.get('v1')}V (0)," \
                   + f" {p.get('v3')}V ({p.get('v3_ph')})," \
                   + f" {p.get('v5')}V ({p.get('v5_ph')})\n" \
                   + f"current : {p.get('i0')}A DC, {p.get('i1')}A ({p.get('i1_ph')})," \
                   + f" {p.get('i3')}A ({p.get('i3_ph')})," \
                   + f" {p.get('i5')}A ({p.get('i5_ph')})\n" \
                   + f"leakage : {p.get('el')} ({p.get('el_ph')})\n" \
                   + ' '*48         # include a long line so that the dimensions never change
        text.set_value(new_text)

    def load_presets(preset_name, parameters):
        """This callback function is called when a preset button is pressed."""
        # we use this flag to stop the slider from updating settings
        nonlocal inhibit_set_from_slider
        parameters.load_presets(preset_name)
        inhibit_set_from_slider = True            
        for ref in parameters.labels:
            value = parameters.get(ref)
            position = parameters.get_as_slider_position(ref)
            sliders[ref].set_value(position)
        inhibit_set_from_slider = False            
        set_text(text, parameters)

    def slider_to_parameters(ref, parameters):
        """This callback function is used to update the relevant parameter and the text view of
        the settings when the slider is moved."""
        if inhibit_set_from_slider == False:
            parameters.set_from_slider_position(ref, sliders[ref].get_value())
            set_text(text, parameters)

    buttons_ui = thorpy.Group([ thorpy.Button('One'),
                                thorpy.Button('Two'),
                                thorpy.Button('Three'),
                                thorpy.Button('Four'),
                                thorpy.Button('Trip+'),
                                thorpy.Button('Trip-') ], mode='h')
   
    for button in buttons_ui.get_children():
        button.set_size((50, 30))
        button_name = button.get_value()
        button.at_unclick = lambda button_name=button_name: load_presets(button_name, parameters) 

    for ref in parameters.labels:
        # ref = 'v1', 'v3', etc
        slider = sliders[ref].children[1]  # child 1 is the actual slider object
        position = slider.get_value()
        slider.function_to_call(lambda a, b, ref=ref: slider_to_parameters(ref, parameters))

    sliders_ui = thorpy.Group([supply, load, earth_leakage], mode='h')
    all_ui = thorpy.Group([buttons_ui, sliders_ui, text], mode='v')

    # load default parameters
    load_presets(DEFAULT_PRESET, parameters)

    return all_ui


def resolve_path(path, file):
    file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), path, file)
    resolved_path = os.path.abspath(file_path)
    return resolved_path


def main():
    # import constants from settings
    global st, time_zero, sample_index
    st = Settings()

    # we use the system clock to regulate how fast to print samples
    time_zero = int(time.time()*1000.0)
    sample_index = 0

    # initialise pygame
    pygame.init()
    pygame.display.set_caption('Rain Chooser')
    screen = pygame.display.set_mode(WINDOW_SIZE)

    # initialise thorpy
    font = resolve_path('.', FONT)
    thorpy.set_default_font(font, FONT_SIZE)
    thorpy.init(screen, thorpy.theme_classic)

    # initialise the parameter object
    parameters = Parameters()

    # the ui has controls and event handlers that can modify the parameters
    all_ui = setup_ui(screen, parameters)

    # now loop, generating output and checking for user input events
    while True:

        # Check if anything happened in the UI
        events = pygame.event.get()
        if events != []:
            for e in events:
                if (e.type == pygame.QUIT) or (e.type == pygame.KEYDOWN and e.key == pygame.K_q):
                    pygame.quit()
                    sys.exit(0)

            screen.fill(BACKGROUND_COLOUR)
            all_ui.get_updater().update(events=events)
      
            # push our updated work into the active display framebuffer
            pygame.display.flip()

        # Push out up to 1000 samples
        n = generate_samples(parameters)

        # gentle optimisation -- n is the number of samples that we generated in this
        # cycle. If we are managing decent performance, then no need to tear around
        # the loop immediately, instead sleep a little and do a bigger block next time
        # round
        if n < 500:
            time.sleep(0.02)  # equivalent to about 156 samples

    pygame.quit()
    
if __name__ == '__main__':
    main()


