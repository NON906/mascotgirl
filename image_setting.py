#!/usr/bin/env python
# -*- coding: utf-8 -*-

import cv2
import numpy as np
import sys

def image_setting(image, cascade_path='./lbpcascade_animeface.xml'):
    import rembg

    if image.shape[2] != 4 or image[0, 0, 3] >= 255:
        image = rembg.remove(image)

    cascade = cv2.CascadeClassifier(cascade_path)

    image_gray = cv2.cvtColor(image, cv2.COLOR_RGBA2GRAY)
    image_gray = cv2.equalizeHist(image_gray)

    for min_neighbors in range(2, 6):
        faces = cascade.detectMultiScale(image_gray, minNeighbors=min_neighbors)
        if len(faces) == 1:
            break
    if len(faces) != 1:
        print('Error: Detect faces: ' + str(len(faces)), file=sys.stderr)
        return None
    
    x, y, w, h = faces[0]
    src_pts = np.float32([[x, y - h * 0.15], [x + w, y - h * 0.15], [x + w, y + h * 0.85]])
    DST_PADDING = 16
    dst_pts = np.float32([[192 + DST_PADDING, 64 + DST_PADDING], [320 - DST_PADDING, 64 + DST_PADDING], [320 - DST_PADDING, 192 - DST_PADDING]])

    mat = cv2.getAffineTransform(src_pts, dst_pts)
    dst = cv2.warpAffine(image, mat, (512, 512))

    return dst

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', '-i')
    parser.add_argument('--output', '-o')
    parser.add_argument('--cascade', '-c', default='./lbpcascade_animeface.xml')
    args = parser.parse_args()

    image = cv2.imread(args.input, -1)

    result = image_setting(image, args.cascade)

    if result is not None:
        cv2.imwrite(args.output, result)