#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import sys
import subprocess
import re

if __name__ == "__main__":
    select = input('本当にアンインストールしますか？ [y/N]: ')
    if select is None or select == '' or select == 'N' or select == 'n':
        sys.exit(2)

    select = input('一部データのバックアップを保存しますか？ [Y/n]: ')
    if select is None or select == '' or select == 'Y' or select == 'y':
        os.makedirs('backup/Style-Bert-VITS2/model_assets')

        shutil.move('mascotgirl/charas', 'backup/charas')
        shutil.move('mascotgirl/Style-Bert-VITS2/Data', 'backup/Style-Bert-VITS2/Data')

        repatter = re.compile(r'jvnv-.*-jp')
        dir_path = 'mascotgirl/Style-Bert-VITS2/model_assets'
        model_assets_dirs = [
            f for f in os.listdir(dir_path) if os.path.isdir(os.path.join(dir_path, f)) and repatter.match(f) is None
        ]
        for model_dir in model_assets_dirs:
            shutil.move(os.path.join(dir_path, model_dir), os.path.join('backup/Style-Bert-VITS2/model_assets', model_dir))

    sys.exit(1)
        
    