#!/usr/bin/env python


# Photo Booth Script


##Imports
import RPi.GPIO as GPIO
import time
import os
import picamera
import pygame
import datetime
import PIL.Image
import cups
from PIL import Image

#from threading import Thread
from pygame.locals import *
from time import sleep


#Define PIR GPIO
#Tell it to use Board Layout
GPIO.setmode(GPIO.BOARD)

GP_BUTTON = 15
GP_PIR = 19

#Setup Button GPIO to read
GPIO.setup(GP_BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)

#initialise global variables
Message = ""  # Message is a fullscreen message
SmallText = ""  # SmallMessage is a lower banner message
global imagecounter
global papertraycount
papertraycount = 18
imagecounter = 0

foldername = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

pygame.font.init()
# Dimensions (pixels)
SCREEN_W = 800
SCREEN_H = 480
THUMB_W = 720
THUMB_H = 540
COUNTDOWN_LOCATION = (400, 240)
## reserved room at bottom for countdown (Not used so set to 0)
BOTTOM_RESERVE = 0
# Colors
WHITE = (255, 255, 255)
RED = (255, 0, 0)
BLACK = (0, 0, 0)

N_COUNTDOWN = 5


camera = picamera.PiCamera()

#initialise pygame
pygame.mixer.pre_init(44100, -16, 1, 1024*3)  # PreInit Music, plays faster
pygame.init()  # Initialise pygame
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.FULLSCREEN)
background = pygame.Surface(screen.get_size())  # Create the background object
background = background.convert()  # Convert it to a background


#########################################
##Functions


def startup():
    if not os.path.exists(foldername):
        os.mkdir(foldername)

    Message = "Welcome!"
    UpdateDisplay(Message)
    time.sleep(5)

    Message = "to the"
    UpdateDisplay(Message)
    time.sleep(1.75)

    Message = "PhotoBooth!"
    UpdateDisplay(Message)
    time.sleep(3.5)

    #Initialise the camera object
    camera.vflip = False
    camera.hflip = True
    #camera.rotation = 90
    camera.brightness = 45
    camera.exposure_compensation = 6
    camera.contrast = 8
    camera.resolution = (THUMB_W, THUMB_H)

    Message = "Loading..."
    UpdateDisplay(Message)
    time.sleep(.75)
    return


#UpdateDisplay - Thread to update the display, neat generic procedure
def UpdateDisplay(Message, SmallText="Jesse & Brittany's Wedding"):
    #init global variables from main thread
    global TotalImageCount
    global screen
    global background
    global pygame

    background.fill(pygame.Color("black"))  # Black background
    smallfont = pygame.font.Font(None, 50)  # Small font for banner message
    SmallText = smallfont.render(SmallText, 1, (255, 0, 0))
    background.blit(SmallText, (10, 445))  # Write the small text

    if(Message != ""):  # If the big message exits write it
        font = pygame.font.Font(None, 180)
        text = font.render(Message, 1, (255, 0, 0))
        textpos = text.get_rect()
        textpos.centerx = background.get_rect().centerx
        textpos.centery = background.get_rect().centery
        background.blit(text, textpos)

    screen.blit(background, (0, 0))
    # Draw the red outer box
    pygame.draw.rect(screen, pygame.Color("red"), (10, 10, SCREEN_W-10, SCREEN_H-10), 2)
    pygame.display.flip()

    return


def outofpaper():
    Message = "Out of Paper!"
    SmallText = "Better go tell Andrew"
    camera.stop_preview()
    UpdateDisplay(Message, SmallText)
    while True:
        for event in pygame.event.get():
            if event.type == QUIT:
                return
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    loopct = 0
                    while loopct < 50:
                        loopct += 1
                        print("Ending because ESCAPE key was pressed")
                    pygame.quit()
                    exit(0)


