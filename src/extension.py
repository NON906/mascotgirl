#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

extensions = []

class Extension:
    def init(self, main_settings):
        pass

    def get_chatgpt_functions(self):
        return None

    def get_chatgpt_system_message(self):
        return None

    def recv_message(self, messages):
        pass

    def recv_message_streaming(self, messages, streaming_message):
        pass

    def recv_function(self, messages, function_name, result):
        return None

    def recv_function_streaming(self, messages, function_name, result):
        pass

    def remove_last_conversation(self):
        pass

    def clear(self):
        pass

from importlib import import_module
extension_modules = [
    import_module('extensions.' + f + '.main') for f in os.listdir('extensions') if os.path.isdir(os.path.join('extensions', f))
]