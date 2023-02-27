#Convert values into display coordinates, where the display is 800x600 pixels (graphics to be 700x500 to leave space):
##we'll make the x axis (time) from 0 to 699:
#####Where 0 pixel = 0ms and 699pixel = 40ms
#########x = int(t/40.0*699)
##we'll make the vertical axis y (Voltage, Current, leakage current) from 0 to 499 pixels:
#####Where 0 pixel = 400V and 499pixel = -400V (negatove because axis y goes down)
##

import sys

def main():
    for line in sys.stdin: #receive data from standard input
        try:
            t, v1, v2, v3, v4 = line.split() # take this line and split 
            x = int((t*698)/40) % 698
            print(x)
        except ValueError:
            # if stuff goes wrong, deal with it here
            1
       # print('{int(t/40.0*699)} {int(t/40.0*699)} {:10.3f} {:10.3f} {:10.3f}')



if __name__ == '__main__':
    main()
