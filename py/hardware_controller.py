#!/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Ryan Jennings
# Author: Chris Usey
# Author: Todd Giles (todd@lightshowpi.com)
"""Control the raspberry pi hardware.

The hardware controller handles all interaction with the raspberry pi hardware to turn the lights
on and off.

Third party dependencies:

wiringpi2: python wrapper around wiring pi - https://github.com/WiringPi/WiringPi2-Python
"""

import argparse
import logging
import math
import time

import configuration_manager as cm

import serial
from sense_hat import SenseHat

LEFT_SIZE = 36
RIGHT_SIZE = 36
CENTRE_SIZE = 28

GPIOLEN = 8

# Initialise Serial port
port = serial.Serial("/dev/ttyACM0", baudrate=115200)
time.sleep(2)

# Initialise SenseHat
sense = SenseHat()

# Functions
def turn_off_lights():
    """Turn off all the lights, but leave on all lights designated to be always on if specified."""
    port.write("0,0,0,0,0,0\n")
    sense.clear()

def turn_on_lights():
    """Turn on all the lights, but leave off all lights designated to be always off if specified."""
    port.write("{},4,{},3,{},2\n".format(LEFT_SIZE,RIGHT_SIZE,CENTRE_SIZE))
    for x in range(0,8):
        for y in range(0,8):
            sense.set_pixel(x,y,[0,0,255])

def set_levels(brightness, peaks, bassOn):
    leftPeak = int(peaks[0]*LEFT_SIZE)
    rightPeak = int(peaks[1]*RIGHT_SIZE)
    bass = CENTRE_SIZE if bassOn else 0

    string = "{},1,{},2,{},3\n".format(leftPeak,rightPeak,bass)
    port.write(string)

    sense.clear()
    for col in range(0,8):
        b = brightness[col]

        if math.isnan(b):
            b = 0

        if b < 0.0:
            b = 0.0

        if b > 1.0:
            b = 1.0

        for row in range(0,int(8.0 * b)):
            sense.set_pixel(row,col,[0,255,0])

def clean_up():
    """Turn off all lights, and set the pins as inputs."""
    turn_off_lights()


def initialize():
    """Set pins as outputs, and start all lights in the off state."""
    turn_off_lights()


# __________________Main________________
def main():
    """main"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', choices=["off", "on", "flash", "cleanup"],
                        help='turn off, on, flash, or cleanup')
    parser.add_argument('--light', default='-1',
                        help='the lights to act on (comma delimited list), -1 for all lights')
    parser.add_argument('--sleep', default=0.5,
                        help='how long to sleep between flashing or fading a light')
    parser.add_argument('--flashes', default=2,
                        help='the number of times to flash or fade each light')
    args = parser.parse_args()
    state = args.state
    sleep = float(args.sleep)
    flashes = int(args.flashes)

    initialize()

    if state == "cleanup":
        clean_up()
    elif state == "off":
        for light in lights:
            turn_off_light(light)
    elif state == "on":
        for light in lights:
            turn_on_light(light)
    elif state == "flash":
        print "Press <CTRL>-C to stop"
        while True:
            try:
                turn_on_lights()
                time.sleep(sleep)
                turn_off_lights()
                time.sleep(sleep)
            except KeyboardInterrupt:
                print "\nstopped"
                turn_off_lights()
                break
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
