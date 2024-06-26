#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import threading
import os
import json
import copy
import cv2
import numpy
import base64
import subprocess
from typing import Optional

from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import StructuredTool

from src import extension
import image_setting

global_loaded_json = None
global_loaded_json_raw_txt = None
global_url_is_added_args = False
global_launch_sd = False

class SDTxt2ImgExtension(extension.Extension):
    _url = 'http://127.0.0.1:7860'
    _generate_prompt = None
    _main_settings = None
    _keywords_json = None
    _keywords_json_raw_txt = None

    def add_argument_to_parser(self, parser):
        global global_url_is_added_args
        if not global_url_is_added_args:
            parser.add_argument('--sd_url', default='http://127.0.0.1:7860')
            parser.add_argument('--sd_path')
            global_url_is_added_args = True

    def init(self, main_settings):
        global global_loaded_json
        global global_loaded_json_raw_txt
        global global_launch_sd
        self._main_settings = main_settings
        self._url = main_settings.args.sd_url
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
        if not global_launch_sd and main_settings.args.sd_path is not None:
            run_path = os.path.join(main_settings.current_path, main_settings.args.sd_path)
            command = []
            if os.path.basename(run_path) == 'run.bat':
                command += ['cd', os.path.dirname(run_path), '&&', 'call', 'environment.bat', '&&', 'cd', os.path.join(os.path.dirname(run_path), 'webui'), '&&']
            else:
                command += ['cd', os.path.dirname(run_path), '&&']
            with open(os.path.join(os.path.dirname(run_path), 'webui', 'config.json'), 'r') as f:
                config_json = json.load(f)
            config_json['auto_launch_browser'] = 'Disable'
            with open(os.path.join(os.path.dirname(__file__), 'config.json'), 'w') as f:
                json.dump(config_json, f)
            command += ['set', 'COMMANDLINE_ARGS=--api', '--ui-settings-file', os.path.join(os.path.dirname(__file__), 'config.json').replace('\\', '\\\\'), '&&']
            command += ['call', 'webui.bat']
            subprocess.Popen(command, shell=True)
            global_launch_sd = True

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

        request_result = requests.post(self._url + '/sdapi/v1/txt2img', data=json.dumps(loaded_json))
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

    def get_langchain_tools(self):
        class ToolInput(BaseModel):
            prompt: str = Field(description='Prompt for generate image. Prompt is comma separated keywords such as "1girl, school uniform, red ribbon". If it is not in English, please translate it into English (lang:en).')

        def tool_function(prompt: str) -> str:
            self.recv_function(None, chatgpt_functions["name"], {"prompt": prompt})
            return 'Success.'

        chatgpt_functions = self.get_chatgpt_functions()
        tool = StructuredTool.from_function(
            func=tool_function,
            name=chatgpt_functions[0]["name"],
            description=chatgpt_functions[0]["description"],
            args_schema=ToolInput,
            #return_direct=True,
        )

        return [tool, ]

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
            if value == 'True':
                self.__loaded_json[name] = True
            elif value == 'False':
                self.__loaded_json[name] = False
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
    __new_chara_image = None
    __face_image_base64 = None
    __use_controlnet = False

    def check_controlnet(self):
        if not self.__use_controlnet:
            try:
                request_result = requests.get(self._url + '/sdapi/v1/scripts')
                if 'controlnet' in request_result.json()['txt2img']:
                    request_result = requests.get(self._url + '/controlnet/model_list')
                    for full_name in request_result.json()['model_list']:
                        if 'openpose' in full_name:
                            self.__use_controlnet = True
                            break
            except:
                pass

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
                'use_controlnet': True,
            }

        self.check_controlnet()

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
    solo, standing, simple background, no background, solid color background, looking at viewer, open mouth, from front
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

    def get_langchain_tools(self):
        class ToolInput(BaseModel):
            character_prompt: str = Field(description='''Prompt for generate character image.
The following are included from the beginning:
    solo, standing, simple background, no background, solid color background, looking at viewer, open mouth, from front
''')

        def tool_function(character_prompt: str) -> str:
            self.recv_function(None, chatgpt_functions[0]["name"], {"character_prompt": character_prompt})
            return 'Success.'

        chatgpt_functions = self.get_chatgpt_functions()
        tool = StructuredTool.from_function(
            func=tool_function,
            name="sd_generate_character",
            description="""Generate character image from prompt by Stable Diffusion.
This character is your alter ego.
Please call it when your appearance changes by saying something like "change your outfit".
Prompt is comma separated keywords such as "1girl, school uniform, red ribbon". If it is not in English, please translate it into English (lang:en).

Sentences cannot be generated.
There is no memory function, so please carry over the prompts from past conversations.
""",
            args_schema=ToolInput,
            #return_direct=True,
        )

        class BackToolInput(BaseModel):
            background_prompt: str = Field(description='Prompt for generate background image.')

        def back_tool_function(background_prompt: str) -> str:
            self.recv_function(None, chatgpt_functions[0]["name"], {"background_prompt": background_prompt})
            return 'Success.'

        back_tool = StructuredTool.from_function(
            func=back_tool_function,
            name="sd_generate_background",
            description="""Generate background image from prompt by Stable Diffusion.
The background is based on your location.
Please call it when your location changes by saying something like "move location".
Prompt is comma separated keywords such as "outdoor, sea". If it is not in English, please translate it into English (lang:en).

Sentences cannot be generated.
There is no memory function, so please carry over the prompts from past conversations.
""",
            args_schema=BackToolInput,
            #return_direct=True,
        )

        return [tool, back_tool]

    def thread_func(self):
        global global_loaded_json

        if self.__character_prompt is not None:
            self._generate_prompt = self.__character_prompt
            self.check_controlnet()
            if self.__use_controlnet and ((not 'use_controlnet' in self.__loaded_json) or self.__loaded_json['use_controlnet']):
                if self.__face_image_base64 is None:
                    with open(os.path.join(os.path.dirname(__file__), 'openpose_face.png'), 'rb') as f:
                        file_bytes = f.read()
                    self.__face_image_base64 = base64.b64encode(file_bytes).decode('utf-8')
                result_json = self.txt2img_thread_func({
                    'width': 512,
                    'height': 512,
                    'prompt': 'solo, standing, simple background, no background, solid color background, looking at viewer, open mouth, from front, ' + global_loaded_json['prompt'],
                    'alwayson_scripts': {
                        "controlnet": {
                            "args": [
                                {
                                    "enabled": True,
                                    "module": "none",
                                    "model": "openpose",
                                    "weight": 1.0,
                                    "image": self.__face_image_base64,
                                    "resize_mode": 1,
                                    "lowvram": False,
                                    "guidance_start": 0.0,
                                    "guidance_end": 1.0,
                                    "control_mode": 1,
                                    "pixel_perfect": False
                                }
                            ]
                        }
                    }
                })
                image = cv2.imdecode(numpy.frombuffer(base64.b64decode(result_json['images'][0]), dtype=numpy.uint8), -1)
                image = cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
                self.__new_chara_image = image_setting.image_setting(image, skip_reshape=True)
            else:
                result_json = self.txt2img_thread_func({
                    'width': 512,
                    'height': 1024,
                    'prompt': 'solo, standing, simple background, no background, solid color background, looking at viewer, open mouth, from front, full body standing, ' + global_loaded_json['prompt'],
                })
                image = cv2.imdecode(numpy.frombuffer(base64.b64decode(result_json['images'][0]), dtype=numpy.uint8), -1)
                image = cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
                self.__new_chara_image = image_setting.image_setting(image)
        else:
            self.__new_chara_image = None
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
        if 'character_prompt' in result and self.__loaded_json['character_enabled']:
            if self.__character_prompt != result['character_prompt']:
                self.__character_prompt = result['character_prompt']
                start_run = False
        if 'background_prompt' in result and self.__loaded_json['background_enabled']:
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
            if self.__loaded_json['character_enabled'] and 'character_prompt' in result:
                self.__character_prompt = result['character_prompt']
            if self.__loaded_json['background_enabled'] and 'background_prompt' in result:
                self.__background_prompt = result['background_prompt']
            self.__thread = threading.Thread(target=self.thread_func)
            self.__thread.start()
        if 'message' in result:
            return result['message']
        return '画像を生成しました'

    def recv_message(self, messages):
        if self.__is_generate:
            self.__thread.join()
            if self.__new_chara_image is not None:
                self._main_settings.set_image_rgba(self.__new_chara_image, True)
        self.__is_generate = False

    def get_settings(self):
        ret = [
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
        self.check_controlnet()
        if self.__use_controlnet:
            ret += [
                {
                    'type': 'Toggle',
                    'name': 'use_controlnet',
                    'text': 'キャラクター生成時にcontrolnet(openpose)を使用するか',
                    'value': str(self.__loaded_json['use_controlnet']),
                },
            ]
        return ret

    def set_setting(self, name, value):
        if value == 'True':
            self.__loaded_json[name] = True
        elif value == 'False':
            self.__loaded_json[name] = False
        else:
            self.__loaded_json[name] = value
        json_path = os.path.join(os.path.dirname(__file__), 'chara_and_back_settings.json')
        with open(json_path, 'w') as f:
            json.dump(self.__loaded_json, f)

extension.extensions.append(PictureExtension())
extension.extensions.append(CharacterAndBackgroundExtension())