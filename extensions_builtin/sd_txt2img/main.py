#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import threading
import os
import json
import copy

from src import extension

global_loaded_json = None
global_loaded_json_raw_txt = None

class SDTxt2ImgExtension(extension.Extension):
    __url = 'http://127.0.0.1:7860'
    _generate_prompt = None
    _main_settings = None
    _keywords_json = None
    _keywords_json_raw_txt = None

    def init(self, main_settings):
        global global_loaded_json
        global global_loaded_json_raw_txt
        self._main_settings = main_settings
        if global_loaded_json is None:
            json_path = os.path.join(os.path.dirname(__file__), 'settings.json')
            with open(json_path, 'r') as f:
                global_loaded_json_raw_txt = f.read()
                global_loaded_json = json.loads(global_loaded_json_raw_txt)
        if self._keywords_json is None:
            keywords_path = os.path.join(os.path.dirname(__file__), 'keywords.json')
            if os.path.isfile(keywords_path):
                with open(keywords_path, 'r') as f:
                    self._keywords_json_raw_txt = f.read()
                    self._keywords_json = json.loads(self._keywords_json_raw_txt)

    def txt2img_thread_func(self, override_settings={}):
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

        global global_loaded_json
        loaded_json = copy.deepcopy(global_loaded_json)

        for key, value in override_settings.items():
            loaded_json[key] = value

        width = -1
        height = -1
        if 'width' in loaded_json:
            width = loaded_json['width']
        if 'height' in loaded_json:
            height = loaded_json['height']
        if width <= 0 and height <= 0:
            width = 512
        if width <= 0 or height <= 0:
            loaded_json['width'] = self._main_settings.screen_size[0]
            loaded_json['height'] = self._main_settings.screen_size[1]
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
        loaded_json['prompt'] += self._generate_prompt

        keywords_json = self._keywords_json
        if keywords_json is not None:
            add_prompt = get_add_keywords(self._generate_prompt, keywords_json['prompt'])
            if add_prompt != '':
                loaded_json['prompt'] += ', ' + add_prompt
            add_negative = get_add_keywords(self._generate_prompt, keywords_json['negative_prompt'])
            if add_negative != '':
                if loaded_json['negative_prompt'] != '':
                    loaded_json['negative_prompt'] += ', '
                loaded_json['negative_prompt'] += add_negative

        request_result = requests.post(self.__url + '/sdapi/v1/txt2img', data=json.dumps(loaded_json))
        return request_result.json()

