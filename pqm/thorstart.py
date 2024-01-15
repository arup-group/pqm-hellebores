import thorpy
import pygame
import sys

WINDOW_SIZE = (100,100)

# initialise pygame
pygame.init()
pygame.display.set_caption('test')
screen = pygame.display.set_mode(WINDOW_SIZE)

# initialise thorpy
thorpy.init(screen, thorpy.theme_classic)



# player is an object that knows how to draw itself
#player = all_ui.get_updater()
# before_refresh is a callback that is called whenever the screen is updated
#player.launch(lambda: before_refresh(screen, all_ui, element_groups))
#pygame.quit()


