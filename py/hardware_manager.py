#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Ryan Jennings
# Author: Chris Usey
# Author: Todd Giles (todd@lightshowpi.com)
# Author: Tom Enos
"""
Control the raspberry pi hardware.

The hardware controller handles all interaction with the raspberry pi hardware to turn the lights
on and off.

Third party dependencies:

wiringpi2: python wrapper around wiring pi - https://github.com/WiringPi/WiringPi2-Python
"""
import argparse
import cPickle
import logging
import os
import platform
import socket
import subprocess
import sys
import threading
import time

import configuration_manager

# Are we running this on a raspberry pi?
# if not then use Tkinter to show what is happening
# NOTE: Only works on linux
pi = True

if "raspberrypi" in platform.uname():
    #from wiringpi2 import *
    import wiringpi2 as wiringpi
else:
    import light_simulator as wiringpi
    #from light_simulator import *
    pi = False


class Pin(object):
    
    def __init__(self, pin_number, pin_mode, active_low_mode, pwm_max):
        self.pin_number = pin_number
        self.pwm = pin_mode
        
        self.pwm_max = pwm_max
        self.active_low_mode = active_low_mode
        
        self.gpioactive = int(not active_low_mode)
        self.gpioinactive = int(active_low_mode)

        self.pwm_on = pwm_max * int(not active_low_mode)
        self.pwm_off = pwm_max * int(active_low_mode)
        
        self.state = 0.0
        self.inout = 'Not set'
        self.always_on = False
        self.always_off = False
        self.inverted = False
        
    def __str__(self):
        """
        
        """
        gpio_pin_number = "channel number: " + str(self.pin_number) + "\n"
        pwm_mode = "in pwm mode: " + str(self.pwm) + "\n"
        in_out = "in/out: " + self.inout + "\n"
        always_on = "always on: " + str(self.always_on) + "\n"
        always_off = "always off: " + str(self.always_off) + "\n"
        inverted = "inverted: " + str(self.inverted)
        temp = 0
        if self.active_low_mode:
            self.state -= 1
        if self.state == 0.0:
            temp = "off"
        elif self.state == 1.0:
            temp = "on"
        else:
            temp = str(self.state)
        state = "current state: " + temp + "\n"

        return gpio_pin_number + state + pwm_mode + in_out + always_on + always_off + inverted

    def set_as_input(self):
        """
        
        """
        self.inout = 'pin is input'
        wiringpi.pinMode(self.pin_number, 0)
    
    def set_as_output(self):
        """
        
        """
        self.inout = 'pin is output'
        if self.pwm:
            wiringpi.softPwmCreate(self.pin_number, 0, self.pwm_max)
        else:
            wiringpi.pinMode(self.pin_number, 1)

    def set_always_on(self, value):
        """
        Should this channel be always on
        
        :param value: boolean
        """
        self.always_on = value
        
    def set_always_off(self, value):
        """
        Should this channel be always off
        
        :param value: boolean
        """
        self.always_off = value

    def set_inverted(self, value):
        """
        Should this channel be inverted
        
        :param value: boolean
        """
        self.inverted = value

    def light_action(self, use_overrides=False, brightness=0.0):
        """
        Turn this light on or off, or some value inbetween

        Taking into account various overrides if specified.
        :param use_overrides: int or boolean, should overrides be used
        :param brightness: float, between 0.0 and 1.0, brightness of light
        0.0 is full off
        1.0 is full on
        
        """
        #if self.active_low_mode:
            #brightness = 1.0 - brightness
        if use_overrides:
            brightness = max(int(self.always_on), brightness)
            brightness = min(int(not self.always_off), brightness)
            brightness = abs(int(self.inverted) - brightness)

            #if self.always_off:
                #brightness = 0
            #elif self.always_on:
                #brightness = 1
            #if self.inverted:
                #brightness = 1 - brightness
        brightness = abs(int(self.active_low_mode) - brightness)
        if self.pwm:
            wiringpi.softPwmWrite(self.pin_number, int(brightness * self.pwm_max))
        else:
            wiringpi.digitalWrite(self.pin_number, int(brightness))

        self.state = brightness

