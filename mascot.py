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
from fastapi.responses import JSONResponse
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

from src.mascot_image import MascotImage
from src.animation_mouth import AnimationMouth
from src.animation_eyes import AnimationEyes
from src.voice_changer import check_voice_changer, VoiceChangerRVC
from src.named_pipe import NamedPipeAudio

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
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
    parser.add_argument('--image_mode', default='standard_float')
    parser.add_argument('--framerate', type=float, default=30.0)
    parser.add_argument('--image_pipe_name')
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
    parser.add_argument('--rvc_feature_file')
    parser.add_argument('--rvc_index_file')
    parser.add_argument('--rvc_is_half', action='store_true')
    parser.add_argument('--rvc_model_trans', type=int, default=0)
    parser.add_argument('--run_command')
    parser.add_argument('--run_command_reload', action='store_true')
    parser.add_argument('--ngrok_auth_token')
    args = parser.parse_args()

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

    current_path = os.getcwd()
    if args.voicevox_path is not None:
        os.chdir(os.path.dirname(args.voicevox_path))
        subprocess.Popen(args.voicevox_path)
    if args.voice_changer_path is not None and (args.rvc_pytorch_model_file is not None or args.rvc_onnx_model_file is not None):
        os.chdir(os.path.dirname(args.voice_changer_path))
        subprocess.Popen(args.voice_changer_path)
    os.chdir(current_path)

    voice_changer = None
    if args.voice_changer_path is not None and (args.rvc_pytorch_model_file is not None or args.rvc_onnx_model_file is not None):
        while voice_changer is None:
            if check_voice_changer(args.voice_changer_url, not args.voice_changer_skip_verify):
                voice_changer = VoiceChangerRVC(args.voice_changer_url, not args.voice_changer_skip_verify)
                result = voice_changer.load(args.rvc_pytorch_model_file,
                    args.rvc_onnx_model_file,
                    args.rvc_feature_file,
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
                    args.rvc_feature_file,
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

    mascot_chatgpt = None
    if args.chatgpt_apikey is not None:
        from src.mascot_chatgpt import MascotChatGpt
        mascot_chatgpt = MascotChatGpt(args.chatgpt_apikey)
        mascot_chatgpt.load_model(args.chatgpt_model_name)
        if args.chatgpt_setting is not None and os.path.isfile(args.chatgpt_setting):
            mascot_chatgpt.load_setting(args.chatgpt_setting, style_names)
        if not args.chatgpt_log_replace and args.chatgpt_log is not None:
            mascot_chatgpt.load_log(args.chatgpt_log)

    mascot_image = MascotImage()

    if args.image is not None:
        image = cv2.imread(args.image, -1)
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
        if image is not None:
            mascot_image.upload_image(image, args.skip_image_setting)

    http_app = FastAPI()
    http_router = APIRouter()

    animation_mouth = AnimationMouth(mascot_image)
    animation_eyes = AnimationEyes(mascot_image)

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

            if len(messages) <= 0:
                recv_mouth_queries = mouth_queries
                recv_time_length = time_length
                recv_response_message = response_message
                recv_is_finished = is_finished
                continue

            for mes in messages:
                vc_input = b''

                res1 = requests.post(args.voicevox_url + '/audio_query', params = {'text': mes, 'speaker': speaker_id})
                res1_data = res1.json()
                res1_data['prePhonemeLength'] = 0.02
                res1_data['postPhonemeLength'] = 0.08
                res1_data['outputSamplingRate'] = 48000
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

    def http_get_tcp_url():
        global image_tcp_url
        global image_tcp_port
        json_compatible_item_data = jsonable_encoder({
            'success': True,
            'local': args.run_command is None or not 'ffmpeg' in args.run_command,
            'protocol': image_tcp_protocol,
            'url': image_tcp_url,
            'port': image_tcp_port
            })
        return JSONResponse(content=json_compatible_item_data)
    http_router.add_api_route("/get_tcp_url", http_get_tcp_url, methods=["GET"])

    stop_main_thread = False

    default_stdout = sys.stdout

    if args.run_command is not None and 'ffmpeg' in args.run_command:
        start_time = time.perf_counter()
    else:
        start_time = 0.0

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
                    frame_size = int((time.perf_counter() - prev_time) * 48000)
                    frame_size = audio_pipe.write_audio_frame(frame_size)
                    prev_time += frame_size / 48000
                    time.sleep(0.0)
            except BrokenPipeError:
                pass
            
            new_pipe.close()
            audio_pipe.set_pipe(None)
    
    audio_thread = threading.Thread(target=audio_thread_func)
    audio_thread.start()

    main_thread = threading.Thread(target=main_thread_func)
    main_thread.start()

    if args.ngrok_auth_token is not None:
        print('---')
        print('Public URL is here: ' + http_url)
        print('---')

    if args.run_command is not None:
        if args.run_command_reload:
            def command_thread_func():
                while not stop_main_thread:
                    subprocess.run(args.run_command.split())

            command_thread = threading.Thread(target=command_thread_func)
            command_thread.start()
        else:
            subprocess.Popen(args.run_command)

    http_app.include_router(http_router)
    #http_app.mount("/dash", StaticFiles(directory="dash"), name="dash")
    with redirect_stdout(open(args.http_log, 'w')):
        uvicorn.run(http_app, host=args.http_host, port=args.http_port)

    stop_main_thread = True
    if args.image_pipe_name is not None:
        while main_thread.is_alive():
            image_pipe.force_close()
            time.sleep(0.1)
    while audio_thread.is_alive():
        new_pipe.force_close()
        time.sleep(0.1)
        