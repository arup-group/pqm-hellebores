import sys
import thorpy
import pygame
from hellebores_constants import *
from hellebores_controls import *



class Waveform:
    # array of thorpy text objects
    def __init__(self, st, app_actions):
        self.st = st
        self.ann = Annunciators(st, app_actions)
        self.app_actions = app_actions
        self.draw_background()
        self.create_waveform_controls()
        # initial set up is lines
        self.plot_mode('lines')
         

    def update_annunciators(self):
        self.ann.update_annunciators()


    def draw_background(self):
        xmax = SCOPE_BOX_SIZE[0] - 1
        ymax = SCOPE_BOX_SIZE[1] - 1

        # empty background
        self.waveform_background = pygame.Surface(SCOPE_BOX_SIZE)
        self.waveform_background.fill(GREY)

        # draw the graticule lines
        for dx in range(1, self.st.time_axis_divisions):
            x = self.st.horizontal_pixels_per_division * dx
            # mark the trigger position (t=0) with an emphasized line
            if dx == self.st.time_axis_pre_trigger_divisions and self.st.trigger_mode != 'freerun':
                lc = WHITE
            else:
                lc = LIGHT_GREY
            pygame.draw.line(self.waveform_background, lc, (x, 0), (x, ymax), 1)
        for dy in range(1, self.st.vertical_axis_divisions):
            y = self.st.vertical_pixels_per_division * dy
            # mark the central position (v, i = 0) with an emphasized line
            if dy == self.st.vertical_axis_divisions // 2:
                lc = WHITE
            else:
                lc = LIGHT_GREY
            pygame.draw.line(self.waveform_background, lc, (0, y), (xmax, y), 1)


    # The plot function that will be used is configurable
    # plot_fn is set to point to either _plot_dots() or _plot_lines()
    def _plot_dots(self, screen, linedata, display_status):
        pa = pygame.PixelArray(screen)
        for i in range(len(linedata)):
            if display_status[i] == True:
                for pixel in linedata[i]:
                    pa[pixel[0], pixel[1]] = SIGNAL_COLOURS[i]
        pa.close()


    def _plot_lines(self, screen, linedata, display_status):
        for i in range(len(linedata)):
            if display_status[i] == True:
                pygame.draw.lines(screen, SIGNAL_COLOURS[i], False, linedata[i], 2)

    
    def plot(self, buffer, multi_trace, screen):
        display_status = [
            self.st.voltage_display_status,
            self.st.current_display_status,
            self.st.power_display_status,
            self.st.earth_leakage_current_display_status
            ]
        try:
            for i in range(multi_trace):
                # plot multiple frames if required on the same background
                # can handle up to six plots in each frame...
                linedata = buffer.get_waveform(i)
                self.plot_fn(screen, linedata, display_status)
        except (IndexError, ValueError):
            # pygame.draw.lines does throw an exception if there are not at
            # least two points in each line - (sounds reasonable)
            print(
                f'exception in hellebores.py: plot_fn(). linedata is: {linedata}.\n',
                file=sys.stderr)

    
    def refresh(self, buffer, screen, multi_trace=1):
        screen.blit(self.waveform_background, (0,0))
        self.plot(buffer, multi_trace, screen)


    def plot_mode(self, mode):
        if mode == 'dots':
            self.plot_fn = self._plot_dots
        elif mode == 'lines':
            self.plot_fn = self._plot_lines


    def create_waveform_controls(self):
        """Waveform controls, on right of screen"""
        # Create buttons
        button_setup = [
            ('Run/Stop', self.app_actions.start_stop),
            ('Mode', lambda: self.app_actions.set_updater('mode')), 
            ('Horizontal', lambda: self.app_actions.set_updater('horizontal')), 
            ('Vertical', lambda: self.app_actions.set_updater('vertical')), 
            ('Trigger', lambda: self.app_actions.set_updater('trigger')), 
            ('Options', lambda: self.app_actions.set_updater('options'))
            ]
        buttons = [ configure_button(BUTTON_SIZE, bt, bf) for bt, bf in button_setup ]
        ts = self.ann.get_text_objects()
        # Assemble annunciators and buttons into a group
        self.waveform_controls = thorpy.Box([ *ts[0:2], *buttons, *ts[2:] ])
        self.waveform_controls.set_topright(*CONTROLS_BOX_POSITION)
        self.waveform_controls.set_bck_color(LIGHT_GREY)
        for e in self.waveform_controls.get_all_descendants():
            e.hand_cursor = False    

