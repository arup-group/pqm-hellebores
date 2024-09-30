#!/usr/bin/env python3

from CTkPopupKeyboard import PopupKeyboard, PopupNumpad
import customtkinter

def show_popup():
    # Disable/Enable popup
    if switch.get()==1:
        keyboard.disable = False
        numpad.disable = False
    else:
        keyboard.disable = True
        numpad.disable = True
        
root = customtkinter.CTk()

text_box = customtkinter.CTkTextbox(root)
text_box.pack(fill="both", padx=10, pady=10)

# attach popup keyboard to text_box
keyboard = PopupKeyboard(text_box)

entry = customtkinter.CTkEntry(root, placeholder_text="Write Something...")
entry.pack(fill="both", padx=10, pady=10)

# attach popup keyboard to entry
numpad = PopupNumpad(entry)

switch = customtkinter.CTkSwitch(root, text="On-Screen Keyboard", command=show_popup)
switch.pack(pady=10)
switch.toggle()

root.mainloop()


