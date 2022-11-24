#ThorPy hello world tutorial : full code
import thorpy

application = thorpy.Application(size=(300, 300), caption="Hello world")

my_button = thorpy.make_button("Hello, world!") #just a useless button
my_button.center() #center the element on the screen

menu = thorpy.Menu(my_button) #create a menu for auto events handling
menu.play() #launch the menu

application.quit()


