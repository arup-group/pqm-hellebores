#!/usr/bin/env python3

# create a calculator key pad with Tkinter
# tested with Python 3.1.2 and Python 2.6.5
# vegaseat

try:
    # Python2
    import Tkinter as tk
except ImportError:
    # Python3
    import tkinter as tk

# needs Python25 or higher
from functools import partial


def click(btn):
    # test the button command click
    s = "Button %s clicked" % btn
    root.title(s)


root = tk.Tk()
root['bg'] = 'green'

# create a labeled frame for the keypad buttons
# relief='groove' and labelanchor='nw' are default
lf = tk.LabelFrame(root, text=" keypad ", bd=3)
lf.pack(padx=15, pady=10)

# typical calculator button layout
btn_list = [
'7',  '8',  '9',  '*',  'C',
'4',  '5',  '6',  '/',  'M->',
'1',  '2',  '3',  '-',  '->M',
'0',  '.',  '=',  '+',  'neg' ]

# create and position all buttons with a for-loop
# r, c used for row, column grid values
r = 1
c = 0
n = 0
# list(range()) needed for Python3
btn = list(range(len(btn_list)))
for label in btn_list:
    # partial takes care of function and argument
    cmd = partial(click, label)
    # create the button
    btn[n] = tk.Button(lf, text=label, width=5, command=cmd)
    # position the button
    btn[n].grid(row=r, column=c)
    # increment button index
    n += 1
    # update row/column position
    c += 1
    if c > 4:
        c = 0
        r += 1

root.mainloop()


