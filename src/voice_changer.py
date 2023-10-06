#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import os
import base64
import json
import sys

def check_voice_changer(url, verify):
    try:
        res = requests.get(url + '/api/hello', verify=verify)
        return res.status_code == 200
    except:
        return False

class VoiceChangerRVC:
    timestamp = 0

    def __init__(self, url, verify):
        self.url = url
        self.verify = verify

    def load(self, pytorch_model_file, onnx_model_file, index_file, is_half, trans):
        def upload_file(file_path):
            with open(file_path, mode='rb') as f:
                form_data = {'filename': os.path.basename(file_path)}
                res = requests.post(self.url + '/upload_file', files={'file': f}, data=form_data, verify=self.verify)
            return res.status_code == 200

        if onnx_model_file is not None:
            is_success = upload_file(onnx_model_file)
            if not is_success:
                return False
        elif pytorch_model_file is not None:
            is_success = upload_file(pytorch_model_file)
            if not is_success:
                return False
        else:
            return False
        
        is_success = upload_file(index_file)
        if not is_success:
            return False

        form_data = {
            'slot': 100,
            'isHalf': is_half,
        }
        params_data = {
            'voiceChangerType': 'RVC',
            'slot': 100,
            'isSampleMode': False,
            'sampleId': 'mascotgirl',
            'params': {
                "slotIndex": 100,
                "voiceChangerType": "RVC",
                "speakers": {
                    "0": "target"
                },
                "indexFile": os.path.basename(index_file),
                "defaultTune": trans,
                "samplingRate": 40000,
                "f0": True,
                "embedder": "hubert_base",
                "sampleId": 'mascotgirl', 
            },
            'files': [
                {
                    'name': os.path.basename(index_file),
                    'kind': 'rvcIndex',
                    'dir': '',
                }
            ],
        }
        if onnx_model_file is not None:
            params_data['params']['modelFile'] = os.path.basename(onnx_model_file)
            params_data['params']['isONNX'] = True
            params_data['params']['modelType'] = 'onnxRVC'
            params_data['files'] += [{
                'name': os.path.basename(onnx_model_file),
                'kind': 'rvcModel',
                'dir': '',
            }]
        else:
            params_data['params']['modelFile'] = os.path.basename(pytorch_model_file)
            params_data['params']['isONNX'] = False
            params_data['params']['modelType'] = 'pyTorchRVC'
            params_data['files'] += [{
                'name': os.path.basename(pytorch_model_file),
                'kind': 'rvcModel',
                'dir': '',
            }]
        form_data['params'] = json.dumps(params_data)
        res = requests.post(self.url + '/load_model', data=form_data, verify=self.verify)
        #print("\n" + str(res.content), file=sys.stderr)
        if res.status_code != 200:
            return False

        res = requests.post(self.url + '/update_settings', data={'key': 'modelSlotIndex', 'val': 100}, verify=self.verify)
        if res.status_code != 200:
            return False

        return True
    
    def test(self, buffer):
        json_data = {
            'timestamp': self.timestamp,
            'buffer': base64.b64encode(buffer).decode("utf-8")
        }
        res = requests.post(self.url + '/test', data=json.dumps(json_data), verify=self.verify)
        if res.status_code != 200:
            #print(res.content, file=sys.stderr)
            return None
        self.timestamp += 1
        base64_str = json.loads(res.content)['changedVoiceBase64']
        return base64.b64decode(base64_str)