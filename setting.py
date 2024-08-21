#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

if __name__ == "__main__":

    run_bat_content = r'''@echo off
setlocal
__SET_PATH__
call __CONDA__ activate mascotgirl
cd mascotgirl
python mascot.py ^
    --select_chara ^
    __IGNORE_EXTENSIONS__ ^
    --voicevox_url "" ^
    --chat_backend "__CHAT_BACKEND__" ^
    __CHAT_OPTION__ ^
    --chatgpt_log "chatgpt.json" ^
    --chatgpt_log_replace ^
    --image_pipe_name "\\.\pipe\mascot_image_pipe" ^
    --framerate 30 ^
    --run_command_reload ^
    --run_command "ffmpeg\ffmpeg -y -f rawvideo -pix_fmt rgba -s 512x512 -framerate 30 -thread_queue_size 8192 -i \\.\pipe\mascot_image_pipe -f s16le -ar __AUDIO_FREQ__ -ac 1 -thread_queue_size 8192 -i \\.\pipe\mascot_pipe -c:v copy -c:a copy -f matroska tcp://localhost:55009/stream?listen" ^
    --run_command2 "client\MascotGirl_Client.exe -start_local"
cd ..
call __CONDA__ deactivate
endlocal
'''

    run_share_bat_content = r'''@echo off
setlocal
__SET_PATH__
call __CONDA__ activate mascotgirl
cd mascotgirl
python mascot.py ^
    --select_chara ^
    __IGNORE_EXTENSIONS__ ^
    --voicevox_url "" ^
    --chat_backend "__CHAT_BACKEND__" ^
    __CHAT_OPTION__ ^
    --ngrok_auth_token "__NGROK_AUTH_TOKEN__" ^
    --show_qrcode ^
    --chatgpt_log "chatgpt.json" ^
    --chatgpt_log_replace ^
    --image_pipe_name "\\.\pipe\mascot_image_pipe" ^
    --framerate 30 ^
    --run_command_reload ^
    --run_command "ffmpeg\ffmpeg -y -f rawvideo -pix_fmt rgba -s 512x512 -framerate 30 -thread_queue_size 8192 -i \\.\pipe\mascot_image_pipe -f s16le -ar __AUDIO_FREQ__ -ac 1 -thread_queue_size 8192 -i \\.\pipe\mascot_pipe -auto-alt-ref 0 -deadline realtime -quality realtime -cpu-used 4 -row-mt 1 -crf 30 -b:v 0 -pass 1 -c:v libvpx-vp9 -c:a libopus -f matroska tcp://0.0.0.0:55009/stream?listen"
cd ..
call __CONDA__ deactivate
endlocal
'''

    train_style_bert_vits2_bat_content = r'''@echo off
echo NOTE:
echo このバッチファイルは「litagin02/Style-Bert-VITS2」の学習用エディタを起動するだけのものです。
echo NON906作ではないのでご注意ください（本家様に迷惑をかけないようご注意ください）。
setlocal
__SET_PATH__
call __CONDA__ activate mascotgirl
cd mascotgirl/Style-Bert-VITS2
python app.py
cd ../..
call __CONDA__ deactivate
endlocal
'''

    uninstall_content = r'''@echo off
setlocal
__SET_PATH__
call __CONDA__ activate mascotgirl
python "mascotgirl/uninstall.py"
if %ERRORLEVEL% neq 1 (
    exit /b
)
call __CONDA__ deactivate
del /Q run.bat
del /Q run_share.bat > nul 2>&1
del /Q train_style_bert_vits2.bat
del /Q setting.bat
rd /S /Q mascotgirl
if NOT EXIST "%~dp0.installed\.environment" (
    powershell -Command "Start-Process -Wait bin\Miniconda3\Uninstall-Miniconda3.exe /S"
    rd /S /Q bin
    rd /S /Q .installed
    del /Q uninstall.bat && echo アンインストールが完了しました && pause && exit /b
)
rd /S /Q bin
rd /S /Q .installed
conda remove -n mascotgirl --all -y && del /Q uninstall.bat && echo アンインストールが完了しました && pause
endlocal
'''

    setting_content = r'''@echo off
setlocal
__SET_PATH__
call __CONDA__ activate mascotgirl
python "mascotgirl/setting.py"
call __CONDA__ deactivate
endlocal
'''

    def replace(target: str, content: str):
        global run_bat_content
        global run_share_bat_content
        global train_style_bert_vits2_bat_content
        global uninstall_content
        global setting_content
        if content is None:
            content = ''
        run_bat_content = run_bat_content.replace(target, content)
        run_share_bat_content = run_share_bat_content.replace(target, content)
        train_style_bert_vits2_bat_content = train_style_bert_vits2_bat_content.replace(target, content)
        uninstall_content = uninstall_content.replace(target, content)
        setting_content = setting_content.replace(target, content)

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
    
    if os.path.isfile('.installed/.miniconda'):
        set_path = r'set PATH=%~dp0bin\Miniconda3;%~dp0bin\Miniconda3\condabin;%~dp0bin\Miniconda3\Library\mingw-w64\bin;%~dp0bin\Miniconda3\Library\usr\bin;%~dp0bin\Miniconda3\Library\bin;%~dp0bin\Miniconda3\Scripts;%PATH%'
        replace('__SET_PATH__', set_path)
        conda = r'%~dp0bin\Miniconda3\condabin\conda'
        replace('__CONDA__', conda)
    else:
        set_path = r''
        replace('__SET_PATH__', set_path)
        conda = r'conda'
        replace('__CONDA__', conda)

    chat_backend_select = -1
    while chat_backend_select < 1 or chat_backend_select > 2:
        select = input('どのAPIを使用しますか？\n [1. OpenAI API (Assistant) / 2. Google Generative AI] (1): ')
        if select is None or select == '' or int(select) == 1:
            chat_backend_select = 1
        elif int(select) <= 2:
            chat_backend_select = int(select)

    if chat_backend_select == 1:
        replace('__CHAT_BACKEND__', 'OpenAIAssistant')

        replace('__CHAT_OPTION__', '''--chatgpt_apikey "__CHATGPT_APIKEY__" ^
    --chatgpt_model_name "__CHATGPT_MODEL_NAME__"''')

        select = ''
        while select is None or select == '':
            select = input('OpenAIのAPIキーを入力してください: \n')
        replace('__CHATGPT_APIKEY__', select)

        select = input('使用するOpenAIのモデル名を入力してください (gpt-3.5-turbo): \n')
        if select is None or select == '':
            select = 'gpt-3.5-turbo'
        replace('__CHATGPT_MODEL_NAME__', select)
    else:
        replace('__CHAT_BACKEND__', 'GoogleGenerativeAI')

        select_apikey = ''
        while select_apikey is None or select_apikey == '':
            select_apikey = input('Google Generative AIのAPIキーを入力してください: \n')
        
        select = input('使用するAIのモデル名を入力してください (gemini-pro): \n')
        if select is None or select == '':
            select = 'gemini-pro'

        replace('__CHAT_OPTION__', '--google_apikey "' + select_apikey + '" --google_model_name "' + select + '"')

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

    while True:
        select = input('拡張機能を有効にしますか？ [y/N]: ')
        if select is None or select == '' or select == 'N' or select == 'n':
            replace('__IGNORE_EXTENSIONS__', '--ignore_extensions')
            break
        elif select == 'Y' or select == 'y':
            replace('__IGNORE_EXTENSIONS__', '')
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
    if not '\r\n' in train_style_bert_vits2_bat_content:
        train_style_bert_vits2_bat_content.replace('\n', '\r\n')
    with open('train_style_bert_vits2.bat', 'w', encoding='shift_jis') as open_file:
        open_file.write(train_style_bert_vits2_bat_content)
    
    if not '\r\n' in uninstall_content:
        uninstall_content.replace('\n', '\r\n')
    with open('uninstall.bat', 'w', encoding='shift_jis') as open_file:
        open_file.write(uninstall_content)

    if not '\r\n' in setting_content:
        setting_content.replace('\n', '\r\n')
    with open('setting.bat', 'w', encoding='shift_jis') as open_file:
        open_file.write(setting_content)