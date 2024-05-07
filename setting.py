#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

if __name__ == "__main__":

    run_bat_content = r'''
@echo off
setlocal
set PATH=%~dp0bin\Miniconda3;%~dp0bin\Miniconda3\condabin;%~dp0bin\Miniconda3\Library\mingw-w64\bin;%~dp0bin\Miniconda3\Library\usr\bin;%~dp0bin\Miniconda3\Library\bin;%~dp0bin\Miniconda3\Scripts;%PATH%
call %~dp0bin\Miniconda3\condabin\conda activate mascotgirl
cd mascotgirl
python mascot.py ^
    --select_chara ^
    --ignore_extensions ^
    --voicevox_url "" ^
    --chat_backend "OpenAIAssistant" ^
    --chatgpt_apikey "__CHATGPT_APIKEY__" ^
    --chatgpt_model_name "__CHATGPT_MODEL_NAME__" ^
    --chatgpt_log "chatgpt.json" ^
    --chatgpt_log_replace ^
    --image_pipe_name "\\.\pipe\mascot_image_pipe" ^
    --run_command "client\MascotGirl_Client.exe -start_local"
cd ..
call %~dp0bin\Miniconda3\condabin\conda deactivate
endlocal
    '''

    run_share_bat_content = r'''
@echo off
setlocal
set PATH=%~dp0bin\Miniconda3;%~dp0bin\Miniconda3\condabin;%~dp0bin\Miniconda3\Library\mingw-w64\bin;%~dp0bin\Miniconda3\Library\usr\bin;%~dp0bin\Miniconda3\Library\bin;%~dp0bin\Miniconda3\Scripts;%PATH%
call %~dp0bin\Miniconda3\condabin\conda activate mascotgirl
cd mascotgirl
python mascot.py ^
    --select_chara ^
    --ignore_extensions ^
    --voicevox_url "" ^
    --chat_backend "OpenAIAssistant" ^
    --chatgpt_apikey "__CHATGPT_APIKEY__" ^
    --chatgpt_model_name "__CHATGPT_MODEL_NAME__" ^
    --ngrok_auth_token "__NGROK_AUTH_TOKEN__" ^
    --show_qrcode ^
    --chatgpt_log "chatgpt.json" ^
    --chatgpt_log_replace ^
    --image_pipe_name "\\.\pipe\mascot_image_pipe" ^
    --framerate 30 ^
    --run_command_reload ^
    --run_command "ffmpeg\ffmpeg -y -f rawvideo -pix_fmt rgba -s 512x512 -framerate 30 -thread_queue_size 8192 -i \\.\pipe\mascot_image_pipe -f s16le -ar __AUDIO_FREQ__ -ac 1 -thread_queue_size 8192 -i \\.\pipe\mascot_pipe -auto-alt-ref 0 -deadline realtime -quality realtime -cpu-used 4 -row-mt 1 -crf 30 -b:v 0 -pass 1 -c:v libvpx-vp9 -c:a libopus -f matroska tcp://0.0.0.0:55009/stream?listen"
cd ..
call %~dp0bin\Miniconda3\condabin\conda deactivate
endlocal
    '''

    def replace(target: str, content: str):
        global run_bat_content
        global run_share_bat_content
        if content is None:
            content = ''
        run_bat_content = run_bat_content.replace(target, content)
        run_share_bat_content = run_share_bat_content.replace(target, content)

    def is_num(s: str):
        try:
            float(s)
        except ValueError:
            return False
        else:
            return True

    def is_int_num(s: str):
        try:
            int(s)
        except ValueError:
            return False
        else:
            return True

    select = ''
    while select is None or select == '':
        select = input('ChatGPTのAPIキーを入力してください: \n')
    replace('__CHATGPT_APIKEY__', select)

    select = input('使用するChatGPTのモデル名を入力してください (gpt-3.5-turbo): \n')
    if select is None or select == '':
        select = 'gpt-3.5-turbo'
    replace('__CHATGPT_MODEL_NAME__', select)

    replace('__AUDIO_FREQ__', '44100')

    while True:
        select = input('リモート接続機能(Androidなど)を使用しますか？ [y/N]: ')
        if select is None or select == '' or select == 'N' or select == 'n':
            save_share_bat = False
            break
        select = input('ngrokのトークンを入力してください: \n')
        if select is not None or select != '':
            replace('__NGROK_AUTH_TOKEN__', select)
            save_share_bat = True
            break

    if not '\r\n' in run_bat_content:
        run_bat_content.replace('\n', '\r\n')
    with open('run.bat', 'w', encoding='shift_jis') as open_file:
        open_file.write(run_bat_content)
    if save_share_bat:
        if not '\r\n' in run_share_bat_content:
            run_share_bat_content.replace('\n', '\r\n')
        with open('run_share.bat', 'w', encoding='shift_jis') as open_file:
            open_file.write(run_share_bat_content)