#!/usr/bin/env python3
#----------------------------------------------------------------------------
# Copyright (c) 2018 FIRST. All Rights Reserved.
# Open Source Software - may be modified and shared by FRC teams. The code
# must be accompanied by the FIRST BSD license file in the root directory of
# the project.
#----------------------------------------------------------------------------

import json
import time
import sys

from cscore import CameraServer, VideoSource, UsbCamera, MjpegServer
from networktables import NetworkTablesInstance
import ntcore

# New code to analyze video stream
from imutils.video import VideoStream
import cv2
import numpy, math
import imutils
from collections import deque
import RPi.GPIO as GPIO
# For PCA9685
# sudo raspi-config
# Select 5 Interfacing Options and then  P5 I2C.
from PCA9685 import PCA9685
# pip3 install simple-pid
from simple_pid import PID
import RPi.GPIO as GPIO

DISABLE_PID = True
DISABLE_PID = True

# sudo apt-get install python3-pantilthat


#   JSON format:
#   {
#       "team": <team number>,
#       "ntmode": <"client" or "server", "client" if unspecified>
#       "cameras": [
#           {
#               "name": <camera name>
#               "path": <path, e.g. "/dev/video0">
#               "pixel format": <"MJPEG", "YUYV", etc>   // optional
#               "width": <video mode width>              // optional
#               "height": <video mode height>            // optional
#               "fps": <video mode fps>                  // optional
#               "brightness": <percentage brightness>    // optional
#               "white balance": <"auto", "hold", value> // optional
#               "exposure": <"auto", "hold", value>      // optional
#               "properties": [                          // optional
#                   {
#                       "name": <property name>
#                       "value": <property value>
#                   }
#               ],
#               "stream": {                              // optional
#                   "properties": [
#                       {
#                           "name": <stream property name>
#                           "value": <stream property value>
#                       }
#                   ]
#               }
#           }
#       ]
#       "switched cameras": [
#           {
#               "name": <virtual camera name>
#               "key": <network table key used for selection>
#               // if NT value is a string, it's treated as a name
#               // if NT value is a double, it's treated as an integer index
#           }
#       ]
#   }
cvCamera = None
configFile = "/boot/frc.json"
class CameraConfig: pass

team = None
server = False
cameraConfigs = []
switchedCameraConfigs = []
cameras = []
cameraInst = None
cvSink = None

laserPIN = 12

def parseError(str):
    """Report parse error."""
    print("config error in '" + configFile + "': " + str, file=sys.stderr)

def readCameraConfig(config):
    """Read single camera configuration."""
    cam = CameraConfig()

    # name
    try:
        cam.name = config["name"]
    except KeyError:
        parseError("could not read camera name")
        return False

    # path
    try:
        cam.path = config["path"]
    except KeyError:
        parseError("camera '{}': could not read path".format(cam.name))
        return False

    # stream properties
    cam.streamConfig = config.get("stream")

    cam.config = config

    cameraConfigs.append(cam)
    return True

def readSwitchedCameraConfig(config):
    """Read single switched camera configuration."""
    cam = CameraConfig()

    # name
    try:
        cam.name = config["name"]
    except KeyError:
        parseError("could not read switched camera name")
        return False

    # path
    try:
        cam.key = config["key"]
    except KeyError:
        parseError("switched camera '{}': could not read key".format(cam.name))
        return False

    switchedCameraConfigs.append(cam)
    return True

def readConfig():
    """Read configuration file."""
    global team
    global server

    # parse file
    try:
        with open(configFile, "rt", encoding="utf-8") as f:
            j = json.load(f)
    except OSError as err:
        print("could not open '{}': {}".format(configFile, err), file=sys.stderr)
        return False

    # top level must be an object
    if not isinstance(j, dict):
        parseError("must be JSON object")
        return False

    # team number
    try:
        team = j["team"]
    except KeyError:
        parseError("could not read team number")
        return False

    # ntmode (optional)
    if "ntmode" in j:
        str = j["ntmode"]
        if str.lower() == "client":
            server = False
        elif str.lower() == "server":
            server = True
        else:
            parseError("could not understand ntmode value '{}'".format(str))

    # cameras
    try:
        cameras = j["cameras"]
    except KeyError:
        parseError("could not read cameras")
        return False
    for camera in cameras:
        if not readCameraConfig(camera):
            return False

    # switched cameras
    if "switched cameras" in j:
        for camera in j["switched cameras"]:
            if not readSwitchedCameraConfig(camera):
                return False

    return True

def startCamera(config):
    """Start running the camera."""
    global cameraInst
    print("Starting camera '{}' on {}".format(config.name, config.path))
    cameraInst = CameraServer.getInstance()
    camera = UsbCamera(config.name, config.path)
    cameraI = cameraInst.startAutomaticCapture(camera=camera, return_server=True)

    camera.setConfigJson(json.dumps(config.config))
    camera.setConnectionStrategy(VideoSource.ConnectionStrategy.kKeepOpen)

    if config.streamConfig is not None:
        cameraI.setConfigJson(json.dumps(config.streamConfig))

    return camera

