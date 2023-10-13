#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess

def install():
    def wget(url: str, save_path: str):
        if os.path.dirname(save_path) != "":
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
        subprocess.run(['wget', '-O', save_path, url])
        
    if os.name == 'nt':
        if not os.path.isfile(os.path.join(os.path.dirname(__file__), 'bin/meilisearch-windows-amd64.exe')):
            print('Download files...')
            os.makedirs(os.path.join(os.path.dirname(__file__), 'bin'), exist_ok=True)
            wget('https://github.com/meilisearch/meilisearch/releases/download/v1.4.1/meilisearch-windows-amd64.exe', os.path.join(os.path.dirname(__file__), 'bin/meilisearch-windows-amd64.exe'))
            wget('https://raw.githubusercontent.com/meilisearch/meilisearch/main/LICENSE', os.path.join(os.path.dirname(__file__), 'bin/LICENSE'))
    else:
        if not os.path.isfile(os.path.join(os.path.dirname(__file__), 'bin/meilisearch')):
            print('Download files...')
            os.makedirs(os.path.join(os.path.dirname(__file__), 'bin'), exist_ok=True)
            default_cd = os.getcwd()
            os.chdir(os.path.join(os.path.dirname(__file__), 'bin'))
            subprocess.run('curl -L https://install.meilisearch.com | sh', shell=True)
            os.chdir(default_cd)
    subprocess.run(['pip', 'install', 'meilisearch', 'tiktoken'])