class PictureExtension(SDTxt2ImgExtension):
    __is_show = False
    __is_generate = False
    __thread = None
    __loaded_json = None

    def init(self, main_settings):
        super().init(main_settings)
        json_path = os.path.join(os.path.dirname(__file__), 'picture_settings.json')
        if os.path.isfile(json_path):
            with open(json_path, 'r') as f:
                self.__loaded_json = json.load(f)
        else:
            self.__loaded_json = {
                'enabled': True,
            }

    def get_chatgpt_functions(self):
        if not self.__loaded_json['enabled']:
            return None

        return [{
            "name": "sd_generate_picture",
            "description": """
Generate image from prompt by Stable Diffusion.
This image will be displayed to hide the character and background.

Sentences cannot be generated.
There is no memory function, so please carry over the prompts from past conversations.
""",
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
        if self.__is_show and self._generate_prompt is not None and self._generate_prompt != '':
            return '* The generated image by the following prompt is displayed.\n  ' + self._generate_prompt
        return None

    def thread_func(self):
        result_json = self.txt2img_thread_func()
        self._main_settings.set_forward_image_base64(result_json['images'][0])

    def recv_function_streaming(self, messages, function_name, result):
        if function_name != 'sd_generate_picture':
            if self.__is_show:
                self._main_settings.set_forward_image(None)
                self.__is_show = False
            return None
        
        if result is None:
            return None

        if 'prompt' in result:
            if self._generate_prompt != result['prompt']:
                self._generate_prompt = result['prompt']
            elif not self.__is_generate:
                self.__is_generate = True
                self.__thread = threading.Thread(target=self.thread_func)
                self.__thread.start()
        
        if 'message' in result:
            return result['message']
        return None

    def recv_function(self, messages, function_name, result):
        if function_name != 'sd_generate_picture':
            return None
        if not self.__is_generate:
            self._generate_prompt = result['prompt']
            self.__is_generate = True
            self.__thread = threading.Thread(target=self.thread_func)
            self.__thread.start()
        if 'message' in result:
            return result['message']
        return '画像を生成しました'

    def recv_message_streaming(self, messages, streaming_message):
        if not self.__is_generate and self.__is_show:
            self._main_settings.set_forward_image(None)
            self.__is_show = False

    def recv_message(self, messages):
        if not self.__is_generate:
            if self.__is_show:
                self._main_settings.set_forward_image(None)
                self.__is_show = False
        else:
            self.__thread.join()
            self.__is_show = True
        self.__is_generate = False

    def get_settings(self):
        global global_loaded_json

        return [
            {
                'type': 'Label',
                'text': '画像生成（共通）',
            },
            {
                'type': 'Editor',
                'name': 'global_setting',
                'text': '画像生成設定',
                'value': global_loaded_json_raw_txt,
            },
            {
                'type': 'Editor',
                'name': 'custom_add_prompt_setting',
                'text': '自動追加（プロンプト・lora）設定',
                'value': self._keywords_json_raw_txt,
            },
            {
                'type': 'Label',
                'text': '画像生成（一枚絵）',
            },
            {
                'type': 'Toggle',
                'name': 'enabled',
                'text': '有効/無効',
                'value': str(self.__loaded_json['enabled']),
            },
        ]

    def set_setting(self, name, value):
        global global_loaded_json
        global global_loaded_json_raw_txt
        if name == 'global_setting':
            global_loaded_json_raw_txt = value
            global_loaded_json = json.loads(value)
            json_path = os.path.join(os.path.dirname(__file__), 'settings.json')
            with open(json_path, 'w') as f:
                f.write(value)
        elif name == 'custom_add_prompt_setting':
            self._keywords_json_raw_txt = value
            self._keywords_json = json.loads(value)
            keywords_path = os.path.join(os.path.dirname(__file__), 'keywords.json')
            with open(keywords_path, 'w') as f:
                f.write(value)
        else:
            self.__loaded_json[name] = value
            json_path = os.path.join(os.path.dirname(__file__), 'picture_settings.json')
            with open(json_path, 'w') as f:
                json.dump(self.__loaded_json, f)

class CharacterAndBackgroundExtension(SDTxt2ImgExtension):
    __character_prompt = None
    __background_prompt = None
    __thread = None
    __is_generate = False
    __loaded_json = None

    def init(self, main_settings):
        super().init(main_settings)
        json_path = os.path.join(os.path.dirname(__file__), 'chara_and_back_settings.json')
        if os.path.isfile(json_path):
            with open(json_path, 'r') as f:
                self.__loaded_json = json.load(f)
        else:
            self.__loaded_json = {
                'character_enabled': True,
                'background_enabled': True,
            }

    def get_chatgpt_functions(self):
        if not self.__loaded_json['character_enabled'] and not self.__loaded_json['background_enabled']:
            return None

        ret = [{
            "name": "sd_generate_character_and_background",
            "description": """
Generate character image and/or background image from prompt by Stable Diffusion.
This character is your alter ego, and the background is based on your location.
Please call it when your appearance changes by saying something like "change your outfit" or when your location changes by saying something like "move location".
Prompt is comma separated keywords such as "1girl, school uniform, red ribbon". If it is not in English, please translate it into English (lang:en).

Sentences cannot be generated.
There is no memory function, so please carry over the prompts from past conversations.
""",
            "parameters": {
                "type": "object",
                "properties": {
                    "character_prompt": {
                        "type": "string",
                        "description": '''
Prompt for generate character image.
The following are included from the beginning:
    solo, standing, simple background, no background, solid color background, looking at viewer, open mouth, full body standing, from front
''',
                    },
                    "background_prompt": {
                        "type": "string",
                        "description": 'Prompt for generate background image.',
                    },
                    "message": {
                        "type": "string",
                        "description": 'Chat message (lang:ja). Changed before the image.',
                    },
                },
                "required": ["message"],
            },
        }]

        if not self.__loaded_json['character_enabled']:
            del ret["parameters"]["properties"]["character_prompt"]
            ret["description"] += '\nNOTE: Character changing is currently disabled.'
        if not self.__loaded_json['background_enabled']:
            del ret["parameters"]["properties"]["background_prompt"]
            ret["description"] += '\nNOTE: Background changing is currently disabled.'

        return ret

    def get_chatgpt_system_message(self):
        if self.__character_prompt is not None:
            return '* Character image is generated the following prompt.\n  ' + self.__character_prompt + '\n'
        if self.__background_prompt is not None:
            return '* Background image is generated the following prompt.\n  ' + self.__background_prompt + '\n'
        return None

    def thread_func(self):
        global global_loaded_json
        if self.__character_prompt is not None:
            self._generate_prompt = self.__character_prompt
            result_json = self.txt2img_thread_func({
                'width': 512,
                'height': 1024,
                'prompt': 'solo, standing, simple background, no background, solid color background, looking at viewer, open mouth, full body standing, from front, ' + global_loaded_json['prompt'],
            })
            self._main_settings.set_image_base64(result_json['images'][0])
        if self.__background_prompt is not None:
            self._generate_prompt = self.__background_prompt
            result_json = self.txt2img_thread_func({
                'width': 608,
                'height': 608,
            })
            self._main_settings.set_background_image_base64(result_json['images'][0])

    def recv_function_streaming(self, messages, function_name, result):
        if function_name != 'sd_generate_character_and_background':
            return None
        
        if result is None:
            return None

        start_run = not self.__is_generate
        if 'character_prompt' in result:
            if self.__character_prompt != result['character_prompt']:
                self.__character_prompt = result['character_prompt']
                start_run = False
        if 'background_prompt' in result:
            if self.__background_prompt != result['background_prompt']:
                self.__background_prompt = result['background_prompt']
                start_run = False
        if start_run:
            self.__is_generate = True
            self.__thread = threading.Thread(target=self.thread_func)
            self.__thread.start()
        
        if 'message' in result:
            return result['message']
        return None

    def recv_function(self, messages, function_name, result):
        if function_name != 'sd_generate_character_and_background':
            return None
        if not self.__is_generate:
            self.__is_generate = True
            self.__character_prompt = result['character_prompt']
            self.__background_prompt = result['background_prompt']
            self.__thread = threading.Thread(target=self.thread_func)
            self.__thread.start()
        if 'message' in result:
            return result['message']
        return '画像を生成しました'

    def recv_message(self, messages):
        if self.__is_generate:
            self.__thread.join()
        self.__is_generate = False

    def get_settings(self):
        return [
            {
                'type': 'Label',
                'text': '画像生成（キャラクター・背景）',
            },
            {
                'type': 'Toggle',
                'name': 'character_enabled',
                'text': 'キャラクターの有効/無効',
                'value': str(self.__loaded_json['character_enabled']),
            },
            {
                'type': 'Toggle',
                'name': 'background_enabled',
                'text': '背景の有効/無効',
                'value': str(self.__loaded_json['background_enabled']),
            },
        ]

    def set_setting(self, name, value):
        self.__loaded_json[name] = value
        json_path = os.path.join(os.path.dirname(__file__), 'chara_and_back_settings.json')
        with open(json_path, 'w') as f:
            json.dump(self.__loaded_json, f)

extension.extensions.append(PictureExtension())
extension.extensions.append(CharacterAndBackgroundExtension())