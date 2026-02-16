#!/usr/bin/env python3

# Photo Booth Script

import RPi.GPIO as GPIO
import time
import os
import logging
import picamera
import pygame
import datetime
import PIL.Image
from PIL import Image
from pygame.locals import *

from config import load_config, save_config, resolve_path
from settings_gui import run_settings
from printer import Printer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s: %(message)s',
)

# Constants
SCREEN_W = 800
SCREEN_H = 480
THUMB_W = 720
THUMB_H = 540
GP_BUTTON = 15
GP_LED = 13  # Ready indicator LED — lit when booth is waiting for input

# GPIO setup — may fail if hardware is absent or permissions are wrong
gpio_available = False
led_available = False
try:
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(GP_BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(GP_LED, GPIO.OUT)
    GPIO.output(GP_LED, GPIO.LOW)  # Start with LED off until booth is ready
    gpio_available = True
    led_available = True
except Exception as e:
    logging.warning("GPIO init failed: %s — touchscreen mode will be used", e)

# --- Step 1: Settings GUI (Tkinter, before pygame) ---
config = run_settings()

# --- Step 2: Init pygame ---
pygame.mixer.pre_init(44100, -16, 1, 1024 * 3)
pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.FULLSCREEN)
surface = pygame.image.load(resolve_path(config['display']['screen_image']))
surface = pygame.transform.scale(surface, (SCREEN_W, SCREEN_H))
background = surface.convert()

# --- Step 3: Init camera ---
camera = picamera.PiCamera()
camera.vflip = False
camera.hflip = True
camera.brightness = 45
camera.exposure_compensation = 6
camera.contrast = 8

# --- Step 4: Init printer ---
booth_printer = Printer(
    max_retries=config['printing']['max_retries'],
    retry_delay=config['printing']['retry_delay'],
)

# Session folder
foldername = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


#########################################
# LED control


def led_on():
    """Turn on the ready indicator LED."""
    if led_available:
        try:
            GPIO.output(GP_LED, GPIO.HIGH)
        except Exception:
            pass


def led_off():
    """Turn off the ready indicator LED."""
    if led_available:
        try:
            GPIO.output(GP_LED, GPIO.LOW)
        except Exception:
            pass


def led_sos():
    """Flash SOS in Morse code: ··· ––– ···"""
    if not led_available:
        return
    dot = 0.15
    dash = 0.45
    gap = 0.15      # gap between signals
    letter_gap = 0.3  # gap between letters

    for pattern in ([dot] * 3, [dash] * 3, [dot] * 3):
        for duration in pattern:
            led_on()
            time.sleep(duration)
            led_off()
            time.sleep(gap)
        time.sleep(letter_gap)


#########################################
# Diagnostics


def test_gpio():
    """
    Test the GPIO button pin at startup.

    Reads the pin 10 times over 0.5 seconds. A healthy button with pull-up
    should read HIGH every time (nobody is pressing it at startup). If the
    pin is stuck LOW (shorted, disconnected, or wiring fault) or throws
    an exception, GPIO is marked unavailable and the booth falls back to
    touchscreen input.

    Returns True if GPIO button looks healthy, False otherwise.
    """
    global gpio_available

    if not gpio_available:
        return False

    stuck_low_count = 0
    try:
        for _ in range(10):
            if GPIO.input(GP_BUTTON) == False:
                stuck_low_count += 1
            time.sleep(0.05)
    except Exception as e:
        logging.warning("GPIO read failed during test: %s", e)
        gpio_available = False
        return False

    if stuck_low_count >= 8:
        # Pin is stuck LOW — button wiring is likely faulty
        logging.warning(
            "GPIO button stuck LOW (%d/10 reads) — switching to touchscreen mode",
            stuck_low_count,
        )
        gpio_available = False
        return False

    logging.info("GPIO button test passed (%d/10 LOW reads)", stuck_low_count)
    return True


#########################################
# Functions


def UpdateDisplay(Message, SmallText=None):
    """Render message text and banner text onto the screen background."""
    if SmallText is None:
        SmallText = config['display']['banner_text']

    text_color = tuple(config['display']['text_color'])
    local_screen = background.copy()

    smallfont = pygame.font.Font(None, 50)
    rendered_small = smallfont.render(SmallText, 1, text_color)
    local_screen.blit(rendered_small, (10, 445))

    if Message != "":
        font = pygame.font.Font(None, 180)
        text = font.render(Message, 1, text_color)
        textpos = text.get_rect()
        textpos.centerx = background.get_rect().centerx
        textpos.centery = background.get_rect().centery
        local_screen.blit(text, textpos)

    screen.blit(local_screen, (0, 0))
    pygame.display.flip()


def check_paper():
    """Check if paper is available via counter and printer status."""
    images_printed = config['state']['images_printed']
    tray_count = config['printing']['paper_tray_count']
    bundles = config['state']['paper_bundles_loaded']

    if images_printed >= tray_count * bundles:
        return False

    return booth_printer.check_paper_status()


