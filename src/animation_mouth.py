#!/usr/bin/env python
# -*- coding: utf-8 -*-

class AnimationMouthQuery:
    index: int
    start_position: float
    end_position: float

class AnimationMouth:
    MAINTAIN_TIME = 0.08
    QUERY_TIME_SCALE = 1.0 #40000.0 / 48000.0

    play_position = 0.0
    animation_length = 0.0
    queries = []

    def __init__(self, mascot_image):
        self.mascot_image = mascot_image

    def set_audio_query(self, query):
        if self.play_position > self.animation_length:
            self.play_position = 0.0
            self.animation_length = 0.0
            self.queries = []
        self.animation_length += query['prePhonemeLength'] * self.QUERY_TIME_SCALE
        for accent_phrase in query['accent_phrases']:
            for mora in accent_phrase['moras']:
                if mora['consonant'] is not None:
                    self.animation_length += mora['consonant_length'] * self.QUERY_TIME_SCALE
                if mora['vowel'] is not None:
                    new_query = AnimationMouthQuery()
                    if mora['vowel'] == 'a' or mora['vowel'] == 'A':
                        new_query.index = 0
                    elif mora['vowel'] == 'i' or mora['vowel'] == 'I':
                        new_query.index = 1
                    elif mora['vowel'] == 'u' or mora['vowel'] == 'U':
                        new_query.index = 2
                    elif mora['vowel'] == 'e' or mora['vowel'] == 'E':
                        new_query.index = 3
                    elif mora['vowel'] == 'o' or mora['vowel'] == 'O':
                        new_query.index = 4
                    else:
                        new_query.index = -1
                    if new_query.index >= 0:
                        new_query.start_position = self.animation_length
                        new_query.end_position = self.animation_length + mora['vowel_length'] * self.QUERY_TIME_SCALE
                        self.queries.append(new_query)
                    self.animation_length += mora['vowel_length'] * self.QUERY_TIME_SCALE
            if accent_phrase['pause_mora'] is not None:
                if mora['consonant'] is not None:
                    self.animation_length += mora['consonant_length'] * self.QUERY_TIME_SCALE
                if mora['vowel'] is not None:
                    self.animation_length += mora['vowel_length'] * self.QUERY_TIME_SCALE
        self.animation_length += query['postPhonemeLength'] * self.QUERY_TIME_SCALE
        return self.animation_length - self.play_position

    def update(self, add_position):
        self.play_position += add_position
        for loop, query in enumerate(self.queries):
            if query.start_position <= self.play_position and self.play_position <= query.end_position:
                self.mascot_image.set_mouth(query.index, 1.0)
                return
            elif self.play_position <= query.start_position:
                target_value = 0.0
                if loop > 0:
                    target_query = self.queries[loop - 1]
                    target_value = 1.0 - (self.play_position - target_query.end_position) / self.MAINTAIN_TIME
                    if target_value < 0.0:
                        target_value = 0.0
                query_value = 1.0 - (query.start_position - self.play_position) / self.MAINTAIN_TIME
                if query_value < 0.0:
                    query_value = 0.0
                if target_value <= query_value:
                    self.mascot_image.set_mouth(query.index, query_value)
                else:
                    self.mascot_image.set_mouth(target_query.index, target_value)
                return
        if len(self.queries) > 0:
            target_query = self.queries[-1]
            target_value = 1.0 - (self.play_position - target_query.end_position) / self.MAINTAIN_TIME
            if target_value < 0.0:
                target_value = 0.0
            self.mascot_image.set_mouth(target_query.index, target_value)
        else:
            self.mascot_image.set_mouth(0, 0.0)