#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import openai
import sys
import json

class MascotChatGpt:
    chatgpt_messages = []
    chatgpt_response = None
    log_file_name = None

    def __init__(self, apikey):
        openai.api_key = apikey

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
        self.json_format = '''
{
    "message": "Japanese message(lang:ja)",
    "voice_style": "Either ''' + style_names_str + '''",
    "eyebrow": "Either normal/troubled/angry/happy/serious",
    "eyes": "Either normal/closed/happy_closed/relaxed_closed/surprized/wink"
}
        '''
        chatgpt_setting_content += '\n\n*You always reply in JSON format like below and must not reply elsewhere:\n'
        chatgpt_setting_content += self.json_format
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
            return None
        self.chatgpt_messages.append({"role": "user", "content": content})
        self.chatgpt_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=self.chatgpt_messages
        )
        result = str(self.chatgpt_response["choices"][0]["message"]["content"])
        self.chatgpt_response = None
        self.chatgpt_messages.append({"role": "assistant", "content": result})
        #print(result, file=sys.stderr)
        if write_log:
            self.write_log()
        return result

    def remove_last_conversation(self, result=None, write_log=True):
        if result is None or self.chatgpt_messages[-1]["content"] == result:
            self.chatgpt_messages = self.chatgpt_messages[:-2]
            if write_log:
                self.write_log()

    def send_to_chatgpt_by_json(self, content):
        def send(content):
            response_json = self.send_to_chatgpt(content, write_log=False)
            if response_json is None:
                return None
            try:
                start_index = response_json.find('{')
                if start_index < 0:
                    raise Exception()
                end_index = response_json.rfind('}')
                if end_index < 0:
                    raise Exception()
                response_json = response_json[start_index:(end_index + 1)]
                response_values = json.loads(response_json)
                #print(response_json, file=sys.stderr)
                return response_values
            except:
                #print(response_json, file=sys.stderr)
                return None

        ret = send(content)
        if ret is None:
            ret = send('Put it in the following JSON format:\n' + self.json_format)
            if ret is None:
                self.chatgpt_messages = self.chatgpt_messages[:-4]
                return ret
            else:
                self.chatgpt_messages = self.chatgpt_messages[:-3] + self.chatgpt_messages[-1:]
        self.write_log()
        return ret
