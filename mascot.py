#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import PIL.Image
import io
from io import StringIO, BytesIO
import numpy
import time
import threading
import torch
import cv2
import json
import argparse
import uvicorn
from fastapi import APIRouter, FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import base64
from contextlib import redirect_stdout
import requests
import re
if os.name == 'nt':
    import pywintypes
    from src.named_pipe import NamedPipeWindows
else:
    from src.named_pipe import NamedPipeUnix
import wave
import subprocess
import shutil

from src.mascot_image import MascotImage
from src.animation_mouth import AnimationMouth
from src.animation_eyes import AnimationEyes
from src.animation_breathing import AnimationBreathing
from src.voice_changer import check_voice_changer, VoiceChangerRVC
from src.named_pipe import NamedPipeAudio
from src import extension
import install

class MascotMainSettings:
    __mascot_image = None
    __background_image = None
    __forward_image = None
    __screen_size = None
    __mascot_chatgpt = None
    __args = None
    __current_path = None

    __image_rembg_model_name = 'isnet-anime'

    def __init__(self, image_mode='standard_float', image_rembg_model_name='isnet-anime'):
        self.__mascot_image = MascotImage(mode=image_mode)
        self.__image_rembg_model_name = image_rembg_model_name
        self.__current_path = os.getcwd()

    @property
    def mascot_image(self):
        return self.__mascot_image

    def set_image_path(self, new_image_path, skip_image_setting=False):
        if new_image_path is not None:
            image = cv2.imread(new_image_path, -1)
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
            if image is not None:
                self.__mascot_image.upload_image(image, skip_image_setting, self.__image_rembg_model_name)
                
    def set_image(self, new_image, skip_image_setting=False):
        image = cv2.imdecode(numpy.frombuffer(new_image, dtype=numpy.uint8), -1)
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
        if image is not None:
            self.__mascot_image.upload_image(image, skip_image_setting, self.__image_rembg_model_name)       

    def set_image_base64(self, new_image, skip_image_setting=False):
        self.set_image(base64.b64decode(new_image), skip_image_setting)

    def set_image_rgba(self, image, skip_image_setting=False):
        if image is not None:
            self.__mascot_image.upload_image(image, skip_image_setting, self.__image_rembg_model_name)      

    @property
    def screen_size(self):
        return self.__screen_size

    @screen_size.setter
    def screen_size(self, size):
        self.__screen_size = size

    @property
    def forward_image(self):
        return self.__forward_image

    def set_forward_image_base64(self, image):
        self.__forward_image = base64.b64decode(image)

    def set_forward_image(self, image):
        self.__forward_image = image

    def set_forward_image_path(self, path):
        with open(path, 'rb') as f:
            self.__forward_image = f.read()

    @property
    def background_image(self):
        return self.__background_image

    def set_background_image_base64(self, image):
        self.__background_image = base64.b64decode(image)

    def set_background_image(self, image):
        self.__background_image = image

    def set_background_image_path(self, path):
        with open(path, 'rb') as f:
            self.__background_image = f.read()

    @property
    def mascot_chatgpt(self):
        return self.__mascot_chatgpt

    @mascot_chatgpt.setter
    def mascot_chatgpt(self, mascot_chatgpt):
        self.__mascot_chatgpt = mascot_chatgpt

    @property
    def args(self):
        return self.__args

    @args.setter
    def args(self, args):
        self.__args = args

    @property
    def current_path(self):
        return self.__current_path

    @current_path.setter
    def current_path(self, current_path):
        self.__current_path = current_path

