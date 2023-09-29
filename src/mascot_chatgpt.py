#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.getcwd() + "/gpt-stream-json-parser")

import openai
import json
import threading
from gpt_stream_parser import force_parse_json

class MascotChatGpt:
    chatgpt_messages = []
    chatgpt_response = None
    log_file_name = None
    chatgpt_model_name = "gpt-3.5-turbo"
    chatgpt_functions = [{
        "name": "message_and_change_states",
        "description": """
Change the state of the character who will be speaking, then send the message.
        """,
        "parameters": {
            "type": "object",
            "properties": {
                "voice_style": {
                    "type": "string",
                    "description": "",
                },
                "eyebrow": {
                    "type": "string",
                    "description": "Change eyebrow (Either normal/troubled/angry/happy/serious).",
                },
                "eyes": {
                    "type": "string",
                    "description": "Change eyes (Either Either normal/closed/happy_closed/relaxed_closed/surprized/wink).",
                },
                "message": {
                    "type": "string",
                    "description": "Japanese message(lang:ja).",
                },
            },
            "required": ["message"],
        },
    }]
    recieved_message = ''
    recieved_states_data = ''

    def __init__(self, apikey):
        openai.api_key = apikey

    def load_model(self, model_name):
        self.chatgpt_model_name = model_name

    def load_log(self, log):
        if log is None:
            return False
        try:
            self.log_file_name = log
            if os.path.isfile(log):
                with open(log, 'r', encoding='UTF-8') as f:
                    self.chatgpt_messages = json.loads(f.read())
                return True
        except:
            pass
        return False

    def load_setting(self, chatgpt_setting, voicevox_style_names):
        self.chatgpt_messages = []
        if os.path.isfile(chatgpt_setting):
            with open(chatgpt_setting, 'r', encoding='UTF-8') as f:
                chatgpt_setting_content = f.read()
        else:
            chatgpt_setting_content = ''
        style_names_str = ''
        for style_name in voicevox_style_names:
            style_names_str += style_name
            if voicevox_style_names[-1] != style_name:
                style_names_str += '/'
        self.chatgpt_functions[0]["parameters"]["properties"]["voice_style"]["description"] = '''
Change voice style (Either ''' + style_names_str + ''').
        '''
        self.chatgpt_messages.append({"role": "system", "content": chatgpt_setting_content})

    def write_log(self):
        if self.log_file_name is None:
            return        
        with open(self.log_file_name + '.tmp', 'w', encoding='UTF-8') as f:
            f.write(json.dumps(self.chatgpt_messages, sort_keys=True, indent=4, ensure_ascii=False))
        if os.path.isfile(self.log_file_name):
            os.rename(self.log_file_name, self.log_file_name + '.prev')
        os.rename(self.log_file_name + '.tmp', self.log_file_name)
        if os.path.isfile(self.log_file_name + '.prev'):
            os.remove(self.log_file_name + '.prev')

    def send_to_chatgpt(self, content, write_log=True):
        if self.chatgpt_response is not None:
            return False

        def recv():
            self.recieved_message = ''
            recieved_json = ''
            self.recieved_states_data = ''
            self.chatgpt_messages.append({"role": "user", "content": content})
            self.chatgpt_response = openai.ChatCompletion.create(
                model=self.chatgpt_model_name,
                messages=self.chatgpt_messages,
                stream=True
            )
            for chunk in self.chatgpt_response:
                if 'function_call' in chunk.choices[0].delta and chunk.choices[0].delta.function_call is not None and chunk.choices[0].delta.function_call.name == 'message_and_change_states':
                    recieved_json += chunk.choices[0].delta.function_call.arguments
                    self.recieved_states_data = force_parse_json(recieved_json)
                    if 'message' in self.recieved_states_data:
                        self.recieved_message = self.recieved_states_data['message']
                else:
                    self.recieved_message += chunk.choices[0].delta.get('content', '')
            self.chatgpt_messages.append({"role": "assistant", "content": self.recieved_message})
            if write_log:
                self.write_log()
            self.chatgpt_response = None

        self.chatgpt_response = []
        recv_thread = threading.Thread(target=recv)
        recv_thread.start()

        return True

    def get_states(self):
        voice_style = None
        eyebrow = None
        eyes = None
        if 'voice_style' in self.recieved_states_data:
            voice_style = self.recieved_states_data['voice_style']
        if 'eyebrow' in self.recieved_states_data:
            eyebrow = self.recieved_states_data['eyebrow']
        if 'eyes' in self.recieved_states_data:
            eyes = self.recieved_states_data['eyes']
        return self.chatgpt_response is None, voice_style, eyebrow, eyes

    def get_message(self):
        return self.chatgpt_response is None, self.recieved_message

    def remove_last_conversation(self, result=None, write_log=True):
        if result is None or self.chatgpt_messages[-1]["content"] == result:
            self.chatgpt_messages = self.chatgpt_messages[:-2]
            if write_log:
                self.write_log()
