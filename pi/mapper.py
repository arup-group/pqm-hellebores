#!/usr/bin/env python3

#Convert values into display coordinates, where the display is 800x600 pixels (graphics to be 700x500 to leave space):
##we'll make the x axis (time) from 0 to 698:
#####Where 0 pixel = 0ms and 699pixel = 40ms
#########x = int(t/40.0*698)
##we'll make the vertical axis y (Voltage) from 0 to 499 pixels:
#####Where 0 pixel = 400V and 498pixel = -400V (negative because axis y goes down)

import sys

def main():
    for line in sys.stdin: #receive data from standard input
        try:
            t, v0, v1, v2, v3 = line.split() # take this line and split 
            x = int((float(t)*698)/40) % 698
            # do other coordinates y1 = vcv
            y0 = int((-float(v0)*249)/500) + 250
            y1 = int((-float(v1)*249)/300) + 250
            y2 = int((-float(v2)*249)/200) + 250
            y3 = int((-float(v3)*249)/100) + 250            
            print(x, y0, y1, y2, y3)
        except ValueError:
            # if stuff goes wrong, deal with it here
            1
        #print('{} {int(t/40.0*699)} {:10.3f} {:10.3f} {:10.3f}')



if __name__ == '__main__':
    main()
