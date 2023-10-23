import thorpy
import pygame
from hellebores_constants import *
from hellebores_controls import *

class Multimeter:
    # array of thorpy text objects
    texts = []
    multimeter_background = None
    multimeter_colours = [ GREEN, YELLOW, MAGENTA, CYAN ]
    text_colours = [BLACK, WHITE, WHITE] + multimeter_colours
    current_range = 'full'
    st = None   # set in __init__ to point to settings

    def set_text_colours(self):
        # the boolean filter allows us to temporarily grey out lines
        # that are currently inactive/switched off
        colour_filter = [
            True,
            True,
            True,
            self.st.voltage_display_status,
            self.st.current_display_status,
            self.st.power_display_status,
            self.st.earth_leakage_current_display_status,
            ]
        colours = [ c if p == True else DARK_GREY for p, c in zip(colour_filter, self.text_colours) ]
        for i in range(len(self.texts)):
            self.texts[i].set_font_color(colours[i])

    def __init__(self, st, start_stop_fn, set_updater_fn):
        self.st = st
        self.start_stop_fn = start_stop_fn
        self.set_updater_fn = set_updater_fn
        for s in range(7):
            t = thorpy.Text('')
            t.set_size(TEXT_SIZE)
            self.texts.append(t)
        self.draw_background()

    def set_text(self, item, value):
        self.texts[item].set_text(value)

    def draw_texts(self, capturing):
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
        elv = (self.st.earth_leakage_current_display_ranges
               [self.st.earth_leakage_current_display_index] * 1000)
        self.texts[T_LEAKDIV].set_text(f'{elv} mA/', adapt_parent=False)


    def draw_background(self):
        # empty background
        self.multimeter_background = pygame.Surface(SCOPE_BOX_SIZE)
        self.multimeter_background.fill(GREY)

    def refresh(self, buffer, screen):
        # display all the readings
        pass


    *** NEED THESE REACTION FUNCTIONS TO BE AVAILABLE IN ANOTHER IMPORT ***
    *** THE UI OBJECT IN PARTICULAR WILL NEED TO RESOLVED IF IT IS DEFINED ***
    *** AFTER THIS FILE ***
    def create_multimeter_controls(self, reaction_fns):
        """Multimeter controls, on right of screen"""
        button_setup = [
            ('Run/Stop', reaction_fns.start_stop),
            ('Mode', lambda: reaction_fns.set_updater('mode')), 
            ('Range', lambda: reaction_fns.set_updater('current_range')), 
            ('Options', lambda: reaction_fns.set_updater('options'))
            ]
        buttons = [ configure_button(BUTTON_SIZE, bt, bf) for bt, bf in button_setup ]
        multimeter_controls = thorpy.Box([ *self.texts[0:2], *buttons, *self.texts[2:] ])
        multimeter_controls.set_bck_color(LIGHT_GREY)
        for e in multimeter_controls.get_all_descendants():
            e.hand_cursor = False    
        return multimeter_controls