def outofpaper():
    """Display out-of-paper message with SOS LED. Space to reload, Escape to quit."""
    camera.stop_preview()
    led_off()
    UpdateDisplay("Out of Paper!", "Press SPACE after loading paper")

    while not check_paper():
        # Flash SOS (~3.6s) then pause (~26s) for a 30s cycle
        led_sos()

        # Wait 26 seconds, checking for input every 0.5s so spacebar is responsive
        for _ in range(52):
            for event in pygame.event.get():
                if event.type == QUIT:
                    return
                elif event.type == KEYDOWN:
                    if event.key == K_SPACE:
                        config['state']['paper_bundles_loaded'] += 1
                        save_config(config)
                        print("Paper tray was reloaded")
                    if event.key == K_ESCAPE:
                        print("Ending because ESCAPE key was pressed")
                        pygame.quit()
                        exit(0)
            if check_paper():
                return
            time.sleep(0.5)


def waitingforbutton():
    """Wait for button press, screen tap, or keyboard input. Shows camera preview."""
    if not check_paper():
        outofpaper()

    led_on()  # Light up — booth is ready

    if gpio_available:
        prompt = "Press the button!"
        pygame.mouse.set_visible(0)
    else:
        prompt = "Tap the screen!"
        pygame.mouse.set_visible(1)

    camera.start_preview(
        alpha=150,
        fullscreen=False,
        window=(12, 12, SCREEN_W - 24, SCREEN_H - 12),
    )

    loopct = 0
    while loopct < 150:
        loopct += 1
        if loopct < 10:
            Message = "Ready"
        else:
            Message = " "

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
            elif event.type == MOUSEBUTTONDOWN:
                # Touchscreen tap — always accepted as fallback
                buttonpressed()
                loopct = 100000

        if gpio_available and GPIO.input(GP_BUTTON) == False:
            buttonpressed()
            loopct = 100000

        UpdateDisplay(Message, prompt)
        time.sleep(0.2)


def instructions():
    """Show pre-capture instruction messages."""
    UpdateDisplay("Get Ready")
    time.sleep(1)
    UpdateDisplay("4 Pictures")
    time.sleep(1)
    UpdateDisplay("Will be taken")
    time.sleep(1)


def buttonpressed():
    """Handle button press: show instructions then take pictures."""
    led_off()  # LED off during capture and printing
    instructions()
    takepictures()


def countdown(text):
    """5-second countdown with beep sound."""
    pygame.mixer.music.load(resolve_path('beep.mp3'))
    for i in range(5, 0, -1):
        pygame.mixer.music.play(0)
        UpdateDisplay(str(i), text)
        time.sleep(0.75)


def take_picture(img, sub):
    """Capture a single photo, return PIL Image (flipped)."""
    filename = "image%d_%d.jpg" % (img, sub)
    UpdateDisplay("SMILE!")
    time.sleep(0.75)
    pygame.mixer.music.load(resolve_path('camera.mp3'))
    pygame.mixer.music.play(0)
    camera.capture(os.path.join(foldername, filename))
    return PIL.Image.open(
        os.path.join(foldername, filename)
    ).transpose(Image.FLIP_LEFT_RIGHT)


def takepictures():
    """Take 4 pictures, composite onto template, and print."""
    camera.resolution = (1440, 1080)
    images = []
    picture_labels = [
        "Picture Number One",
        "Picture Number Two",
        "Picture Number Three",
        "Last Picture",
    ]

    img_number = config['state']['images_printed'] + 1

    for sub in range(4):
        UpdateDisplay("Get Ready!", picture_labels[sub])
        time.sleep(2)
        countdown(picture_labels[sub])
        images.append(take_picture(img_number, sub))

    # Load the template and composite the 4 photos
    template_path = resolve_path(config['printing']['template_image'])
    bgimage = PIL.Image.open(template_path)

    for x in range(4):
        images[x].thumbnail((THUMB_W, THUMB_H))

    bgimage.paste(images[0], (40, 40))
    bgimage.paste(images[1], (40, 620))
    bgimage.paste(images[2], (1040, 40))
    bgimage.paste(images[3], (1040, 620))

    Final_Image_Name = os.path.join(foldername, "Final_%d.jpg" % img_number)
    bgimage.save(Final_Image_Name)

    # Print with status updates on screen
    camera.stop_preview()

    def on_print_status(msg):
        UpdateDisplay(msg)

    success = booth_printer.print_file(
        os.path.abspath(Final_Image_Name),
        on_status=on_print_status,
    )

    if success:
        config['state']['images_printed'] += 1
        save_config(config)
        UpdateDisplay("Done!")
        time.sleep(2)
    else:
        UpdateDisplay("Print Failed!", "Press button to try again")
        time.sleep(3)


##############################################################################

# Create session folder
if not os.path.exists(foldername):
    os.mkdir(foldername)

# Startup welcome messages
UpdateDisplay("Welcome!")
time.sleep(5)
UpdateDisplay("to the")
time.sleep(1.75)
UpdateDisplay("PhotoBooth!")
time.sleep(3.5)
UpdateDisplay("Loading...")
time.sleep(0.75)

# --- Step 6: Diagnostics ---
UpdateDisplay("Testing...", "Checking hardware")
time.sleep(0.5)
test_gpio()

if gpio_available:
    # Flash the LED 3 times to confirm it works
    for _ in range(3):
        led_on()
        time.sleep(0.2)
        led_off()
        time.sleep(0.2)
    UpdateDisplay("Button OK", "GPIO test passed")
else:
    UpdateDisplay("No Button", "Using touchscreen mode")
time.sleep(2)

# Main loop
waitingforbutton()
while True:
    print("Loop cycle - restarting waitingforbutton")
    waitingforbutton()
