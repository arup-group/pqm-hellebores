#!/usr/bin/env python3

import sys
import tkinter as tk

root = tk.Tk()
root.title('Wifi Setup')

slider_position = tk.IntVar()
character_selected = tk.StringVar()
string_entered = tk.StringVar()

def print_result(string_variable):
    print(string_variable.get())

# frame for the buttons
button_frame = tk.Frame(root, width=400, height=100)
button_frame.grid(row=2, column=0)

# password field is an editable Text object
text = tk.Entry(root, width=50, textvariable=string_entered)
text.grid(row=1, column=0)

# we use a Button object to display the currently selected character
type_button = tk.Button(button_frame, width=5, font=('System', 18), textvariable=character_selected, \
        command=lambda c=character_selected: text.insert(tk.END, c.get()))
type_button.grid(row=0, column=0)
delete_button = tk.Button(button_frame, width=5, font=('System', 18), text='<BS', \
        command=lambda: string_entered.set(string_entered.get()[:-1]))
delete_button.grid(row=0, column=1)
enter_button = tk.Button(button_frame, width=5, font=('System', 18), text='ENTER', \
        command=lambda: print_result(string_entered) and sys.exit(0))
enter_button.grid(row=0, column=2)

# we use a Slider object to select a character
selector = tk.Scale(root, from_=32, to=127, orient=tk.HORIZONTAL, length=500, \
        width=50, label='Character selector', showvalue=0, variable=slider_position, \
        command=lambda val, var=slider_position: character_selected.set(chr(slider_position.get())))
selector.grid(row=3, column=0)
#selector.pack()

# process events
root.mainloop()





