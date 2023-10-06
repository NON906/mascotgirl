#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

if __name__ == "__main__":

    run_bat_content = r'''
@echo off
setlocal
set PATH=%~dp0Miniconda3;%~dp0Miniconda3\condabin;%~dp0Miniconda3\Library\mingw-w64\bin;%~dp0Miniconda3\Library\usr\bin;%~dp0Miniconda3\Library\bin;%~dp0Miniconda3\Scripts;%PATH%
call %~dp0Miniconda3\condabin\conda activate mascotgirl
cd mascotgirl
python mascot.py ^
    --voicevox_path "..\bin\voicevox\run.exe" ^
    --voice_changer_path "..\bin\MMVCServerSIO\start_http.bat" ^
    --image "__CHARA_IMAGE__" ^
    --background_image "__BACKGROUND_IMAGE__" ^
    --chatgpt_setting "__CHARA_SETTING__" ^
    --chatgpt_apikey "__CHATGPT_APIKEY__" ^
    --chatgpt_model_name "__CHATGPT_MODEL_NAME__" ^
    --voicevox_speaker_name "__VOICEVOX_SPEAKER_NAME__" ^
    --voicevox_intonation_scale __VOICEVOX_INTONATION_SCALE__ ^
    __RVC_PYTORCH_MODEL_FILE_OPT__ ^
    --rvc_index_file "__RVC_INDEX_FILE__" ^
    --rvc_model_trans __RVC_MODEL_TRANS__ ^
    --chatgpt_log "chatgpt.json" ^
    --chatgpt_log_replace ^
    --image_pipe_name "\\.\pipe\mascot_image_pipe" ^
    --run_command "client\MascotGirl_Client.exe -start_local"
cd ..
call %~dp0Miniconda3\condabin\conda deactivate
endlocal
    '''

    run_share_bat_content = r'''
@echo off
setlocal
set PATH=%~dp0Miniconda3;%~dp0Miniconda3\condabin;%~dp0Miniconda3\Library\mingw-w64\bin;%~dp0Miniconda3\Library\usr\bin;%~dp0Miniconda3\Library\bin;%~dp0Miniconda3\Scripts;%PATH%
call %~dp0Miniconda3\condabin\conda activate mascotgirl
cd mascotgirl
python mascot.py ^
    --voicevox_path "..\bin\voicevox\run.exe" ^
    --voice_changer_path "..\bin\MMVCServerSIO\start_http.bat" ^
    --image "__CHARA_IMAGE__" ^
    --background_image "__BACKGROUND_IMAGE__" ^
    --chatgpt_setting "__CHARA_SETTING__" ^
    --chatgpt_apikey "__CHATGPT_APIKEY__" ^
    --chatgpt_model_name "__CHATGPT_MODEL_NAME__" ^
    --voicevox_speaker_name "__VOICEVOX_SPEAKER_NAME__" ^
    --voicevox_intonation_scale __VOICEVOX_INTONATION_SCALE__ ^
    __RVC_PYTORCH_MODEL_FILE_OPT__ ^
    --rvc_index_file "__RVC_INDEX_FILE__" ^
    --rvc_model_trans __RVC_MODEL_TRANS__ ^
    --ngrok_auth_token "__NGROK_AUTH_TOKEN__" ^
    --show_qrcode ^
    --chatgpt_log "chatgpt.json" ^
    --chatgpt_log_replace ^
    --image_pipe_name "\\.\pipe\mascot_image_pipe" ^
    --framerate 30 ^
    --run_command_reload ^
    --run_command "ffmpeg\ffmpeg -y -f rawvideo -pix_fmt rgba -s 512x512 -framerate 30 -thread_queue_size 8192 -i \\.\pipe\mascot_image_pipe -f s16le -ar 48000 -ac 1 -thread_queue_size 8192 -i \\.\pipe\mascot_pipe -auto-alt-ref 0 -deadline realtime -quality realtime -cpu-used 4 -row-mt 1 -crf 30 -b:v 0 -pass 1 -c:v libvpx-vp9 -c:a libopus -f matroska tcp://0.0.0.0:55009/stream?listen"
cd ..
call %~dp0Miniconda3\condabin\conda deactivate
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

    select = input('キャラクターの画像ファイルのパスを入力してください (chara/chara_image.png): \n')
    if select is None or select == '':
        select = 'chara/chara_image.png'
    replace('__CHARA_IMAGE__', select)

    select = input('背景の画像ファイルのパスを入力してください (chara/background.png): \n')
    if select is None or select == '':
        select = 'chara/background.png'
    replace('__BACKGROUND_IMAGE__', select)
    
    select = input('キャラクター設定のテキストファイルのパスを入力してください (chara/chara_setting.txt): \n')
    if select is None or select == '':
        select = 'chara/chara_setting.txt'
    replace('__CHARA_SETTING__', select)

    select = ''
    while select is None or select == '':
        select = input('ChatGPTのAPIキーを入力してください（必須）: \n')
    replace('__CHATGPT_APIKEY__', select)

    select = input('使用するChatGPTのモデル名を入力してください (gpt-3.5-turbo): \n')
    if select is None or select == '':
        select = 'gpt-3.5-turbo'
    replace('__CHATGPT_MODEL_NAME__', select)

    select = input('VOICEVOXのキャラクター名を入力してください (春日部つむぎ): \n')
    if select is None or select == '':
        select = '春日部つむぎ'
    replace('__VOICEVOX_SPEAKER_NAME__', select)

    select = 'dummy'
    while not is_num(select):
        select = input('VOICEVOXの抑揚（0.0～2.0くらい）を入力してください (1.0): \n')
        if select is None or select == '':
            select = '1.0'
    replace('__VOICEVOX_INTONATION_SCALE__', select)

    select_pth = ''
    select_index = ''
    select_scale = '0'
    if os.path.isfile('.installed/.vc'):
        loop_flag = True
        while loop_flag:
            loop_flag = False
            select_pth = input('RVCのmodelファイル(*.pthまたは*.onnx)のパスを入力してください（空白でスキップ）: \n')
            if select_pth is not None and select_pth != '':
                _, ext = os.path.splitext(select_pth)
                if ext == '.pth':
                    select_pth = '--rvc_pytorch_model_file "' + select_pth + '"'
                elif ext == '.onnx':
                    select_pth = '--rvc_onnx_model_file "' + select_pth + '"'
                else:
                    loop_flag = True
                    continue
                select_index = input('RVCのindexファイル(*.index)のパスを入力してください（空白でスキップ）: \n')
                if select_index is not None and select_index != '':
                    select_scale = 'dummy'
                    while not is_int_num(select_scale):
                        select_scale = input('RVCの音高（-20～20くらい）を入力してください (0): \n')
                        if select_scale is None or select_scale == '':
                            select_scale = '0'
                else:
                    select_pth = ''
    replace('__RVC_PYTORCH_MODEL_FILE_OPT__', select_pth)
    replace('__RVC_INDEX_FILE__', select_index)
    replace('__RVC_MODEL_TRANS__', select_scale)

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