# !/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Tom Enos

from math import ceil
import Tkinter
import sys
import threading

class Gui(object):
    def __init__(self):
        self.is_setup = False
        self.gpio_pins = None
        self.gpiolen = None
        self.pwm_max = None
        self.gpioactive = None
        self.gpio = list()
        self.state = list()

   
    def setup_sim(self, gpins, glen, pmax, gactive, gui_locals):
        
        self.gui_locals = gui_locals
        self.parent = self.gui_locals.parent
        self.canvas = self.gui_locals.canvas
        
        self.gpio_pins = gpins
        self.gpiolen = glen
        self.pwm_max = pmax
        self.gpioactive = gactive
        
        # on screen position of the tkinter window
        # 0,0 top left corner
        self.screen_x = 0
        self.screen_y = 0

        # radius of lights
        self.rad = 10

        # x and y of the first light inside the tkinter window
        self.x = self.rad * 2
        self.y = self.rad * 2

        # lights are evenly spaced by half the radius
        self.spacing = (self.rad * 2) + (self.rad / 2)

        # How many lights in a row
        self.max_row_length = 16

        self.row_length = self.gpiolen

        if self.gpiolen > self.max_row_length:
            self.row_length = self.max_row_length

        # calculate number of rows
        self.rows = int(ceil(self.gpiolen / self.row_length))

        # size of the window
        self.width = (self.row_length * self.spacing) + int((self.rad * 1.75))
        self.height = (self.rows * self.spacing) + int(self.rad * 1.75)

        self.red = "#FF0000"
        self.green = "#00FF00"
        self.blue = "#0000FF"
        self.white = "#FFFFFF"
        self.black = "#000000"
        
        self.parent.geometry('{0:d}x{1:d}+{2:d}+{3:d}'.format(self.width, self.height, self.screen_x, self.screen_y))
        self.parent.title("Lights")        
        self.parent.protocol("WM_DELETE_WINDOW", self.quit)
        x1, y1 = self.x, self.y
        
        row_counter = 0
        
        for counter in range(self.gpiolen):
            top_left = x1 - self.rad
            bottom_left = y1 - self.rad
            top_right = x1 + self.rad
            bottom_right = y1 + self.rad
            
            self.gpio.append(self.canvas.create_oval(top_left, 
                                                bottom_left, 
                                                top_right, 
                                                bottom_right, 
                                                fill="#FFFFFF"))

            x1 += self.spacing
            row_counter += 1

            if row_counter == self.row_length:
                x1 = self.x
                y1 += self.spacing
                row_counter = 0

        self.canvas.pack(fill=Tkinter.BOTH, expand=1)


    def start_display(self):
        """
        
        """
        self.parent.mainloop()
            
    def quit(self):
        """
        
        """
        if 'normal' == self.parent.state():
            self.parent.destroy()

    def softPwmWrite(self, gpin, brightness):
        """
        
        :param gpin, int, to be used as index of gpio pin to use
        :param birghtness, int, brightness of light
        """
        pin = self.gpio_pins.index(gpin)
        if self.gpioactive:
            brightness = 100 - brightness
        level = '#{0:02X}{1:02X}{2:02X}'.format(255, int(ceil(brightness * 2.55)), int(ceil(brightness * 2.55)))
        try:
            self.canvas.itemconfig(self.gpio[pin], fill=level)
            self.parent.update()
        except:
            pass
        
    def digitalWrite(self, gpin, onoff):
        """
        
        :param gpin, int, to be used as index of gpio pin to use
        :param onoff, on or off
        """
        pin = self.gpio_pins.index(gpin)
        item = self.gpio[pin]
        if self.gpioactive:
            onoff = 1 - onoff
        color = (self.blue, self.white)[onoff]
        try:
            self.canvas.itemconfig(item, fill=color)
            self.parent.update()
        except:
            pass
        
    # Empty functions, most will remain empty as they are not needed
    # but we can implement any that are needed in the future.
    # TODO: (Tom) Implement softPwmCreate, and pinMode and add option to set 
    #             light colors (individual or all) through these functions
    #             Add empty functions for all other wiringPi methods that work in python
    #             incase we decide to use them in the future.
    #             
    def wiringPiSetup(self):
        """Empty function"""
        pass

    #def wiringPiSetupSys():
    #def wiringPiSetupGpio():
    #def wiringPiSetupPhys():

    def softPwmCreate(self, *agrs):
        """Empty function"""
        pass


    def pinMode(self, *agrs):
        """Empty function"""
        pass


    def mcp23017Setup(self, *agrs):
        """Empty function"""
        pass


    def mcp23s17Setup(self, *agrs):
        """Empty function"""
        pass


    def mcp23016Setup(self, *agrs):
        """Empty function"""
        pass


    def mcp23008Setup(*agrs):
        """Empty function"""
        pass


    def mcp23s08Setup(self, *agrs):
        """Empty function"""
        pass


    def pcf8574Setup(self, *agrs):
        """Empty function"""
        pass


    def sr595Setup(self, *agrs):
        """Empty function"""
        pass


    def softPwmCreate(self, *agrs):
        """Empty function"""
        pass


    def pinMode(self, *agrs):
        """Empty function"""
        pass

