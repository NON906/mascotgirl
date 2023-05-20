#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import uuid
import wave
import sys
if os.name == 'nt':
    import win32pipe, win32file, pywintypes

class NamedPipeAudio:
    wave_files = []
    named_pipe = None

    def set_pipe(self, pipe):
        self.named_pipe = pipe

    def add_wave_file(self, memory):
        wav_file = wave.open(memory, 'rb')
        self.wave_files.append(wav_file)

    def add_bytes(self, memory):
        self.wave_files.append(memory)

    def write_audio_frame(self, get_frame_size, audio_sampwidth=2):
        ret = get_frame_size
        while get_frame_size > 0:
            if len(self.wave_files) <= 0:
                write_size = get_frame_size
                if write_size > 0:
                    self.named_pipe.write(bytes(write_size * audio_sampwidth))
                    get_frame_size -= write_size
                return ret - get_frame_size
            if type(self.wave_files[0]) is bytes:
                data = self.wave_files[0][0:(get_frame_size * audio_sampwidth)]
                self.wave_files[0] = self.wave_files[0][(get_frame_size * audio_sampwidth):]
            elif self.wave_files[0] is not None:
                data = self.wave_files[0].readframes(get_frame_size)
            else:
                if self.wave_files == 1:
                    self.wave_files = []
                else:
                    self.wave_files = self.wave_files[1:]
                continue
            get_frame_size -= len(data) // audio_sampwidth
            self.named_pipe.write(data)
            if get_frame_size > 0:
                if type(self.wave_files[0]) is not bytes:
                    self.wave_files[0].close()
                if self.wave_files == 1:
                    self.wave_files = []
                else:
                    self.wave_files = self.wave_files[1:]
        return ret

class NamedPipeWindows:
    def create(self, pipe_path):
        self.pipe_path = pipe_path
        self.pipe = win32pipe.CreateNamedPipe(
            pipe_path,
            win32pipe.PIPE_ACCESS_OUTBOUND,
            win32pipe.PIPE_TYPE_BYTE,
            1, 9600, 9600,
            0,
            None)
        win32pipe.ConnectNamedPipe(self.pipe, None)

    def close(self):
        if self.pipe is not None:
            win32file.CloseHandle(self.pipe)
        self.pipe = None

    def write(self, data):
        try:
            if self.pipe is not None:
                win32file.WriteFile(self.pipe, data)
        except pywintypes.error:
            raise BrokenPipeError()

    def force_close(self):
        handle = win32file.CreateFile(
            self.pipe_path,
            0,
            0,
            None,
            win32file.OPEN_EXISTING,
            0,
            None
        )
        win32file.CloseHandle(handle)

class NamedPipeUnix:
    pipe_path = None
    pipe_file = None

    def create(self, pipe_path):
        if not os.path.exists(pipe_path):
            self.pipe_path = pipe_path
            os.mkfifo(self.pipe_path)
        self.pipe_file = open(pipe_path, mode='wb')

    def close(self):
        if self.pipe_file is not None:
            self.pipe_file.close()
            self.pipe_file = None
        if self.pipe_path is not None:
            os.remove(self.pipe_path)
            self.pipe_path = None

    def write(self, data):
        if self.pipe_file is not None:
            self.pipe_file.write(data)

    def force_close(self):
        pass