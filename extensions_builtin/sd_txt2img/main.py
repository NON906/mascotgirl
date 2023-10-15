#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import threading
import os
import json

from src import extension

class SDTxt2ImgExtension(extension.Extension):
    __url = 'http://127.0.0.1:7860'
    __width = 512
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
        json_path = os.path.join(os.path.dirname(__file__), 'settings.json')
        with open(json_path, 'r') as f:
            loaded_json = json.load(f)
        loaded_json['width'] = self.__main_settings.screen_size[0]
        loaded_json['height'] = self.__main_settings.screen_size[1]
        while loaded_json['width'] > self.__width:
            loaded_json['height'] = loaded_json['height'] * self.__width // loaded_json['width']
            loaded_json['width'] = self.__width
        loaded_json['prompt'] = self.__generate_prompt
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
        self.__thread.join()
        self.__is_generate = False
        if 'message' in result:
            return result['message']
        return '画像を生成しました'

extension.extensions.append(SDTxt2ImgExtension())