class Hardware(configuration_manager.Configuration):
    
    def __init__(self):
        super(Hardware, self).__init__()
        self.lights = list()
        
        self.devices = self.hardware_config['devices']
        self.gpio_pins = self.hardware_config['gpio_pins']
        self.gpiolen = self.hardware_config['gpiolen']
        self.pin_modes = self.hardware_config['pin_modes']
        self.pwm_max = self.hardware_config['pwm_range']
        self.active_low_mode = self.hardware_config['active_low_mode']

        self.networking = self.network_config['networking']
        self.port = self.network_config['port']
        self.playing = False
        self.vr = None

        self.is_pin_pwm = list()
        for pmode in range(len(self.pin_modes)):
            if self.pin_modes[pmode] == "pwm":
                self.is_pin_pwm.append(True)
            else:
                self.is_pin_pwm.append(False)
        
        self.create_lights()
        self.set_overrides()

        # if in broadcast mode, setup socket
        if self.networking == "server":
            self.setup_network()

    def set_playing(self):
        """
        
        """
        self.playing = True

    def unset_playing(self):
        """
        
        """
        self.playing = False

    def create_lights(self):
        """
        
        """
        for channel in range(self.gpiolen):
            pin = self.gpio_pins[channel]
            if self.pin_modes[channel].lower() == 'pwm':
                mode = True
            else:
                mode = False
                
            self.lights.append(Pin(pin, mode, self.active_low_mode, self.pwm_max))
            
    def set_overrides(self):
        """
        
        """
        for channel in range(self.gpiolen):
            self.lights[channel].set_always_off(channel + 1 in self.lightshow_config['always_off_channels'])
            self.lights[channel].set_always_on(channel + 1 in self.lightshow_config['always_on_channels'])
            self.lights[channel].set_inverted(channel + 1 in self.lightshow_config['invert_channels'])
            
    def setup_network(self):
        """
        
        """
        print "streaming on port: " + str(self.port)
        try:
            self.streaming = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.streaming.bind(('', 0))
            self.streaming.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST,1)
            logging.info("streaming on port: " + str(self.port))
        except socket.error, msg:
            logging.error('Failed create socket or bind. Error code: ' + 
                        str(msg[0]) + 
                        ' : ' + 
                        msg[1])
            print "error creating and binding socket for broadcast"
            sys.exit()

    def enable_device(self):
        """enable the specified device """
        try:
            for key in self.devices.keys():
                device = key
                device_slaves = self.devices[key]
                
                # mcp23017
                if device.lower() == "mcp23017":
                    for slave in device_slaves:
                        params = slave
                        wiringpi.mcp23017Setup(int(params['pinBase']),
                                      int(params['i2cAddress'], 16))
                
                # mcp23s17
                elif device.lower() == "mcp23s17":
                    for slave in device_slaves:
                        params = slave
                        wiringpi.mcp23s17Setup(int(params['pinBase']),
                                      int(params['spiPort'], 16),
                                      int(params['devId']))
                
                # TODO: Devices below need testing, these should work but 
                # could not verify due to lack of hardware
                
                # mcp23016
                elif device.lower() == "mcp23016":
                    for slave in device_slaves:
                        params = slave
                        wiringpi.mcp23016Setup(int(params['pinBase']),
                                      int(params['i2cAddress'], 16))

                # mcp23s08 - Needs Testing
                elif device.lower() == "mcp23008":
                    for slave in device_slaves:
                        params = slave
                        wiringpi.mcp23008Setup(int(params['pinBase']),
                                      int(params['i2cAddress'], 16))

                # mcp23s08 - Needs Testing
                elif device.lower() == "mcp23s08":
                    for slave in device_slaves:
                        params = slave
                        wiringpi.mcp23s08Setup(int(params['pinBase']),
                                      int(params['spiPort'], 16),
                                      int(params['devId']))

                # sr595 - Needs Testing
                elif device.lower() == "sr595":
                    for slave in device_slaves:
                        params = slave
                        wiringpi.sr595Setup(int(params['pinBase']),
                                   int(params['numPins']),
                                   int(params['dataPin']),
                                   int(params['clockPin']),
                                   int(params['latchPin']))
                
                # pcf8574
                elif device.lower() == "pcf8574":
                    for slave in device_slaves:
                        params = slave
                        wiringpi.pcf8574Setup(int(params['pinBase']),
                                     int(params['i2cAddress'], 16))

                else:
                    logging.error("Device defined is not supported, please check your devices "
                                "settings: " + str(device))
            logging.info("Device defined is ready for use: " + str(device))
        except Exception as e:
            logging.debug("Error setting up devices, please check your devices settings. " + str(3))

    def set_pins_as_outputs(self):
        """Set all the configured pins as outputs."""
        for pin in range(self.gpiolen):
            self.set_pin_as_output(pin)

    def set_pins_as_inputs(self):
        """Set all the configured pins as inputs."""
        for pin in range(self.gpiolen):
            self.set_pin_as_input(pin)

    def set_pin_as_output(self, pin):
        """
        Set the specified pin as an output.

        :param pin: int, index of pin in gpio_pins
        """
        self.lights[pin].set_as_output()

    def set_pin_as_input(self, pin):
        """
        Set the specified pin as an input.

        :param pin: int, index of pin in gpio_pins
        """
        self.lights[pin].set_as_input()

    def turn_on_lights(self, use_always_onoff=False):
        """
        Turn on all the lights

        But leave off all lights designated to be always off if specified.

        :param use_always_onoff: int or boolean, should always on/off be used
        """
        for pin in range(self.gpiolen):
            self.turn_on_light(pin, use_always_onoff)

    def turn_off_lights(self, use_always_onoff=False):
        """
        Turn off all the lights

        But leave on all lights designated to be always on if specified.

        :param use_always_onoff: int or boolean, should always on/off be used
        """
        for pin in range(self.gpiolen):
            self.turn_off_light(pin, use_always_onoff)

    def turn_on_light(self, pin, use_overrides=False, brightness=1.0):
        """
        Turn on the specified light

        Taking into account various overrides if specified.
        :param pin: int, index of pin in gpio_pins
        :param use_overrides: int or boolean, should overrides be used
        :param brightness: float, between 0.0 and 1.0, brightness of light
        """
        if not self.playing and self.networking == "server":
            self.broadcast(pin, brightness)

        self.lights[pin].light_action(use_overrides, brightness)
        
    def turn_off_light(self, pin, use_overrides=False):
        """
        Turn off the specified light

        Taking into account various overrides if specified.
        :param pin: int, index of pin in gpio_pins
        :param use_overrides: int or boolean, should overrides be used
        """
        if not self.playing and self.networking == "server":
            self.broadcast(pin, 0.0)
            
        self.lights[pin].light_action(use_overrides, 0.0)
        
    def broadcast(self, *args):
        """
        
        """
        if self.networking == "server":
            data = cPickle.dumps(args)
            self.streaming.sendto(data,('<broadcast>', self.port))

    def clean_up(self):
        """
        Clean up and end the lightshow

        Turn off all lights set the pins as inputs
        """
        self.turn_off_lights()
        self.set_pins_as_inputs()
        
        #try:
            #if self.networking == "server":
                #for pin in range(self.gpiolen):
                    #self.broadcast(pin, 0)
                #self.streaming.close()
        #except socket.error , msg:
            #logging.error(str(msg[0]) + ' ' + msg[1])
            #print str(msg[0]) + ' ' + msg[1]
            
        if not pi and self.vr:
            if self.vr.isAlive():
                wiringpi.quit()
                #self.vr._Thread__stop()
            
    def initialize(self):
        """Set pins as outputs, and start all lights in the off state."""
        if not pi:
            gpioactive = int(not self.active_low_mode)
            self.vr = threading.Thread(target=wiringpi.ui, args=(self.gpio_pins, self.gpiolen, self.pwm_max, gpioactive))
            self.vr.start()
            time.sleep(1)
            
        wiringpi.wiringPiSetup()
        self.enable_device()
        self.set_pins_as_outputs()
        self.turn_off_lights()

    def load_config(self):
        logging.info("Reloading config")
        self.set_overrides()


