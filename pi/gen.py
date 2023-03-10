#!/usr/bin/env python3


#                                  
#   __ _  ___ _ __    _ __  _   _ 
#  / _` |/ _ \ '_ \  | '_ \| | | |
# | (_| |  __/ | | |_| |_) | |_| |
#  \__, |\___|_| |_(_) .__/ \__, |
#  |___/             |_|    |___/ 
# 
# 
import math
import random


SCOPE_BOX_SIZE = (700,480)

def get_capture():
    points1 = []
    points2 = []
    points3 = []
    points4 = []
    T_DIV = 0.005    # standard scope time/div
    FREQ = 60.0
    for s in range(0, SCOPE_BOX_SIZE[0]):
        t = T_DIV*10.0*s/SCOPE_BOX_SIZE[0]
        points1.append((s, 50.0*math.sin(2.0*math.pi*FREQ*t) + 20.0*(random.random() - 0.5)))
        points2.append((s, 50.0*math.sin(2.0*math.pi*FREQ*t) + 20.0*(random.random() - 0.5)))
        points3.append((s, points1[s][1]*points2[s][1]))
        points4.append((s, 0.1*points1[s][1]*points2[s][1]))
    return points1, points2, points3, points4


def to_screen_coordinates(points1, points2, points3, points4):
    p = []
    for t in range(0, len(points1)):
        # invert y axis in plot coordinates, which increase from top of the display downwards
        p.append(' '.join((str(t), str(100-int(points1[t][1])), str(400-int(points2[t][1])),\
                               str(250-int(0.05*points3[t][1])), str(300-int(0.05*points4[t][1])))))
    return p


def main():
    while 1:
        lines = to_screen_coordinates(*get_capture())
        print('\n'.join(lines))



if __name__ == '__main__':
    main()