if __name__ in "__main__":
    x = Gui()

#a = subprocess.Popen(["python", "gui.py", "0,1,3,4,5,6,7","8","100","0"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)


#def wiringPiFailure(*args):
#def wiringPiFindNode(*args):
#def wiringPiNewNode(*args):
#def pinModeAlt(*args):
#def pullUpDnControl(*args):
#def digitalRead(*args):
#def pwmWrite(*args):
#def analogRead(*args):
#def analogWrite(*args):
#def piBoardRev():
#def piBoardId(*args):
#def wpiPinToGpio(*args):
#def physPinToGpio(*args):
#def setPadDrive(*args):
#def getAlt(*args):
#def pwmToneWrite(*args):
#def digitalWriteByte(*args):
#def pwmSetMode(*args):
#def pwmSetRange(*args):
#def pwmSetClock(*args):
#def gpioClockSet(*args):
#def waitForInterrupt(*args):
#def wiringPiISR(*args):
#def piThreadCreate(*args):
#def piLock(*args):
#def piUnlock(*args):
#def piHiPri(*args):
#def delay(*args):
#def delayMicroseconds(*args):
#def millis():
#def micros():
#def ds1302rtcRead(*args):
#def ds1302rtcWrite(*args):
#def ds1302ramRead(*args):
#def ds1302ramWrite(*args):
#def ds1302clockRead(*args):
#def ds1302clockWrite(*args):
#def ds1302trickleCharge(*args):
#def ds1302setup(*args):
#def gertboardAnalogWrite(*args):
#def gertboardAnalogRead(*args):
#def gertboardSPISetup():
#def gertboardAnalogSetup(*args):
#def lcd128x64setOrigin(*args):
#def lcd128x64setOrientation(*args):
#def lcd128x64orientCoordinates(*args):
#def lcd128x64getScreenSize(*args):
#def lcd128x64point(*args):
#def lcd128x64line(*args):
#def lcd128x64lineTo(*args):
#def lcd128x64rectangle(*args):
#def lcd128x64circle(*args):
#def lcd128x64ellipse(*args):
#def lcd128x64putchar(*args):
#def lcd128x64puts(*args):
#def lcd128x64update():
#def lcd128x64clear(*args):
#def lcd128x64setup():
#def lcdHome(*args):
#def lcdClear(*args):
#def lcdDisplay(*args):
#def lcdCursor(*args):
#def lcdCursorBlink(*args):
#def lcdSendCommand(*args):
#def lcdPosition(*args):
#def lcdCharDef(*args):
#def lcdPutchar(*args):
#def lcdPuts(*args):
#def lcdPrintf(*args):
#def lcdInit(*args):
#def piFaceSetup(*args):
#def piGlow1(*args):
#def piGlowLeg(*args):
#def piGlowRing(*args):
#def piGlowSetup(*args):
#def setupNesJoystick(*args):
#def readNesJoystick(*args):
#def drcSetupSerial(*args):
#def max31855Setup(*args):
#def max5322Setup(*args):
#def mcp3002Setup(*args):
#def mcp3004Setup(*args):
#def mcp3422Setup(*args):
#def mcp4802Setup(*args):
#def pcf8574Setup(*args):
#def pcf8591Setup(*args):
#def sn3218Setup(*args):
#def softPwmStop(*args):
#def softServoWrite(*args):
#def softServoSetup(*args):
#def softToneCreate(*args):
#def softToneStop(*args):
#def softToneWrite(*args):
#def wiringPiSPIGetFd(*args):
#def wiringPiSPIDataRW(*args):
#def wiringPiSPISetup(*args):
#def wiringPiI2CRead(*args):
#def wiringPiI2CReadReg8(*args):
#def wiringPiI2CReadReg16(*args):
#def wiringPiI2CWrite(*args):
#def wiringPiI2CWriteReg8(*args):
#def wiringPiI2CWriteReg16(*args):
#def wiringPiI2CSetupInterface(*args):
#def wiringPiI2CSetup(*args):
#def serialOpen(*args):
#def serialClose(*args):
#def serialFlush(*args):
#def serialPutchar(*args):
#def serialPuts(*args):
#def serialPrintf(*args):
#def serialDataAvail(*args):
#def serialGetchar(*args):
#def shiftIn(*args):
#def shiftOut(*args):
