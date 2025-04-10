#
#                      _              _
#   ___ ___  _ __  ___| |_ __ _ _ __ | |_ ___   _ __  _   _
#  / __/ _ \| '_ \/ __| __/ _` | '_ \| __/ __| | '_ \| | | |
# | (_| (_) | | | \__ \ || (_| | | | | |_\__ \_| |_) | |_| |
#  \___\___/|_| |_|___/\__\__,_|_| |_|\__|___(_) .__/ \__, |
#                                              |_|    |___/


# Common constants for all pqm programs

# scaler parameters
# ch0 = earth leakage, ch1 = low range, ch2 = full range, ch3 = voltage
HARDWARE_SCALE_FACTORS = [ 4.07e-07, 2.44e-05, 0.00122, 0.0489 ]

# display pixel dimension parameters
PI_SCREEN_SIZE = (800,480)

# framer parameters for waveform clipping
X_MIN = 0
X_MAX = 699
Y_MIN = 0
Y_MAX = 479

# hellebores UI parameters

# sample buffer for multi-trace history
SAMPLE_BUFFER_SIZE = 16

# UI colours
RED = (255,0,0)
BLUE = (0,0,255)
GREEN = (0,255,0)
ORANGE = (255,150,0)
YELLOW = (255,255,0)
MAGENTA = (255,0,255)
CYAN = (0,255,255)
WHITE = (255,255,255)
BLACK = (0,0,0)
DARK_GREY = (30,30,30)
GREY = (75,75,75)
LIGHT_GREY = (100,100,100)
VERY_LIGHT_GREY = (150,150,150)
LIGHTEST_GREY = (220,220,220)

# set colours for voltage, current, power and earth leakage current
SIGNAL_COLOURS = [ GREEN, YELLOW, MAGENTA, CYAN ]

# scope box is increased by one pixel because line width of plots is
# two pixels wide: leaves artifact dots otherwise
SCOPE_BOX_SIZE = (701,480)           # waveform and multimeter display area
CONTROLS_BOX_SIZE = (99,480)         # main buttons and status texts
CONTROLS_BOX_POSITION = (799,0)      # top right corner
SETTINGS_BOX_SIZE = (500,400)        # 'dialog' boxes
SETTINGS_BOX_POSITION = (690,100)    # top right corner
DATETIME_POSITION = (0,0)
WFS_POSITION = (640,0)
METER_POSITION = (0,32)
BUTTON_SIZE = (86,50)
BUTTON_WIDE_SIZE = (180,50)
TEXT_SIZE = (86,16)
TEXT_WIDE_SIZE = (120,16)
TEXT_METER_LABEL_SIZE = (30,64)
TEXT_METER_SIZE = (184,64)

# typeface and font size parameters
FONT = 'font/RobotoMono-Medium.ttf'
FONT_SIZE = 14
LARGE_FONT_SIZE = 64

# Default pygame font: freesansbold
# Ubuntu monospaced fonts:
# dejavusansmono
# ubuntumono
# bitstreamverasansmono
# nimbusmonops
# notosansmono
# notomono
