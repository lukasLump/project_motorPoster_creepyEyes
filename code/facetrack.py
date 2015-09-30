#!/usr/bin/python

# Core code borrowed from
# http://instructables.com/id/Pan-Tilt-face-tracking-with-the-raspberry-pi
# and various other places

from RPIO import PWM
from multiprocessing import Process, Queue
import time
import cv2
import logging

log_format = '%(levelname)s | %(asctime)-15s | %(message)s'
logging.basicConfig(format=log_format, level=logging.DEBUG)
#servo GPIO connections
pPan = 23
pTilt = 24

# Upper limit

_ServoPanUL = 240

# Lower Limit

_ServoPanLL = 64

#initial Position
initPan = ((_ServoPanUL - _ServoPanLL) / 2) + _ServoPanLL

#size of the video
width = 320
height = 240

capture = cv2.VideoCapture(0)        # Get ready to start getting images from the webcam
capture.set(cv2.cv.CV_CAP_PROP_FRAME_WIDTH, width)
capture.set(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT, height)

#frontalface = cv2.CascadeClassifier("haarcascade_frontalface_alt2.xml")    # frontal face pattern detection
frontalface = cv2.CascadeClassifier("lbpcascade_frontalface.xml")    # frontal face pattern detection
#profileface = cv2.CascadeClassifier("lbpcascade_profileface.xml")    # side face pattern detection

face = [0,0,0,0]  # This will hold the array that OpenCV returns when it finds a face: (makes a rectangle)
Cface = [0,0]    # Center of the face: a point calculated from the above variable
lastface = 0    # int 1-3 used to speed up detection. The script is looking for a right profile face,-
      #   a left profile face, or a frontal face; rather than searching for all three every time,-
      #   it uses this variable to remember which is last saw: and looks for that again. If it-
      #   doesn't find it, it's set back to zero and on the next loop it will search for all three.-
      #   This basically tripples the detect time so long as the face hasn't moved much.

PWM.setup()
PWM.init_channel(0)

#init servos to center
PWM.add_channel_pulse(0, pPan, 0, initPan)


ServoPanCP = Queue()  # Servo zero current position, sent by subprocess and read by main process
ServoPanDP = Queue()  # Servo zero desired position, sent by main and read by subprocess
ServoPanS = Queue()  # Servo zero speed, sent by main and read by subprocess

#cv2.cv.NamedWindow("video", cv2.cv.CV_WINDOW_AUTOSIZE)


def P0():  # Process 0 controlles Pan servo
  speed = .1    # Here we set some defaults:
  _ServoPanCP = initPan - 1    # by making the current position and desired position unequal,-
  _ServoPanDP = initPan    #   we can be sure we know where the servo really is. (or will be soon)

  while True:
    time.sleep(speed)
    if ServoPanCP.empty():      # Constantly update ServoPanCP in case the main process needs-
      ServoPanCP.put(_ServoPanCP)    #   to read it
    if not ServoPanDP.empty():    # Constantly read read ServoPanDP in case the main process-
      _ServoPanDP = ServoPanDP.get()  #  has updated it
    if not ServoPanS.empty():      # Constantly read read ServoPanS in case the main process-
      _ServoPanS = ServoPanS.get()  #   has updated it, the higher the speed value, the shorter-
      speed = .1 / _ServoPanS    #   the wait between loops will be, so the servo moves faster
    if _ServoPanCP < _ServoPanDP:          # if ServoPanCP less than ServoPanDP
      _ServoPanCP += 1            # incriment ServoPanCP up by one
      ServoPanCP.put(_ServoPanCP)          # move the servo that little bit
      PWM.clear_channel_gpio(0, pPan)
      PWM.add_channel_pulse(0, pPan, 0, _ServoPanCP)
      if not ServoPanCP.empty():        # throw away the old ServoPanCP value,-
        trash = ServoPanCP.get()        #   it's no longer relevent
    if _ServoPanCP > _ServoPanDP:          # if ServoPanCP greater than ServoPanDP
      _ServoPanCP -= 1            # incriment ServoPanCP down by one
      ServoPanCP.put(_ServoPanCP)          # move the servo that little bit
      PWM.clear_channel_gpio(0, pPan)
      PWM.add_channel_pulse(0, pPan, 0, _ServoPanCP)
      if not ServoPanCP.empty():        # throw away the old ServoPanCP value,-
        trash = ServoPanCP.get()        #   it's no longer relevent
    if _ServoPanCP == _ServoPanDP:          # if all is good,-
      _ServoPanS = 1            # slow the speed; no need to eat CPU just waiting





