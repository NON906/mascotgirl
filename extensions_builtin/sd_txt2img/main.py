#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import threading
import os
import json

from src import extension

class SDTxt2ImgExtension(extension.Extension):
    __url = 'http://127.0.0.1:7860'
    __generate_prompt = None
    __main_settings = None
    __thread = None
    __is_show = False
    __is_generate = False

    def init(self, main_settings):
        self.__main_settings = main_settings

    def get_chatgpt_functions(self):
        return [{
            "name": "sd_txt2img",
            "description": "Generate image from prompt by Stable Diffusion. (Sentences cannot be generated.) There is no memory function, so please carry over the prompts from past conversations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": 'Prompt for generate image. Prompt is comma separated keywords such as "1girl, school uniform, red ribbon". If it is not in English, please translate it into English (lang:en).',
                    },
                    "message": {
                        "type": "string",
                        "description": 'Chat message (lang:ja). Displayed before the image.',
                    },
                },
                "required": ["prompt", "message"],
            },
        }]

    def get_chatgpt_system_message(self):
        if self.__is_show and self.__generate_prompt is not None and self.__generate_prompt != '':
            return '* The generated image by the following prompt is displayed.\n  ' + self.__generate_prompt
        return None

    def txt2img_thread_func(self):
        def get_add_keywords(prompt, keywords):
            add_prompt = ''
            prompt_list = prompt.split(',')
            for add_word, targets in keywords.items():
                add_flag = False
                for prompt_word in prompt_list:
                    for target in targets:
                        if target in prompt_word:
                            add_flag = True
                if add_flag:
                    if add_prompt != '':
                        add_prompt += ', '
                    add_prompt += add_word
            return add_prompt

        json_path = os.path.join(os.path.dirname(__file__), 'settings.json')
        with open(json_path, 'r') as f:
            loaded_json = json.load(f)
        width = -1
        height = -1
        if 'width' in loaded_json:
            width = loaded_json['width']
        if 'height' in loaded_json:
            height = loaded_json['height']
        if width <= 0 and height <= 0:
            width = 512
        if width <= 0 or height <= 0:
            loaded_json['width'] = self.__main_settings.screen_size[0]
            loaded_json['height'] = self.__main_settings.screen_size[1]
            if width > 0:
                if loaded_json['width'] > width:
                    loaded_json['height'] = loaded_json['height'] * width // loaded_json['width']
                    loaded_json['width'] = width
            elif height > 0:
                if loaded_json['height'] > height:
                    loaded_json['width'] = loaded_json['width'] * height // loaded_json['height']
                    loaded_json['height'] = height
            
        if not 'prompt' in loaded_json:
            loaded_json['prompt'] = ''
        if not 'negative_prompt' in loaded_json:
            loaded_json['negative_prompt'] = ''

        if loaded_json['prompt'] != '':
            loaded_json['prompt'] += ', '
        loaded_json['prompt'] += self.__generate_prompt

        keywords_path = os.path.join(os.path.dirname(__file__), 'keywords.json')
        if os.path.isfile(keywords_path):
            with open(keywords_path, 'r') as f:
                keywords_json = json.load(f)
            add_prompt = get_add_keywords(self.__generate_prompt, keywords_json['prompt'])
            if add_prompt != '':
                loaded_json['prompt'] += ', ' + add_prompt
            add_negative = get_add_keywords(self.__generate_prompt, keywords_json['negative_prompt'])
            if add_negative != '':
                if loaded_json['negative_prompt'] != '':
                    loaded_json['negative_prompt'] += ', '
                loaded_json['negative_prompt'] += add_negative

        request_result = requests.post(self.__url + '/sdapi/v1/txt2img', data=json.dumps(loaded_json))
        result_json = request_result.json()
        self.__main_settings.set_forward_image_base64(result_json['images'][0])

    def recv_function_streaming(self, messages, function_name, result):
        if function_name != 'sd_txt2img':
            if self.__is_show:
                self.__main_settings.set_forward_image(None)
                self.__is_show = False
            return None
        
        if result is None:
            return None

        if 'prompt' in result:
            if self.__generate_prompt != result['prompt']:
                self.__generate_prompt = result['prompt']
            elif not self.__is_generate:
                self.__is_generate = True
                self.__thread = threading.Thread(target=self.txt2img_thread_func)
                self.__thread.start()
        
        if 'message' in result:
            return result['message']
        return None

    def recv_function(self, messages, function_name, result):
        if function_name != 'sd_txt2img':
            return None
        if not self.__is_generate:
            self.__generate_prompt = result['prompt']
            self.__is_generate = True
            self.__thread = threading.Thread(target=self.txt2img_thread_func)
            self.__thread.start()
        if 'message' in result:
            return result['message']
        return '画像を生成しました'

    def recv_message_streaming(self, messages, streaming_message):
        if not self.__is_generate and self.__is_show:
            self.__main_settings.set_forward_image(None)
            self.__is_show = False

    def recv_message(self, messages):
        if not self.__is_generate:
            if self.__is_show:
                self.__main_settings.set_forward_image(None)
                self.__is_show = False
        else:
            self.__thread.join()
            self.__is_show = True
        self.__is_generate = False

extension.extensions.append(SDTxt2ImgExtension())