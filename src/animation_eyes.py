#!/usr/bin/env python
# -*- coding: utf-8 -*-

import random

class AnimationEyes:
    #BLINK_CLOSE_TIME = 0.16
    #BLINK_MIN_TIME = 1.2
    #BLINK_MAX_TIME = 1.8

    play_name = None
    play_position = 0.0
    animation_length = 0.0

    def __init__(self, mascot_image):
        self.mascot_image = mascot_image
        #self.blink_time = random.uniform(self.BLINK_MIN_TIME, self.BLINK_MAX_TIME)

    def set_morph(self, name, time_length, reset):
        if name == 'normal':
            self.play_name = None
            return
        self.play_name = name
        if reset:
            self.play_position = 0.0
        self.animation_length = time_length

    def update(self, add_position):
        #self.blink_time -= add_position
        if self.play_name is not None:
            self.play_position += add_position
            if self.play_position > self.animation_length:
                self.play_name = None
            else:
                if self.play_name == 'closed':
                    self.mascot_image.set_eye(0, 1.0, 1.0)
                elif self.play_name == 'happy_closed':
                    self.mascot_image.set_eye(1, 1.0, 1.0)
                elif self.play_name == 'relaxed_closed':
                    self.mascot_image.set_eye(3, 1.0, 1.0)
                elif self.play_name == 'surprized':
                    self.mascot_image.set_eye(2, 1.0, 1.0)
                #elif self.play_name == 'jig_eyes':
                #    self.mascot_image.set_eye(4, 1.0, 1.0)
                elif self.play_name == 'wink':
                    self.mascot_image.set_eye(1, 1.0, 0.0)
                #if self.blink_time < self.BLINK_CLOSE_TIME / 2.0:
                #    self.blink_time = self.BLINK_CLOSE_TIME / 2.0
                return
        #if self.blink_time < -self.BLINK_CLOSE_TIME / 2.0:
        #    self.mascot_image.set_eye(0, 0.0, 0.0)
        #    self.blink_time += random.uniform(self.BLINK_MIN_TIME, self.BLINK_MAX_TIME)
        #elif self.blink_time < self.BLINK_CLOSE_TIME / 2.0:
        #    closed_val = self.blink_time / (self.BLINK_CLOSE_TIME / 2.0)
        #    self.mascot_image.set_eye(0, closed_val, closed_val)
        #else:
        #    self.mascot_image.set_eye(0, 0.0, 0.0)
        self.mascot_image.set_eye(0, 0.0, 0.0)