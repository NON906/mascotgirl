#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
from pathlib import Path

if __name__ == "__main__":
    chara_json = {}
    chara_name = ''
    
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

    chara_name = input('保存先のキャラクター名を入力してください: \n')
    target_path = os.path.join(os.path.dirname(__file__), 'charas', chara_name)

    select = input('キャラクターの画像ファイルのパスを入力してください: \n')
    chara_json['image'] = str(Path(select).resolve().relative_to(Path(target_path).resolve()))

    select = input('背景の画像ファイルのパスを入力してください: \n')
    chara_json['background_image'] = str(Path(select).resolve().relative_to(Path(target_path).resolve()))

    select = input('キャラクター設定のテキストファイルのパスを入力してください: \n')
    chara_json['chatgpt_setting'] = str(Path(select).resolve().relative_to(Path(target_path).resolve()))

    select = input('VOICEVOXのキャラクター名を入力してください: \n')
    chara_json['voicevox_speaker_name'] = select

    select = 'dummy'
    while not is_num(select):
        select = input('VOICEVOXの抑揚（0.0～2.0くらい）を入力してください (1.0): \n')
        if select is None or select == '':
            select = '1.0'
    chara_json['voicevox_intonation_scale'] = float(select)

    select_pth = ''
    select_index = ''
    select_scale = 0
    if os.path.isfile('.installed/.vc'):
        loop_flag = True
        while loop_flag:
            loop_flag = False
            select_pth = input('RVCのmodelファイル(*.pthまたは*.onnx)のパスを入力してください（空白でスキップ）: \n')
            if select_pth is not None and select_pth != '':
                _, ext = os.path.splitext(select_pth)
                if ext == '.pth':
                    chara_json['rvc_pytorch_model_file'] = str(Path(select_pth).resolve().relative_to(Path(target_path).resolve()))
                elif ext == '.onnx':
                    chara_json['rvc_onnx_model_file'] = str(Path(select_pth).resolve().relative_to(Path(target_path).resolve()))
                else:
                    loop_flag = True
                    continue
                select_index = input('RVCのindexファイル(*.index)のパスを入力してください: \n')
                if select_index is not None and select_index != '':
                    select_index = str(Path(select_index).resolve().relative_to(Path(target_path).resolve()))
                    select_scale = 'dummy'
                    while not is_int_num(select_scale):
                        select_scale = input('RVCの音高（-20～20くらい）を入力してください (0): \n')
                        if select_scale is None or select_scale == '':
                            select_scale = '0'
    chara_json['rvc_index_file'] = select_index
    chara_json['rvc_model_trans'] = select_scale

    os.makedirs(target_path, exist_ok=True)
    with open(os.path.join(target_path, 'setting.json'), 'w', encoding='utf-8') as f:
        json.dump(chara_json, f, indent=2, ensure_ascii=False)