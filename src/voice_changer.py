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

    def load(self, pytorch_model_file, onnx_model_file, feature_file, index_file, is_half, trans):
        res = requests.post(self.url + '/model_type', data={'modelType': 'RVC'}, verify=self.verify)
        if res.status_code != 200:
            return False

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
        
        is_success = upload_file(feature_file)
        if not is_success:
            return False
        is_success = upload_file(index_file)
        if not is_success:
            return False

        form_data = {
            'slot': 0,
            'pyTorchModelFilename': '-',
            'onnxModelFilename': '-',
            'configFilename': '-',
            'clusterTorchModelFilename': '-',
            'featureFilename': os.path.basename(feature_file),
            'indexFilename': os.path.basename(index_file),
            'isHalf': is_half
        }
        params_dict = {
            'rvcFeature': os.path.basename(feature_file),
            'rvcIndex': os.path.basename(index_file)
        }
        if onnx_model_file is not None:
            form_data['onnxModelFilename'] = os.path.basename(onnx_model_file)
            params_dict['rvcModel'] = os.path.basename(onnx_model_file)
        else:
            form_data['pyTorchModelFilename'] = os.path.basename(pytorch_model_file)
            params_dict['rvcModel'] = os.path.basename(pytorch_model_file)
        form_data['params'] = json.dumps({ "trans": trans, "files": params_dict })
        res = requests.post(self.url + '/load_model', data=form_data, verify=self.verify)
        #print("\n" + str(res.content), file=sys.stderr)
        if res.status_code != 200:
            return False

        res = requests.post(self.url + '/update_settings', data={'key': 'modelSlotIndex', 'val': 0}, verify=self.verify)
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