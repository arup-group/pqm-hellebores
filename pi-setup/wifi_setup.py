#!/usr/bin/env python3

import tkinter as tk

root = tk.Tk()

var1 = tk.IntVar()
var2 = tk.StringVar()

# password field is an editable Text object
text = tk.Text(root, height = 1, width = 50)
text.pack()

# we use a Button object to display the currently selected character
character_button = tk.Button(root, width=3, font=('System', 72), textvariable=var2, \
        command=lambda var=var2: text.insert(tk.END, var.get()))
character_button.pack()

# we use a Slider object to select a character
selector = tk.Scale(root, from_=32, to=127, orient=tk.HORIZONTAL, length=500, \
        width=50, label='Character selector', showvalue=0, variable=var1, \
        command=lambda val, var=var1: var2.set(chr(var1.get())))
selector.pack()

# process events
root.mainloop()





