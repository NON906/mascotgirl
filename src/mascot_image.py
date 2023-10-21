#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.getcwd() + "/talking_head_anime_3_demo")

import PIL.Image
import io
from io import StringIO, BytesIO
import numpy
import time
import torch
from tha3.poser.modes.load_poser import load_poser
from tha3.util import resize_PIL_image, extract_PIL_image_from_filelike, \
    extract_pytorch_image_from_PIL_image, convert_output_image_from_torch_to_numpy
from tha3.poser.modes.pose_parameters import get_pose_parameters
import cv2
import sys
import json
from pydantic import BaseModel
from contextlib import redirect_stdout

import image_setting

class MascotImage:
    last_torch_input_image = None
    torch_input_image = None

    numpy_image = None

    eyebrow_options = ["troubled", "angry", "lowered", "raised", "happy", "serious"]
    eyebrow_index = 0
    eyebrow_left = 0.0
    eyebrow_right = 0.0

    eye_options = ["wink", "happy_wink", "surprised", "relaxed", "unimpressed", "raised_lower_eyelid"]
    eye_index = 0
    eye_left = 0.0
    eye_right = 0.0

    mouth_options = ["aaa", "iii", "uuu", "eee", "ooo", "delta", "lowered_corner", "raised_corner", "smirk"]
    mouth_index = 0
    mouth_left = 0.0
    mouth_right = 0.0

    pose_values = [0.0 for _ in range(10)]

    is_uploading = False

    def __init__(self, mode='standard_float'):
        self.device = torch.device('cuda')
        try:
            os.chdir("./talking_head_anime_3_demo")
            with redirect_stdout(open(os.devnull, 'w')):
                self.poser = load_poser(mode, self.device)
            os.chdir("..")
        except RuntimeError as e:
            print(e)
            sys.exit()

        self.pose_parameters = get_pose_parameters()
        self.pose_size = self.poser.get_num_parameters()
        self.last_pose = torch.zeros(1, self.pose_size, dtype=self.poser.get_dtype()).to(self.device)

        self.iris_small_left_index = self.pose_parameters.get_parameter_index("iris_small_left")
        self.iris_small_right_index = self.pose_parameters.get_parameter_index("iris_small_right")
        self.iris_rotation_x_index = self.pose_parameters.get_parameter_index("iris_rotation_x")
        self.iris_rotation_y_index = self.pose_parameters.get_parameter_index("iris_rotation_y")
        self.head_x_index = self.pose_parameters.get_parameter_index("head_x")
        self.head_y_index = self.pose_parameters.get_parameter_index("head_y")
        self.neck_z_index = self.pose_parameters.get_parameter_index("neck_z")
        self.body_y_index = self.pose_parameters.get_parameter_index("body_y")
        self.body_z_index = self.pose_parameters.get_parameter_index("body_z")
        self.breathing_index = self.pose_parameters.get_parameter_index("breathing")

    def refresh_image(self, pytorch_image):
        output_image = pytorch_image.detach().cpu()
        self.numpy_image = numpy.uint8(numpy.rint(convert_output_image_from_torch_to_numpy(output_image) * 255.0))

    def get_pose(self):
        pose = torch.zeros(1, self.pose_size, dtype=self.poser.get_dtype())

        eyebrow_name = f"eyebrow_{self.eyebrow_options[self.eyebrow_index]}"
        eyebrow_left_index = self.pose_parameters.get_parameter_index(f"{eyebrow_name}_left")
        eyebrow_right_index = self.pose_parameters.get_parameter_index(f"{eyebrow_name}_right")
        pose[0, eyebrow_left_index] = self.eyebrow_left
        pose[0, eyebrow_right_index] = self.eyebrow_right

        eye_name = f"eye_{self.eye_options[self.eye_index]}"
        eye_left_index = self.pose_parameters.get_parameter_index(f"{eye_name}_left")
        eye_right_index = self.pose_parameters.get_parameter_index(f"{eye_name}_right")
        pose[0, eye_left_index] = self.eye_left
        pose[0, eye_right_index] = self.eye_right

        mouth_name = f"mouth_{self.mouth_options[self.mouth_index]}"
        if mouth_name == "mouth_lowered_corner" or mouth_name == "mouth_raised_corner":
            mouth_left_index = self.pose_parameters.get_parameter_index(f"{mouth_name}_left")
            mouth_right_index = self.pose_parameters.get_parameter_index(f"{mouth_name}_right")
            pose[0, mouth_left_index] = self.mouth_left
            pose[0, mouth_right_index] = self.mouth_right
        else:
            mouth_index_local = self.pose_parameters.get_parameter_index(mouth_name)
            pose[0, mouth_index_local] = self.mouth_left

        pose[0, self.iris_small_left_index] = self.pose_values[0]
        pose[0, self.iris_small_right_index] = self.pose_values[1]
        pose[0, self.iris_rotation_x_index] = self.pose_values[2]
        pose[0, self.iris_rotation_y_index] = self.pose_values[3]
        pose[0, self.head_x_index] = self.pose_values[4]
        pose[0, self.head_y_index] = self.pose_values[5]
        pose[0, self.neck_z_index] = self.pose_values[6]
        pose[0, self.body_y_index] = self.pose_values[7]
        pose[0, self.body_z_index] = self.pose_values[8]
        pose[0, self.breathing_index] = self.pose_values[9]

        return pose.to(self.device)

    def update(self):
        if self.is_uploading:
            return

        if self.torch_input_image is None:
            return

        needs_update = False
        if self.last_torch_input_image is None:
            needs_update = True        
        else:
            if (self.torch_input_image - self.last_torch_input_image).abs().max().item() > 0:
                needs_update = True         

        pose = self.get_pose()
        if (pose - self.last_pose).abs().max().item() > 0:
            needs_update = True

        if not needs_update:
            return

        os.chdir("./talking_head_anime_3_demo")
        with redirect_stdout(open(os.devnull, 'w')):
            output_image = self.poser.pose(self.torch_input_image, pose)[0]
        os.chdir("..")
        self.refresh_image(output_image)

        self.last_torch_input_image = self.torch_input_image
        self.last_pose = pose

    def upload_image(self, numpy_content, skip_setting, rembg_model_name='isnet-anime'):
        self.is_uploading = True
        if not skip_setting:
            numpy_content = image_setting.image_setting(numpy_content, model_name=rembg_model_name)
            if numpy_content is None:
                self.is_uploading = False
                return False
        pil_image = resize_PIL_image(PIL.Image.fromarray(numpy_content), size=(512,512))
        w, h = pil_image.size
        if pil_image.mode != 'RGBA':
            self.torch_input_image = None
            self.is_uploading = False
            return False
        else:
            self.torch_input_image = extract_pytorch_image_from_PIL_image(pil_image).to(self.device)
            if self.poser.get_dtype() == torch.half:
                self.torch_input_image = self.torch_input_image.half()
        self.is_uploading = False
        return True

    def get_numpy_image(self):
        ret = self.numpy_image
        if ret is None or ret.shape != (512, 512, 4):
            return None
        return ret

    def set_eyebrow(self, target, left, right):
        is_matched = False
        if type(target) is int:
            self.eyebrow_index = target
            is_matched = True
        elif type(target) is str:
            for loop, loop_name in enumerate(self.eyebrow_options):
                if loop_name == target:
                    self.eyebrow_index = loop
                    is_matched = True
        if is_matched:
            self.eyebrow_left = left
            self.eyebrow_right = right

    def set_eye(self, target, left, right):
        if type(target) is int:
            self.eye_index = target
        elif type(target) is str:
            for loop, loop_name in enumerate(self.eye_options):
                if loop_name == target:
                    self.eye_index = loop
        self.eye_left = left
        self.eye_right = right

    def set_mouth(self, target, left, right=0.0):
        if type(target) is int:
            self.mouth_index = target
        elif type(target) is str:
            for loop, loop_name in enumerate(self.mouth_options):
                if loop_name == target:
                    self.mouth_index = loop
        self.mouth_left = left
        self.mouth_right = right

    def set_body_morph(self, iris_rotation_x, iris_rotation_y, head_x, head_y, body_y):
        self.pose_values[2] = iris_rotation_x
        self.pose_values[3] = iris_rotation_y
        self.pose_values[4] = head_x
        self.pose_values[5] = head_y
        self.pose_values[7] = body_y

    def set_other_pose(self, id, value):
        self.pose_values[id] = value