def startSwitchedCamera(config):
    """Start running the switched camera."""
    print("Starting switched camera '{}' on {}".format(config.name, config.key))
    server = CameraServer.getInstance().addSwitchedCamera(config.name)

    def listener(fromobj, key, value, isNew):
        if isinstance(value, float):
            i = int(value)
            if i >= 0 and i < len(cameras):
              server.setSource(cameras[i])
        elif isinstance(value, str):
            for i in range(len(cameraConfigs)):
                if value == cameraConfigs[i].name:
                    server.setSource(cameras[i])
                    break

    NetworkTablesInstance.getDefault().getEntry(config.key).addListener(
        listener,
        ntcore.constants.NT_NOTIFY_IMMEDIATE |
        ntcore.constants.NT_NOTIFY_NEW |
        ntcore.constants.NT_NOTIFY_UPDATE)

    return server

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        configFile = sys.argv[1]

    # read configuration
    if not readConfig():
        sys.exit(1)

    # start NetworkTables
    ntinst = NetworkTablesInstance.getDefault()
    if server:
        print("Setting up NetworkTables server")
        ntinst.startServer()
    else:
        print("Setting up NetworkTables client for team {}".format(team))
        ntinst.startClientTeam(team)

    # start cameras
    for config in cameraConfigs:
        print("camera")
        cameras.append(startCamera(config))

    # start switched cameras
    for config in switchedCameraConfigs:
        print("switched")
        startSwitchedCamera(config)

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(laserPIN, GPIO.OUT)

    pwm = PCA9685()
    pwm.setPWMFreq(50)
    panAddress = 0
    tiltAddress = 1
    minPan = 70
    maxPan = 180
    panRange = (maxPan-minPan)/2
    centerPan = (minPan+maxPan)/2
    upTilt = 70
    downTilt = 180
    tiltRange = (downTilt-upTilt)/2
    centerTilt = (upTilt+downTilt)/2

    # for j in range(1):
    #     while(i < maxPan):
    #         i = i + 1
    #         pwm.setRotationAngle(panAddress, i)
    #         time.sleep(0.01)
    #     while(i > minPan):
    #         i = i - 1
    #         pwm.setRotationAngle(panAddress, i)
    #         time.sleep(0.01)
    #
    # pwm.setRotationAngle(panAddress, (minPan+maxPan)/2)
    # pwm.setRotationAngle(tiltAddress, (minTilt+maxTilt)/2)
    #
    # for j in range(1):
    #     for i in range(minTilt,maxTilt,1):
    #         pwm.setRotationAngle(tiltAddress, i)
    #         time.sleep(0.01)
    #     for i in range(maxTilt,minTilt,-1):
    #         pwm.setRotationAngle(tiltAddress, i)
    #         time.sleep(0.01)

    pwm.setRotationAngle(panAddress, centerPan) # centerPan)
    pwm.setRotationAngle(tiltAddress, upTilt + 20) # centerTilt)

    panPid = PID(Kp=0.05, Ki=0.2, Kd=0.0,
                 setpoint=320, # pan is in the x direction so half the horizontal resolution
                 sample_time=0.01,
                 output_limits=(-panRange, panRange))
    tiltPid = PID(Kp=0.05, Ki=0.2, Kd=0.0,
                  setpoint=240,  # tilt is in the y direction so half the vertical resolution
                  sample_time=0.01,
                  output_limits=(-tiltRange, tiltRange))

    # Allocating new images is very expensive, always try to preallocate
    img = numpy.zeros(shape=(480, 640, 3), dtype=numpy.uint8)
    blurred = numpy.zeros(shape=(480, 640, 3), dtype=numpy.uint8)
    hsv = numpy.zeros(shape=(480, 640, 3), dtype=numpy.uint8)
    # grey = numpy.zeros(shape=(480, 640, 1), dtype=numpy.uint8)
    # if no parameter is passed, gets OpenCV access to the primary camera feed
    cvSink = cameraInst.getVideo()

    # Creates the CvSource and MjpegServer [2] and connects them
    outputStream = cameraInst.putVideo("Tracking", 640, 480)

    detector = cv2.CascadeClassifier()
    # construct a range of colors of our ball,
    # this sets a minimum and maximum range in HSV space and makes it white
    # and makes everything else white.  This mask is much easier to identify
    # features in the image
    greenLower = (73, 91, 52)   # (h, s, v)
    greenUpper = (82, 218, 255)
    # Note: h (hue) is normally 0 to 359 on the color wheel but OpenCV uses 0 to 179,
    # s (saturation) is normally 0 to 100 but 255 in OpenCV,
    # v (value) also is normally 0 to 100 but 255 in OpenCV

    # We want to create a queue to more easily manage our list of pts for displaying a trail
    # pts = deque(maxlen = 50)

    sequenceNumber = 1
    # loop forever
    while True:
        frameTime, img = cvSink.grabFrame(img)
        if frameTime == 0:
            print("zero time error")
            continue
        else:
            # We want to blur the image do reduce noise to improve the HSV space conversion
            # https://docs.opencv.org/master/d4/d13/tutorial_py_filtering.html
            blurred = cv2.GaussianBlur(img, (11, 11), 0)
            hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
            # create a black and white bitmap (not greyscale) version that shows
            # pixels that match the color range
            mask = cv2.inRange(hsv, greenLower, greenUpper)
            # a series of dilations and erosions
            # erosions do a 3x3 moving matrix that replaces the center with the minimum
            mask = cv2.erode(mask, None, iterations=2)
            # dilations do a 3x3 moving matrix that replaces the center with the maximum
            mask = cv2.dilate(mask, None, iterations=2)
            # the above removes any small blobs left in the mask
            # https://docs.opencv.org/2.4/doc/tutorials/imgproc/erosion_dilatation/erosion_dilatation.html

            # Now find contours in the mask we created and initialize the current
            # (x, y) center of the contour
            # https://docs.opencv.org/3.4/d4/d73/tutorial_py_contours_begin.html
            cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)
            cnts = imutils.grab_contours(cnts)

            for c in cnts:
                # find the largest contour in the mask, then use
                # it to compute the minimum enclosing circle and
                # centroid
                # minArea = 0 # Does it help to clear this?
                # c = max(cnts, key=cv2.contourArea)
                storage = None
                minArea = cv2.minAreaRect2(c, storage)
                # to find the centroid (center) of the identified blob we
                # will use the calculated moments where x = m10/m00 and
                # and y is m01/m00
                # https://www.learnopencv.com/find-center-of-blob-centroid-using-opencv-cpp-python/
                M = cv2.moments(c)
                center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

                # only proceed if the minArea meets a minimum size
                if minArea > 10:
                    # draw a circle the circle and centroid on the frame,
                    circleColor = (0, 255, 17)  # TODO verify, I think it is B, G, R
                    thickness = 2
                    shift = 0
                    lineType=8
                    cv2.rectangle(img, (int(x), int(y)),
                               circleColor, thickness, lineType, shift)

                    # then update the list of tracked points
                    # circleColor = (0, 0, 255)
                    # thickness = -1 # -1 is filled
                    # cv2.circle(frame, center, 5, circleColor, thickness)

            # convert it to grayscale
            # gray = mask[:,:,2] # We want to only keep the v channel

            center = None
            # only update the trail a contour was found
            if len(cnts) > 0:
                # find the largest contour in the mask, then use
                # it to compute the minimum enclosing circle and
                # centroid
                # minArea = 0 # Does it help to clear this?
                c = max(cnts, key=cv2.contourArea)
                minArea = cv2.minAreaRect2(c, storage)
                # to find the centroid (center) of the identified blob we
                # will use the calculated moments where x = m10/m00 and
                # and y is m01/m00
                # https://www.learnopencv.com/find-center-of-blob-centroid-using-opencv-cpp-python/
                M = cv2.moments(c)
                center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

                # only proceed if the minArea meets a minimum size
                if minArea > 10:
                    # draw a circle the circle and centroid on the frame,
                    circleColor = (0, 255, 17)  # TODO verify, I think it is B, G, R
                    thickness = 2
                    shift = 0
                    lineType=8
                    cv2.rectangle(img, (int(x), int(y)),
                               circleColor, thickness, lineType, shift)
                    # then update the list of tracked points
                    # circleColor = (0, 0, 255)
                    # thickness = -1 # -1 is filled
                    # cv2.circle(frame, center, 5, circleColor, thickness)

                    outputPan = centerPan + panPid(x)
                    outputTilt = centerTilt - tiltPid(y)
                    if not DISABLE_PID:
                        pwm.setRotationAngle(panAddress, outputPan)
                        pwm.setRotationAngle(tiltAddress, outputTilt)
                    oldOutputPan = outputPan
                    oldOutputTilt = outputTilt
                    #Following was part of the ball tracking
                    # print(repr(int(x)) + ", " + repr(panPid(x)))
                    # print(repr(sequenceNumber) + ", Radius: " + repr(int(radius))
                    #       + " at X,Y of " + repr(int(x)) + "," + repr(int(y)) + ","
                    #       + repr(panPid(x)) + ", " + repr(tiltPid(y)) + ", "
                    #       + repr(panPid.components) + repr(tiltPid.components)
                    #       )
                    if (abs(320 - x) < 30) and (abs(240 - y) < 30):
                        GPIO.output(laserPIN, GPIO.HIGH)
                    else:
                        GPIO.output(laserPIN, GPIO.LOW)

            sequenceNumber = sequenceNumber + 1
            if sequenceNumber == 10:
                sequenceNumber = 1

        time.sleep(0.01)
        outputStream.putFrame(img)