Process(target=P0, args=()).start()  # Start the subprocesses
time.sleep(1)        # Wait for them to start

#====================================================================================================

def CamRight( distance, speed ):    # To move right, we are provided a distance to move and a speed to move.
  global _ServoPanCP      # We Global it so  everyone is on the same page about where the servo is...
  if not ServoPanCP.empty():    # Read it's current position given by the subprocess(if it's avalible)-
    _ServoPanCP = ServoPanCP.get()  #   and set the main process global variable.
  _ServoPanDP = _ServoPanCP + distance  # The desired position is the current position + the distance to move.
  if _ServoPanDP > _ServoPanUL:    # But if you are told to move further than the servo is built go...
    _ServoPanDP = _ServoPanUL    # Only move AS far as the servo is built to go.
  ServoPanDP.put(_ServoPanDP)      # Send the new desired position to the subprocess
  ServoPanS.put(speed)      # Send the new speed to the subprocess
  return;

def CamLeft(distance, speed):      # Same logic as above
  global _ServoPanCP
  if not ServoPanCP.empty():
    _ServoPanCP = ServoPanCP.get()
  _ServoPanDP = _ServoPanCP - distance
  if _ServoPanDP < _ServoPanLL:
    _ServoPanDP = _ServoPanLL
  ServoPanDP.put(_ServoPanDP)
  ServoPanS.put(speed)
  return;





#============================================================================================================

try:
    while True:

        faceFound = False  # This variable is set to true if, on THIS loop a face has already been found
                    # We search for a face three diffrent ways, and if we have found one already-
                    # there is no reason to keep looking.

        if not faceFound:
            if lastface == 0 or lastface == 1:
                aframe = capture.grab()  # there seems to be an issue in OpenCV or V4L or my webcam-
                aframe = capture.grab()  #   driver, I'm not sure which, but if you wait too long,
                aframe = capture.grab()  #  the webcam consistantly gets exactly five frames behind-
                aframe = capture.grab()  #  realtime. So we just grab a frame five times to ensure-
                aframe = capture.read()[1]  #  we have the most up-to-date image.
                #fface = frontalface.detectMultiScale(aframe, 1.3, 4, (cv2.cv.CV_HAAR_DO_CANNY_PRUNING + cv2.cv.CV_HAAR_FIND_BIGGEST_OBJECT + cv2.cv.CV_HAAR_DO_ROUGH_SEARCH), (60,60))
                fface = frontalface.detectMultiScale(aframe, 1.1, 2, 0, (60,60))
                if fface != ():      # if we found a frontal face...
                    lastface = 1    # set lastface 1 (so next loop we will only look for a frontface)
                    for f in fface:    # f in fface is an array with a rectangle representing a face
                        faceFound = True
                        face = f


        if not faceFound:    # if no face was found...-
            lastface = 0    #   the next loop needs to know
            face = [0,0,0,0]  # so that it doesn't think the face is still where it was last loop

        x,y,w,h = face

        if lastface == 3:
            Cface = [(w/2+(width-x-w)),(h/2+y)]  # we are given an x,y corner point and a width and height, we need the center
        else:
            Cface = [(w/2+x),(h/2+y)]  # we are given an x,y corner point and a width and height, we need the center

    #    print str(Cface[0]) + "," + str(Cface[1])


        cv2.cv.Rectangle(cv2.cv.fromarray(aframe), (x,y), (x+w, y+h), cv2.cv.RGB(255, 0, 0), 3, 8, 0)
    #    cv2.imshow("video", aframe)
        cv2.waitKey(1)


        if Cface[0] != 0:    # if the Center of the face is not zero (meaning no face was found)

            if Cface[0] > 180:  # The camera is moved diffrent distances and speeds depending on how far away-
                CamLeft(5,400)  #  from the center of that axis it detects a face
            if Cface[0] > 190:  #
                CamLeft(32,400)  #
            if Cface[0] > 200:  #
                CamLeft(36,400)  #

            if Cface[0] < 180:  # and diffrent dirrections depending on what side of center if finds a face.
                CamRight(5,400)
            if Cface[0] < 130:
                CamRight(32,400)
            if Cface[0] < 120:
                CamRight(36,400)



except KeyboardInterrupt:
    pass

finally:
    PWM.clear_channel(0)
    PWM.cleanup()
    capture.release()
    cv2.cv.DestroyWindow("video")
