#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import py7zr
import subprocess

def wget(url: str, save_path: str):
    if os.path.dirname(save_path) != "":
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
    subprocess.run(['wget', '-O', save_path, url])

def make_empty_file(path: str):
    with open(path, 'w') as o:
        o.write('')

if __name__ == "__main__":
    while not os.path.isfile('.installed/.tha3'):
        wget('https://www.dropbox.com/s/zp3e5ox57sdws3y/editor.pt?dl=0', 'mascotgirl/talking_head_anime_3_demo/data/models/standard_float/editor.pt')
        wget('https://www.dropbox.com/s/bcp42knbrk7egk8/eyebrow_decomposer.pt?dl=0', 'mascotgirl/talking_head_anime_3_demo/data/models/standard_float/eyebrow_decomposer.pt')
        wget('https://www.dropbox.com/s/oywaiio2s53lc57/eyebrow_morphing_combiner.pt?dl=0', 'mascotgirl/talking_head_anime_3_demo/data/models/standard_float/eyebrow_morphing_combiner.pt')
        wget('https://www.dropbox.com/s/8qvo0u5lw7hqvtq/face_morpher.pt?dl=0', 'mascotgirl/talking_head_anime_3_demo/data/models/standard_float/face_morpher.pt')
        wget('https://www.dropbox.com/s/qmq1dnxrmzsxb4h/two_algo_face_body_rotator.pt?dl=0', 'mascotgirl/talking_head_anime_3_demo/data/models/standard_float/two_algo_face_body_rotator.pt')
        make_empty_file('.installed/.tha3')

    while not os.path.isfile('.installed/.voicevox'):
        select = input('どのバージョンのVOICEVOXをインストールしますか？ [CPU/CUDA] (CUDA): ')
        is_selected = True
        if select is None or select == '' or select == 'CUDA':
            wget('https://github.com/VOICEVOX/voicevox_engine/releases/download/0.14.5/voicevox_engine-windows-nvidia-0.14.5.7z.001', 'voicevox_engine-windows.7z.001')
        elif select == 'CPU':
            wget('https://github.com/VOICEVOX/voicevox_engine/releases/download/0.14.5/voicevox_engine-windows-cpu-0.14.5.7z.001', 'voicevox_engine-windows.7z.001')
        #elif select == 'DirectML':
        #    wget('https://github.com/VOICEVOX/voicevox_engine/releases/download/0.14.5/voicevox_engine-windows-directml-0.14.5.7z.001', 'voicevox_engine-windows.7z.001')
        else:
            continue
        with py7zr.SevenZipFile('voicevox_engine-windows.7z.001', mode='r') as archive:
            archive.extractall(path='bin/voicevox_tmp')
        for f in os.listdir('bin/voicevox_tmp'):
            sub_dir = os.path.join('bin/voicevox_tmp', f)  
            if os.path.isdir(sub_dir):
                break
        shutil.move(sub_dir, 'bin/voicevox')
        make_empty_file('.installed/.voicevox')
        os.remove('voicevox_engine-windows.7z.001')

    while not os.path.isfile('.installed/.vc'):
        select = input('VC Clientをインストールしますか？ [y/N]: ')
        is_selected = True
        if select is None or select == '' or select == 'N' or select == 'n':
            break
        elif select == 'Y' or select == 'y':
            wget('https://huggingface.co/wok000/vcclient000/resolve/main/MMVCServerSIO_win_onnxgpu-cuda_v.1.5.3.14.zip', 'MMVCServerSIO_win_onnxgpu-cuda.zip')
            shutil.unpack_archive('MMVCServerSIO_win_onnxgpu-cuda.zip', 'bin')
            os.remove('MMVCServerSIO_win_onnxgpu-cuda.zip')
        else:
            continue
        make_empty_file('.installed/.vc')