if __name__ == "__main__":
    for ext_dir_name in os.listdir('extensions'):
        install.install_extensions(ext_dir_name)

    parser = argparse.ArgumentParser()
    parser.add_argument('--select_chara', action='store_true')
    parser.add_argument('--http_host', default='0.0.0.0')
    parser.add_argument('--http_port', type=int, default=55007)
    parser.add_argument('--http_log', default=os.devnull)
    parser.add_argument('--chatgpt_apikey', required=True)
    parser.add_argument('--chatgpt_setting')
    parser.add_argument('--chatgpt_log')
    parser.add_argument('--chatgpt_log_replace', action='store_true')
    parser.add_argument('--chatgpt_model_name', default='gpt-3.5-turbo')
    parser.add_argument('--image')
    parser.add_argument('--skip_image_setting', action='store_true')
    parser.add_argument('--image_rembg_model_name', default='isnet-anime')
    parser.add_argument('--image_mode', default='standard_float')
    parser.add_argument('--framerate', type=float, default=30.0)
    parser.add_argument('--image_pipe_name')
    parser.add_argument('--background_image')
    parser.add_argument('--voicevox_path')
    parser.add_argument('--voicevox_url', default='http://localhost:50021')
    parser.add_argument('--voicevox_speaker_name', default='WhiteCUL')
    parser.add_argument('--voicevox_pitch_scale', type=float, default=0.0)
    parser.add_argument('--voicevox_intonation_scale', type=float, default=1.0)
    parser.add_argument('--voicevox_style_names')
    if os.name == 'nt':
        default_path = '\\\\.\\pipe\\mascot_pipe'
    else:
        default_path = '/tmp/mascot_pipe'
    parser.add_argument('--audio_pipe_name', default=default_path)
    parser.add_argument('--voice_changer_path')
    parser.add_argument('--voice_changer_url', default='http://localhost:18888')
    parser.add_argument('--voice_changer_skip_verify', action='store_true')
    parser.add_argument('--rvc_pytorch_model_file')
    parser.add_argument('--rvc_onnx_model_file')
    parser.add_argument('--rvc_index_file')
    parser.add_argument('--rvc_is_half', action='store_true')
    parser.add_argument('--rvc_model_trans', type=int, default=0)
    parser.add_argument('--run_command')
    parser.add_argument('--run_command_reload', action='store_true')
    parser.add_argument('--ngrok_auth_token')
    parser.add_argument('--show_qrcode', action='store_true')
    parser.add_argument('--bert_vits2_model')
    parser.add_argument('--bert_vits2_model_path')
    parser.add_argument('--bert_vits2_model_file_name')
    for ext in extension.extensions:
        ext.add_argument_to_parser(parser)
    args = parser.parse_args()

    if args.select_chara:
        print('キャラクターを選択してください')
        dir_path = os.path.join(os.path.dirname(__file__), 'charas')
        chara_dir = [
            f for f in os.listdir(dir_path) if os.path.isdir(os.path.join(dir_path, f)) and os.path.isfile(os.path.join(dir_path, f, 'setting.json'))
        ]
        for loop, chara_name in enumerate(chara_dir):
            print(str(loop + 1) + ': ' + chara_name)
        chara_id = int(input('> ')) - 1
        with open(os.path.join(dir_path, chara_dir[chara_id], 'setting.json'), encoding='utf-8') as f:
            chara_dict = json.load(f)
        for k, v in chara_dict.items():
            if k == 'image' or k == 'background_image' or k == 'chatgpt_setting' or k == 'rvc_pytorch_model_file' or k == 'rvc_onnx_model_file' or k == 'rvc_index_file' or k == 'bert_vits2_model_path':
                v = os.path.join(dir_path, chara_dir[chara_id], v)
            setattr(args, k, v)

    main_settings = MascotMainSettings()
    main_settings.args = args
    main_settings.set_image_path(args.image, args.skip_image_setting)
    main_settings.set_background_image_path(args.background_image)

    http_url = ''
    image_tcp_protocol = 'tcp'
    image_tcp_url = '/stream'
    image_tcp_port = 55009
    if args.ngrok_auth_token is not None:
        from pyngrok import ngrok, conf
        conf.get_default().auth_token = args.ngrok_auth_token
        http_url = ngrok.connect(55007, "http").public_url
        image_tcp_url = ngrok.connect(image_tcp_port, image_tcp_protocol).public_url + image_tcp_url
        image_tcp_protocol = ''
        image_tcp_port = 0

    if args.rvc_pytorch_model_file == '':
        args.rvc_pytorch_model_file = None
    if args.rvc_onnx_model_file == '':
        args.rvc_onnx_model_file = None
    if args.voicevox_path == '':
        args.voicevox_path = None
    if args.voicevox_url == '':
        args.voicevox_url = None

    current_path = os.getcwd()
    if args.voicevox_path is not None:
        os.chdir(os.path.dirname(args.voicevox_path))
        subprocess.Popen(os.path.basename(args.voicevox_path))
        os.chdir(current_path)
    if args.voice_changer_path is not None and (args.rvc_pytorch_model_file is not None or args.rvc_onnx_model_file is not None):
        os.chdir(os.path.dirname(args.voice_changer_path))
        subprocess.Popen(os.path.basename(args.voice_changer_path))
        os.chdir(current_path)

    voice_changer = None
    if args.voice_changer_path is not None and (args.rvc_pytorch_model_file is not None or args.rvc_onnx_model_file is not None):
        while voice_changer is None:
            if check_voice_changer(args.voice_changer_url, not args.voice_changer_skip_verify):
                voice_changer = VoiceChangerRVC(args.voice_changer_url, not args.voice_changer_skip_verify)
                result = voice_changer.load(args.rvc_pytorch_model_file,
                    args.rvc_onnx_model_file,
                    args.rvc_index_file,
                    args.rvc_is_half,
                    args.rvc_model_trans
                )
                voice_changer.test(bytes(48000 * 2))
            else:
                time.sleep(0.01)
    else:
        if args.rvc_pytorch_model_file is not None or args.rvc_onnx_model_file is not None:
            if check_voice_changer(args.voice_changer_url, not args.voice_changer_skip_verify):
                voice_changer = VoiceChangerRVC(args.voice_changer_url, not args.voice_changer_skip_verify)
                result = voice_changer.load(args.rvc_pytorch_model_file,
                    args.rvc_onnx_model_file,
                    args.rvc_index_file,
                    args.rvc_is_half,
                    args.rvc_model_trans
                )
                voice_changer.test(bytes(48000 * 2))
            else:
                print("WARNING: voice_changer is not launch.", file=sys.stderr)

    style_names = []
    style_ids = []
    res = None
    if args.voicevox_url is not None:
        while res is None:
            try:
                res = requests.get(args.voicevox_url + '/speakers')
            except requests.exceptions.ConnectionError:
                res = None
                if args.voicevox_path is None:
                    print("ERROR: VOICEVOX is not launch.", file=sys.stderr)
                    exit()
        res_data = res.json()
        for speaker in res_data:
            if speaker['name'] == args.voicevox_speaker_name:
                if args.voicevox_style_names is None:
                    for style in speaker['styles']:
                        style_names.append(style['name'])
                        style_ids.append(style['id'])
                else:
                    style_args_list = args.voicevox_style_names.replace(' ', '').split(',')
                    for style_arg in style_args_list:
                        for style in speaker['styles']:
                            if style_arg == style['name']:
                                style_names.append(style['name'])
                                style_ids.append(style['id'])
        #if args.voicevox_speaker_name == 'WhiteCUL':
        #    style_names = ['normal', 'happy', 'sad', 'crying']
        if len(style_ids) <= 0:
            print("ERROR: Undefined speaker name.", file=sys.stderr)
            exit()
    else:
        style_names = ['Neutral']
        style_ids = ['Neutral']

    audio_freq = 48000
    if args.bert_vits2_model is not None:
        if args.bert_vits2_model_path is not None:
            shutil.copytree(args.bert_vits2_model_path, os.path.join('Style-Bert-VITS2', 'model_assets', args.bert_vits2_model))
        os.chdir('Style-Bert-VITS2')
        subprocess.Popen(['python', 'server_editor.py'])
        os.chdir(current_path)
        audio_freq = 44100
        res = None
        while res is None:
            time.sleep(0.1)
            try:
                res = requests.get('http://localhost:8000/api/version')
            except requests.exceptions.ConnectionError:
                res = None

    mascot_chatgpt = None
    if args.chatgpt_apikey is not None:
        from src.mascot_chatgpt import MascotChatGpt
        mascot_chatgpt = MascotChatGpt(args.chatgpt_apikey)
        mascot_chatgpt.load_model(args.chatgpt_model_name)
        if args.chatgpt_setting is not None and os.path.isfile(args.chatgpt_setting):
            mascot_chatgpt.load_setting(args.chatgpt_setting, style_names)
        if not args.chatgpt_log_replace and args.chatgpt_log is not None:
            mascot_chatgpt.load_log(args.chatgpt_log)
    main_settings.mascot_chatgpt = mascot_chatgpt
    
    for ext in extension.extensions:
        ext.init(main_settings)

    http_app = FastAPI()
    http_router = APIRouter()

    mascot_image = main_settings.mascot_image
    animation_mouth = AnimationMouth(mascot_image)
    animation_eyes = AnimationEyes(mascot_image)
    animation_breathing = AnimationBreathing(mascot_image)

    #class UpdateImageRequest(BaseModel):
    #    image: str
    #    skip_setting: bool = False

    #def http_upload_image(image: UpdateImageRequest):
    #    f = base64.b64decode(image.image)
    #    numpy_content = cv2.imdecode(numpy.frombuffer(f, dtype=numpy.uint8), -1)
    #    numpy_content = cv2.cvtColor(numpy_content, cv2.COLOR_BGRA2RGBA)
    #    ret = mascot_image.upload_image(numpy_content, image.skip_setting)
    #    json_compatible_item_data = jsonable_encoder({'success': ret})
    #    return JSONResponse(content=json_compatible_item_data)
    #http_router.add_api_route("/upload_image", http_upload_image, methods=["POST"])

    recv_mouth_queries = []
    recv_time_length = 0.0
    recv_response_message = ''
    recv_is_finished = False

    class SendMessageRequest(BaseModel):
        message: str

    def http_send_message(request: SendMessageRequest):
        global recv_mascot_chatgpt
        global recv_mouth_queries
        global recv_response_message
        global recv_is_finished

        if mascot_chatgpt is None or mascot_image is None:
            json_compatible_item_data = jsonable_encoder({'success': False})
            return JSONResponse(content=json_compatible_item_data)

        response_values = mascot_chatgpt.send_to_chatgpt(request.message)
        if not response_values:
            json_compatible_item_data = jsonable_encoder({'success': False})
            return JSONResponse(content=json_compatible_item_data)

        recv_mouth_queries = []
        recv_time_length = 0.0
        recv_response_message = ''
        recv_is_finished = False

        recv_thread = threading.Thread(target=recv_message)
        recv_thread.start()

        json_compatible_item_data = jsonable_encoder({
            'success': True
            })
        return JSONResponse(content=json_compatible_item_data)
    http_router.add_api_route("/send_message", http_send_message, methods=["POST"])

    def recv_message():
        global mascot_image
        global mascot_chatgpt
        global args
        global animation_mouth
        global audio_pipe
        global style_names
        global style_ids
        global animation_eyes
        global recv_mouth_queries
        global recv_time_length
        global recv_response_message
        global recv_is_finished

        mouth_queries = []
        time_length = 0.0
        response_message = ''
        is_finished = False

        recv_start_time = 0.0

        recv_mouth_queries = mouth_queries
        recv_time_length = time_length
        recv_response_message = response_message
        recv_is_finished = False

        while not is_finished:
            is_start = len(mouth_queries) == 0

            is_finished, response_voice_style, response_eyebrow, response_eyes = mascot_chatgpt.get_states()

            speaker_id = style_ids[0]
            for s_id, s_name in enumerate(style_names):
                if s_name == response_voice_style:
                    speaker_id = style_ids[s_id]
                    break

            _, response_message = mascot_chatgpt.get_message()

            s = re.sub(r'([。\.！\!？\?]+)', r'\1\n', response_message)
            messages = s.splitlines()[len(mouth_queries):]
            if not is_finished:
                if len(messages) <= 0:
                    response_message = ''
                    messages = []
                else:
                    response_message = response_message[:-len(messages[-1])]
                    messages = messages[:-1]

            if args.bert_vits2_model is None:
                for mes in messages:
                    vc_input = b''

                    res1 = requests.post(args.voicevox_url + '/audio_query', params = {'text': mes, 'speaker': speaker_id})
                    res1_data = res1.json()
                    res1_data['prePhonemeLength'] = 0.02
                    res1_data['postPhonemeLength'] = 0.08
                    res1_data['outputSamplingRate'] = audio_freq
                    res1_data['pitchScale'] = args.voicevox_pitch_scale
                    res1_data['intonationScale'] = args.voicevox_intonation_scale
                    res2 = requests.post(args.voicevox_url + '/synthesis', params = {'speaker': speaker_id}, data=json.dumps(res1_data))
                    
                    file_in_memory = BytesIO(res2.content)
                    with wave.open(file_in_memory, 'rb') as wav_file:
                        vc_input += wav_file.readframes(wav_file.getnframes())

                    if voice_changer is not None:
                        vc_output = voice_changer.test(vc_input)
                    else:
                        vc_output = vc_input
                    audio_pipe.add_bytes(vc_output)

                    mouth_queries.append(res1_data)

                    if recv_start_time == 0.0:
                        recv_start_time = time.perf_counter()
                    else:
                        now_time = time.perf_counter() - recv_start_time
                        if time_length < now_time:
                            time_length = now_time
                    time_length += animation_mouth.set_audio_query(res1_data)
                    animation_eyes.set_morph(response_eyes, time_length, is_start)

                    if response_eyebrow == 'normal':
                        mascot_image.set_eyebrow(0, 0.0, 0.0)
                    else:
                        mascot_image.set_eyebrow(response_eyebrow, 1.0, 1.0)

                    recv_mouth_queries = mouth_queries
                    recv_time_length = time_length
                    recv_response_message = response_message[:len(recv_response_message) + len(mes)]
            else:
                for mes in messages:
                    vc_output = b''
                    g2p_res = requests.post('http://localhost:8000/api/g2p', data=json.dumps({'text': mes}))
                    synth_data = {
                        'model': args.bert_vits2_model,
                        'modelFile': os.path.join('model_assets', args.bert_vits2_model, args.bert_vits2_model_file_name),
                        'text': mes,
                        'moraToneList': g2p_res.json(),
                        'silenceAfter': 0.08
                    }
                    synth_res = requests.post('http://localhost:8000/api/synthesis', data=json.dumps(synth_data))

                    file_in_memory = BytesIO(synth_res.content)
                    with wave.open(file_in_memory, 'rb') as wav_file:
                        vc_output += wav_file.readframes(wav_file.getnframes())

                    audio_pipe.add_bytes(vc_output)

                    mouth_queries.append({
                        'prePhonemeLength': 0.0,
                        'postPhonemeLength': synth_data['silenceAfter']
                    })

                    if recv_start_time == 0.0:
                        recv_start_time = time.perf_counter()
                    else:
                        now_time = time.perf_counter() - recv_start_time
                        if time_length < now_time:
                            time_length = now_time
                    time_length += animation_mouth.set_by_mora_tone_list(synth_data['moraToneList'], vc_output, synth_data['silenceAfter'])
                    animation_eyes.set_morph(response_eyes, time_length, is_start)

                    if response_eyebrow == 'normal':
                        mascot_image.set_eyebrow(0, 0.0, 0.0)
                    else:
                        mascot_image.set_eyebrow(response_eyebrow, 1.0, 1.0)

                    recv_mouth_queries = mouth_queries
                    recv_time_length = time_length
                    recv_response_message = response_message[:len(recv_response_message) + len(mes)]
            
            recv_is_finished = is_finished

    def http_recv_message():
        global recv_mouth_queries
        global recv_time_length
        global recv_response_message
        global recv_is_finished
        if len(recv_mouth_queries) <= 0:
            json_compatible_item_data = jsonable_encoder({
                'success': True,
                'message': '',
                'start': 0.0,
                'end': 0.0,
                'finished': False
                })
            return JSONResponse(content=json_compatible_item_data)
        else:
            json_compatible_item_data = jsonable_encoder({
                'success': True,
                'message': recv_response_message,
                'start': recv_mouth_queries[0]['prePhonemeLength'],
                'end': recv_time_length - recv_mouth_queries[-1]['postPhonemeLength'],
                'finished': recv_is_finished
                })
            return JSONResponse(content=json_compatible_item_data)
    http_router.add_api_route("/recv_message", http_recv_message, methods=["GET"])

    open_qrcode = False

    def http_get_tcp_url():
        global image_tcp_url
        global image_tcp_port
        #global open_qrcode
        #open_qrcode = False
        json_compatible_item_data = jsonable_encoder({
            'success': True,
            'local': args.run_command is None or not 'ffmpeg' in args.run_command,
            'protocol': image_tcp_protocol,
            'url': image_tcp_url,
            'port': image_tcp_port
            })
        return JSONResponse(content=json_compatible_item_data)
    http_router.add_api_route("/get_tcp_url", http_get_tcp_url, methods=["GET"])

    class BodyMorphRequest(BaseModel):
        iris_rotation_x: float
        iris_rotation_y: float
        head_x: float
        head_y: float
        body_y: float

    def http_body_morph(request: BodyMorphRequest):
        global mascot_image
        mascot_image.set_body_morph(request.iris_rotation_x, request.iris_rotation_y, request.head_x, request.head_y, request.body_y)
        json_compatible_item_data = jsonable_encoder({
            'success': True
            })
        return JSONResponse(content=json_compatible_item_data)
    http_router.add_api_route("/body_morph", http_body_morph, methods=["POST"])

    def http_background():
        global current_path
        global main_settings
        background_image = main_settings.background_image
        if background_image is None:
            return JSONResponse(content={'success': False}, status_code=404)
        response = Response(
            content=background_image
            )
        return response
    http_router.add_api_route("/background", http_background, methods=["GET"])

    def http_forward_image():
        global current_path
        global main_settings
        forward_image = main_settings.forward_image
        if forward_image is None:
            return JSONResponse(content={'success': False}, status_code=404)
        response = Response(
            content=forward_image
            )
        return response
    http_router.add_api_route("/forward_image", http_forward_image, methods=["GET"])

    class ScreenSizeRequest(BaseModel):
        width: int
        height: int

    def http_screen_size(request: ScreenSizeRequest):
        global main_settings
        main_settings.screen_size = (request.width, request.height)
        json_compatible_item_data = jsonable_encoder({
            'success': True
            })
        return JSONResponse(content=json_compatible_item_data)
    http_router.add_api_route("/screen_size", http_screen_size, methods=["POST"])

    def http_get_settings():
        settings = []
        for index, ext in enumerate(extension.extensions):
            ext_settings = ext.get_settings()
            if ext_settings is not None:
                for setting in ext_settings:
                    setting['index'] = index
                    settings.append(setting)
        json_compatible_item_data = jsonable_encoder({
            'success': True,
            'settings': settings,
            })
        return JSONResponse(content=json_compatible_item_data)
    http_router.add_api_route("/get_settings", http_get_settings, methods=["GET"])

    class SetSettingRequest(BaseModel):
        index: int
        name: str
        value: str

    def http_set_setting(request: SetSettingRequest):
        extension.extensions[request.index].set_setting(request.name, request.value)
        json_compatible_item_data = jsonable_encoder({
            'success': True,
            })
        return JSONResponse(content=json_compatible_item_data)
    http_router.add_api_route("/set_setting", http_set_setting, methods=["POST"])

    def http_get_audio_freq():
        json_compatible_item_data = jsonable_encoder({
            'success': True,
            'audio_freq': audio_freq,
            })
        return JSONResponse(content=json_compatible_item_data)
    http_router.add_api_route("/get_audio_freq", http_get_audio_freq, methods=["GET"])

    stop_main_thread = False

    default_stdout = sys.stdout

    start_time = 0.0

    mascot_image.update()

    def main_thread_func():
        global image_pipe

        while not stop_main_thread:
            image_pipe = None
            if args.image_pipe_name is not None:
                if os.name == 'nt':
                    image_pipe = NamedPipeWindows()
                else:
                    image_pipe = NamedPipeUnix()
                image_pipe.create(args.image_pipe_name)
            if start_time == 0.0:
                next_time = time.perf_counter() + 1.0 / args.framerate
            else:
                next_time = start_time + 1.0 / args.framerate
            try:
                while not stop_main_thread:
                    animation_mouth.update(1.0 / args.framerate)
                    animation_eyes.update(1.0 / args.framerate)
                    animation_breathing.update(1.0 / args.framerate)
                    span = next_time - time.perf_counter()
                    if span > 0.0:
                        mascot_image.update()
                    img = mascot_image.get_numpy_image()
                    if img is not None:
                        if image_pipe is None:
                            with redirect_stdout(default_stdout):
                                sys.stdout.buffer.write(img.tobytes())
                        else:
                            image_pipe.write(img.tobytes())
                    span = next_time - time.perf_counter()
                    if span > 0.0:
                        time.sleep(span)
                    next_time += 1.0 / args.framerate
            except BrokenPipeError:
                pass

            if image_pipe is not None:
                image_pipe.close()

    def audio_thread_func():
        global audio_pipe
        global new_pipe

        audio_pipe = NamedPipeAudio()

        while not stop_main_thread:
            if os.name == 'nt':
                new_pipe = NamedPipeWindows()
            else:
                new_pipe = NamedPipeUnix()
            new_pipe.create(args.audio_pipe_name)
            audio_pipe.set_pipe(new_pipe)
            if start_time == 0.0:
                prev_time = time.perf_counter()
            else:
                prev_time = start_time
            try:
                while not stop_main_thread:
                    frame_size = int((time.perf_counter() - prev_time) * audio_freq)
                    frame_size = audio_pipe.write_audio_frame(frame_size)
                    prev_time += frame_size / audio_freq
                    time.sleep(0.0)
            except BrokenPipeError:
                pass
            
            new_pipe.close()
            audio_pipe.set_pipe(None)
    
    def start_threads():
        global stop_main_thread
        global start_time
        global audio_thread
        global main_thread

        stop_main_thread = False

        if args.run_command is not None and 'ffmpeg' in args.run_command:
            start_time = time.perf_counter()
        else:
            start_time = 0.0

        audio_thread = threading.Thread(target=audio_thread_func)
        audio_thread.start()

        main_thread = threading.Thread(target=main_thread_func)
        main_thread.start()

    start_threads()

    def show_qrcode():
        if args.ngrok_auth_token is not None:
            #print('---')
            #print('Public URL is here: ' + http_url)
            #print('---')
            if args.show_qrcode:
                import qrcode
                qrcode_pil = qrcode.make('mascotgirl://' + http_url)
                qrcode_cv2 = numpy.array(qrcode_pil, dtype=numpy.uint8) * 255
                def qrcode_thread_func():
                    global open_qrcode
                    open_qrcode = True
                    cv2.imshow('Please scan.', qrcode_cv2)
                    while open_qrcode:
                        cv2.waitKey(1)
                qrcode_thread = threading.Thread(target=qrcode_thread_func)
                qrcode_thread.start()

    def stop_threads():
        global stop_main_thread
        global audio_thread
        global main_thread
        stop_main_thread = True
        if args.image_pipe_name is not None:
            while main_thread.is_alive():
                image_pipe.force_close()
                time.sleep(0.1)
        while audio_thread.is_alive():
            new_pipe.force_close()
            time.sleep(0.1)

    is_exiting = False

    if args.run_command is not None:
        if args.run_command_reload:
            def command_thread_func():
                global open_qrcode
                global is_exiting
                while True:
                    command_process = subprocess.Popen(args.run_command.split(), stderr=subprocess.PIPE, universal_newlines=True)
                    for line in command_process.stderr:
                        if '  Stream #1:0: Audio:' in line:
                            show_qrcode()
                    stop_threads()
                    if is_exiting:
                        break
                    start_threads()

            command_thread = threading.Thread(target=command_thread_func)
            command_thread.start()
        else:
            subprocess.Popen(args.run_command)

    http_app.include_router(http_router)
    #http_app.mount("/dash", StaticFiles(directory="dash"), name="dash")
    with redirect_stdout(open(args.http_log, 'w')):
        uvicorn.run(http_app, host=args.http_host, port=args.http_port)

    open_qrcode = False
    is_exiting = True

    stop_threads()

    try:
        cv2.destroyWindow('Please scan.')
        cv2.waitKey(1)
    except cv2.error:
        pass