# __________________Main________________
def main():
    """main"""
    hardware = Hardware()
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', choices=["off", "on", "flash", "fade", "cleanup"],
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

    lights = [int(light) for light in args.light.split(',')]
    if -1 in lights:
        lights = range(0, len(hardware.gpio_pins))

    hardware.initialize()

    if state == "cleanup":
        hardware.clean_up()
    elif state == "off":
        for light in lights:
            hardware.turn_off_light(light)
    elif state == "on":
        for light in lights:
            hardware.turn_on_light(light)
    elif state == "fade":
        # Test fading in and out for each light configured in pwm mode
        print "Press <CTRL>-C to stop"
        while True:
            try:
                for light in lights:
                    print "channel %s " % light
                    if hardware.is_pin_pwm[light]:
                        for _ in range(flashes):
                            for brightness in range(0, hardware.pwm_max):
                                # fade in
                                hardware.turn_on_light(light, 0, float(brightness) / hardware.pwm_max)
                                time.sleep(sleep / hardware.pwm_max)
                            for brightness in range(hardware.pwm_max - 1, -1, -1):
                                # fade out
                                hardware.turn_on_light(light, 0, float(brightness) / hardware.pwm_max)
                                time.sleep(sleep / hardware.pwm_max)
            except KeyboardInterrupt:
                print "\nstopped"
                hardware.clean_up()
                break
    elif state == "flash":
        print "Press <CTRL>-C to stop"
        while True:
            try:
                for light in lights:
                    print "channel %s " % light
                    for _ in range(flashes):
                        hardware.turn_on_light(light)
                        time.sleep(sleep)
                        hardware.turn_off_light(light)
                        time.sleep(sleep)
            except KeyboardInterrupt:
                print "\nstopped"
                hardware.clean_up()
                break
    else:
        parser.print_help()

if __name__ == "__main__":
    main()



