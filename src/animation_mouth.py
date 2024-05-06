#!/usr/bin/env python
# -*- coding: utf-8 -*-

import librosa
import numpy as np

import sys
import os
sys.path.append(os.getcwd() + "/Style-Bert-VITS2")
from style_bert_vits2.nlp.japanese.mora_list import MORA_KATA_TO_MORA_PHONEMES

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

    def set_by_mora_tone_list(self, mora_tone_list_input, wav_data, silence_after):
        if self.play_position > self.animation_length:
            self.play_position = 0.0
            self.animation_length = 0.0
            self.queries = []
        mora_tone_list = []
        for mora_tone_input in mora_tone_list_input:
            if mora_tone_input['mora'] in MORA_KATA_TO_MORA_PHONEMES.keys():
                mora_tone_list.append(mora_tone_input)
        if len(mora_tone_list) <= 0:
            return length
        y = np.frombuffer(wav_data, dtype=np.uint8)
        y = y.view(np.int16).astype(np.float32) / 32768.0
        length = y.shape[0] / 44100.0
        dbs = librosa.feature.rms(y=y, frame_length=44100 * 4 // 120, hop_length=44100 // 120)[0]
        dbs = 20 * np.log10(dbs / 2e-5)
        dbs_delta = dbs - np.concatenate([np.array([0.0, ]), dbs[:dbs.shape[0] - 1]])
        threshold = np.sort(dbs_delta)[dbs_delta.shape[0] - len(mora_tone_list)]
        step_length = length / dbs.shape[0]
        mora_index = 0
        queries = []
        for loop in range(dbs.shape[0]):
            if dbs_delta[loop] >= threshold:
                for loop2 in range(loop + 1):
                    if loop - loop2 - 1 < 0 or dbs[loop - loop2 - 1] > dbs[loop - loop2]:
                        new_query = AnimationMouthQuery()
                        new_query.start_position = (loop - loop2) * step_length + self.animation_length
                        vowel = MORA_KATA_TO_MORA_PHONEMES[mora_tone_list[mora_index]['mora']][1]
                        if vowel == 'a':
                            new_query.index = 0
                        elif vowel == 'i':
                            new_query.index = 1
                        elif vowel == 'u':
                            new_query.index = 2
                        elif vowel == 'e':
                            new_query.index = 3
                        elif vowel == 'o':
                            new_query.index = 4
                        else:
                            new_query.index = -1
                        queries.append(new_query)
                        mora_index += 1
                        break
        for loop in range(len(queries) - 1):
            queries[loop].end_position = queries[loop + 1].start_position
            if queries[loop].index >= 0:
                self.queries.append(queries[loop])
        queries[len(queries) - 1].end_position = length - silence_after + self.animation_length
        if queries[len(queries) - 1].index >= 0:
            self.queries.append(queries[len(queries) - 1])
        self.animation_length += length
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