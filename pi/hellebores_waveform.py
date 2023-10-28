import thorpy
import pygame
from hellebores_constants import *
from hellebores_controls import *


# text message cell enumerations
T_RUNSTOP     = 0
T_WFS         = 1
T_TIMEDIV     = 2
T_VOLTSDIV    = 3
T_AMPSDIV     = 4
T_WATTSDIV    = 5
T_LEAKDIV     = 6


class Waveform:
    # array of thorpy text objects
    waveform_colours = [ GREEN, YELLOW, MAGENTA, CYAN ]
    text_colours = [BLACK, WHITE, WHITE] + waveform_colours

    def __init__(self, st, wfs, app_actions):
        self.texts = []
        self.st = st
        self.wfs = wfs
        self.app_actions = app_actions
        for s in range(7):
            t = thorpy.Text('')
            t.set_size(TEXT_SIZE)
            self.texts.append(t)
        self.waveform_background = self.draw_background()
        self.waveform_controls = self.create_waveform_controls()
        # initial set up is lines
        self.plot_mode('lines')
         

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
        self.texts[T_WFS].set_text(f'{self.wfs.get()} wfm/s', adapt_parent=False)
        self.texts[T_TIMEDIV].set_text(
            f'{self.st.time_display_ranges[self.st.time_display_index]} ms/',
            adapt_parent=False)
        self.texts[T_VOLTSDIV].set_text(
            f'{self.st.voltage_display_ranges[self.st.voltage_display_index]} V/',
            adapt_parent=False)
        self.texts[T_AMPSDIV].set_text(
            f'{self.st.current_display_ranges[self.st.current_display_index]} A/',
            adapt_parent=False)
        self.texts[T_WATTSDIV].set_text(
            f'{self.st.power_display_ranges[self.st.power_display_index]} W/',
            adapt_parent=False)
        elv = (self.st.earth_leakage_current_display_ranges
               [self.st.earth_leakage_current_display_index] * 1000)
        self.texts[T_LEAKDIV].set_text(f'{elv} mA/', adapt_parent=False)


    def draw_background(self):
        xmax = SCOPE_BOX_SIZE[0] - 1
        ymax = SCOPE_BOX_SIZE[1] - 1

        # empty background
        waveform_background = pygame.Surface(SCOPE_BOX_SIZE)
        waveform_background.fill(GREY)

        # draw the graticule lines
        for dx in range(1, self.st.time_axis_divisions):
            x = self.st.horizontal_pixels_per_division * dx
            # mark the trigger position (t=0) with an emphasized line
            if (dx == self.st.time_axis_pre_trigger_divisions) and (self.st.trigger_channel != -1):
                lc = WHITE
            else:
                lc = LIGHT_GREY
            pygame.draw.line(waveform_background, lc, (x, 0), (x, ymax), 1)
        for dy in range(1, self.st.vertical_axis_divisions):
            y = self.st.vertical_pixels_per_division * dy
            # mark the central position (v, i = 0) with an emphasized line
            if dy == self.st.vertical_axis_divisions // 2:
                lc = WHITE
            else:
                lc = LIGHT_GREY
            pygame.draw.line(waveform_background, lc, (0, y), (xmax, y), 1)
        return waveform_background

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
        linedata = buffer.get_waveform()
        display_status = [
            self.st.voltage_display_status,
            self.st.current_display_status,
            self.st.power_display_status,
            self.st.earth_leakage_current_display_status
            ]
        try:
            self.plot_fn(screen, linedata, display_status)
        except (IndexError, ValueError):
            # the pygame.draw.lines will throw an exception if there are not at
            # least two points in each line - (sounds reasonable)
            print(
                f'exception in hellebores.py: plot_fn(). linedata is: {linedata}.\n',
                file=sys.stderr)

    def refresh(self, buffer, screen):
        self.plot(buffer, screen)

    def plot_mode(self, mode):
        if mode == 'dots':
            self.plot_fn = self._plot_dots
        elif mode == 'lines':
            self.plot_fn = self._plot_lines

    def create_waveform_controls(self):
        """Waveform controls, on right of screen"""
        button_setup = [
            ('Run/Stop', self.app_actions.start_stop),
            ('Mode', lambda: self.app_actions.set_updater('mode')), 
            ('Horizontal', lambda: self.app_actions.set_updater('horizontal')), 
            ('Vertical', lambda: self.app_actions.set_updater('vertical')), 
            ('Trigger', lambda: self.app_actions.set_updater('trigger')), 
            ('Options', lambda: self.app_actions.set_updater('options'))
            ]
        buttons = [ configure_button(BUTTON_SIZE, bt, bf) for bt, bf in button_setup ]
        waveform_controls = thorpy.Box([ *self.texts[0:2], *buttons, *self.texts[2:] ])
        waveform_controls.set_topright(*CONTROLS_BOX_POSITION)
        waveform_controls.set_bck_color(LIGHT_GREY)
        for e in waveform_controls.get_all_descendants():
            e.hand_cursor = False    
        return waveform_controls

