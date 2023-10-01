#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math

class AnimationBreathing:
    SPEED = math.pi / 16

    play_position = 0.0

    def __init__(self, mascot_image):
        self.mascot_image = mascot_image

    def update(self, add_position):
        self.play_position += add_position * self.SPEED
        self.mascot_image.set_other_pose(9, -math.cos(self.play_position) * 0.5 + 0.5)