def waitingforbutton():
    #Check number of prints is less then PaperTrayCount
    if imagecounter > papertraycount:
        outofpaper()

    pygame.mouse.set_visible(0)
    
    camera.start_preview(alpha=150,
                         fullscreen=False,
                         window=(12,12, SCREEN_W-24, SCREEN_H - 12 - BOTTOM_RESERVE))

    # Start checking for button press every .2 seconds
    #  for 30 seconds or a loop of 150
    loopct = 0
    while loopct < 150:
        loopct += 1
        if loopct < 10:
            Message = "Ready"
            SmallText = "Press the button!"
        else:
            Message = str(loopct)
            Message = " "
            SmallText = "Press the button!"

        for event in pygame.event.get():
            if event.type == QUIT:
                return
            elif event.type == KEYDOWN:
                if event.key == K_DOWN:
                    buttonpressed()
                    loopct = 100000
                if event.key == K_ESCAPE:
                    print("Ending because ESCAPE key was pressed")
                    pygame.quit()
                    exit(0)
        if GPIO.input(GP_BUTTON) == False:
            buttonpressed()
            loopct = 100000
        UpdateDisplay(Message, SmallText)
        time.sleep(.2)

def instructions():
    Message = "Get Ready"
    UpdateDisplay(Message)
    time.sleep(1)
    Message = "4 Pictures"
    UpdateDisplay(Message)
    time.sleep(1)
    Message = "Will be taken"
    UpdateDisplay(Message)
    time.sleep(1)


def buttonpressed():
    instructions()
    takepictures()


def printingmessage():
    loopcount = 0
    while loopcount < 12:
        loopcount += 1
        os.system("sudo /home/pi/photoBooth/restart_print.sh")
        Message = "Printing..."

        UpdateDisplay(Message)
        time.sleep(1.5)
        Message = "Do not pull"

        UpdateDisplay(Message)
        time.sleep(.75)
        Message = "Picture"

        UpdateDisplay(Message)
        time.sleep(.75)
        Message = "wait for it"

        UpdateDisplay(Message)
        time.sleep(.75)
        Message = "to finish!"

        UpdateDisplay(Message)
        time.sleep(.75)


def printpicture(picture):
    # Connect to cups and select printer 0
    Message = "Preparing to print..."

    UpdateDisplay(Message)
    #os.system("sudo service cups stop")
    #os.system("sudo service cups start")
    conn = cups.Connection()
    printers = conn.getPrinters()
    printer_name = next(iter(printers.keys()))
    conn.printFile(printer_name, picture, "PhotoBooth", {})
    camera.stop_preview()
    printingmessage()


def countdown(text):
    countdownct = 5
    pygame.mixer.music.load('beep.mp3')
    while countdownct > 0:
        Message = str(countdownct)
        pygame.mixer.music.play(0)
        UpdateDisplay(Message, text)
        time.sleep(.75)
        countdownct -= 1


def take_picture(img, sub):
    filename = "image%d_%d.jpg" % (img, sub)
    Message = "SMILE!"
    UpdateDisplay(Message)
    time.sleep(.75)
    pygame.mixer.music.load('camera.mp3')
    pygame.mixer.music.play(0)
    camera.capture(os.path.join(foldername, filename))
    return PIL.Image.open(
        os.path.join(foldername, filename)).transpose(Image.FLIP_LEFT_RIGHT)


def takepictures():
    global imagecounter
    camera.resolution = (1440, 1080)
    images = []
    imagecounter += 1
    for sub in range(4):
        Message = "Get Ready!"
        smalltext = "Picture Number One"
        if sub == 1:
            smalltext = "Picture Number Two"
        elif sub == 2:
            smalltext = "Picture Number Three"
        elif sub == 3:
            smalltext = "Last Picture"
        UpdateDisplay(Message, smalltext)
        time.sleep(2)
        countdown(smalltext)
        images.append(take_picture(imagecounter, sub))

    #Load the background template
    #1800 x 1200
    bgimage = PIL.Image.open("/home/pi/photoBooth/template.jpg")

    # #thumbnail the 4 images
    for x in range(4):
        images[x].thumbnail((720, 540))

    # paste the thumbnails to the background images
    bgimage.paste(images[0], (40, 40))
    bgimage.paste(images[1], (40, 620))
    bgimage.paste(images[2], (1040, 40))
    bgimage.paste(images[3], (1040, 620))
    # Create the final filename
    Final_Image_Name = os.path.join(
        foldername, "Final_%d.jpg" % (imagecounter))
    # Save the final image
    bgimage.save(Final_Image_Name)

    printpicture(Final_Image_Name)


##############################################################################


#startup
startup()


#Make a loop that always runs
while True:
    print("A loop cycle has been run - If you see this the program crashed")
    waitingforbutton()
    #time.sleep(.2)




