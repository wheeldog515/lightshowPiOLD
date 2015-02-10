# !/usr/bin/env python
#
# Licensed under the BSD license.  See full license in LICENSE file.
# http://www.lightshowpi.com/
#
# Author: Tom Enos

from math import ceil
import Tkinter

gpio = list()
state = list()

# on screen position of the tkinter window
# 0,0 top left corner
screen_x = 0
screen_y = 0

# radius of lights
rad = 20

# x and y of the first light inside the tkinter window
x = rad * 2
y = rad * 2

# lights are evenly spaced by half the radius
spacing = (rad * 2) + (rad / 2)

# How many lights in a row
max_row_length = 16


red = "#FF0000"
green = "#00FF00"
blue = "#0000FF"
white = "#FFFFFF"
black = "#000000"


def ui(gpins, glen, pmax, gactive):
    """
    
    """
    global parent, canvas, gpio_pins, gpiolen, pwm_max, gpioactive
    
    gpio_pins = gpins
    gpiolen = glen
    pwm_max = pmax
    gpioactive = gactive
    
    parent = Tkinter.Tk()    
    
    row_length = gpiolen

    if gpiolen > max_row_length:
        row_length = max_row_length

    # calculate number of rows
    rows = int(ceil(gpiolen / row_length))

    # size of the window
    width = (row_length * spacing) + int((rad * 1.75))
    height = (rows * spacing) + int(rad * 1.75)
    
    parent.geometry('{0:d}x{1:d}+{2:d}+{3:d}'.format(width, height, screen_x, screen_y))
    parent.title("Lights")        
    parent.protocol("WM_DELETE_WINDOW", quit)
    canvas = Tkinter.Canvas(parent)

    x1, y1 = x, y
    
    counter = row_counter = 0
    
    while counter < gpiolen:
        top_left = x1 - rad
        bottom_left = y1 - rad
        top_right = x1 + rad
        bottom_right = y1 + rad
        
        gpio.append(canvas.create_oval(top_left, 
                                       bottom_left, 
                                       top_right, 
                                       bottom_right, 
                                       fill="#FFFFFF"))

        x1 += spacing
        row_counter += 1

        if row_counter == row_length:
            x1 = x
            y1 += spacing
            row_counter = 0
        counter += 1

    canvas.pack(fill=Tkinter.BOTH, expand=1)
    
    parent.mainloop()


def null_function():
    """
    does nothing, callback for WM_DELETE_WINDOW to prevent window close
    """
    pass

def quit():
    """
    exit the gui
    """
    if 'normal' == parent.state():
        parent.destroy()
        
def softPwmWrite(gpin, brightness):
    """
    
    :param gpin, int, to be used as index of gpio pin to use
    :param birghtness, int, brightness of light
    """
    try:
        pin = gpio_pins.index(gpin)
        if gpioactive:
            brightness = 100 - brightness
        level = '#{0:02X}{1:02X}{2:02X}'.format(255, int(ceil(brightness * 2.55)), int(ceil(brightness * 2.55)))
        canvas.itemconfig(gpio[pin], fill=level)
        parent.update()
    except:
        pass

def digitalWrite(gpin, onoff):
    """
    
    :param gpin, int, to be used as index of gpio pin to use
    :param onoff, on or off
    """
    try:
        pin = gpio_pins.index(gpin)
        if gpioactive:
            onoff = 1 - onoff
        canvas.itemconfig(gpio[pin], fill=(blue, white)[onoff])
        parent.update()
    except:
        pass

# Empty functions, most will remain empty as they are not needed
# but we can implement any that are needed in the future.
def wiringPiSetup():
    """Empty function"""
    pass

#def wiringPiSetupSys():
#def wiringPiSetupGpio():
#def wiringPiSetupPhys():

def softPwmCreate(*agrs):
    """Empty function"""
    pass


def pinMode(*agrs):
    """Empty function"""
    pass


def mcp23017Setup(*agrs):
    """Empty function"""
    pass


def mcp23s17Setup(*agrs):
    """Empty function"""
    pass


def mcp23016Setup(*agrs):
    """Empty function"""
    pass


def mcp23008Setup(*agrs):
    """Empty function"""
    pass


def mcp23s08Setup(*agrs):
    """Empty function"""
    pass


def pcf8574Setup(*agrs):
    """Empty function"""
    pass


def sr595Setup(*agrs):
    """Empty function"""
    pass


def softPwmCreate(*agrs):
    """Empty function"""
    pass


def pinMode(*agrs):
    """Empty function"""
    pass


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
