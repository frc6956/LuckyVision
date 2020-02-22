
import numpy as np
import cv2

image = cv2.imread('green.JPG')
original = image.copy()
image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
lower = np.array([73, 91, 52], dtype="uint8")
upper = np.array([82, 218, 255], dtype="uint8")
mask = cv2.inRange(image, lower, upper)

cnts = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
cnts = cnts[0] if len(cnts) == 2 else cnts[1]

for c in cnts:
    x,y,w,h = cv2.boundingRect(c)
    cv2.rectangle(original, (x, y), (x + w, y + h), (36,255,12), 2)

print(cv2.__file__)
print(cv2.getBuildInformation())
cv2.startWindowThread()
cv2.imshow('mask', mask)
#cv2.imshow('original', original)
cv2.waitKey()
cv2.destroyAllWindows()
