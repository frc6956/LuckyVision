import cv2
import imutils

# construct a range of colors of our ball,
# this sets a minimum and maximum range in HSV space and makes it white
# and makes everything else white.  This mask is much easier to identify
# features in the image
greenLower = (73, 91, 52)   # (h, s, v)
greenUpper = (82, 218, 255)
# Note: h (hue) is normally 0 to 359 on the color wheel but OpenCV uses 0 to 179,
# s (saturation) is normally 0 to 100 but 255 in OpenCV,
# v (value) also is normally 0 to 100 but 255 in OpenCV

def test(img):
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
        minArea = cv2.minAreaRect(c)
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
    return img, center
