#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: penghuailiang
# @Date  : 2019-10-04

import torch
import os
import cv2
import random
import struct
import utils
import numpy as np
import util.logit as log
from util.exception import NeuralException


class FaceDataset:
    """
    由Unity引擎生成的dataset
    """

    def __init__(self, args, mode="train"):
        """
        Dataset construction
        :param args: argparse options
        :param mode: "train": 训练集, "test": 测试集
        """
        self.names = []
        self.params = []
        if mode == "train":
            self.path = args.path_to_dataset
        elif mode == "test":
            self.path = args.path_to_testset
        else:
            raise NeuralException("not such mode for dataset")
        self.args = args
        if os.path.exists(self.path):
            name = "db_description"
            path = os.path.join(self.path, name)
            log.info(path)
            f = open(path, "rb")
            self.cnt = struct.unpack("i", f.read(4))[0]
            for it in range(self.cnt):
                kk = f.read(10)[1:]  # 第一个是c#字符串的长度
                self.names.append(str(kk, encoding='utf-8'))
                v = []
                for i in range(args.params_cnt):
                    v.append(struct.unpack("f", f.read(4))[0])
                self.params.append(v)
            f.close()
        else:
            log.info("can't be found path %s. Skip it.", self.path)

    def get_batch(self, batch_size, size=512):
        """
        以<name, params, image>的形式返回
        formatter: [batch, ?]
        :param batch_size:  batch size
        :param size: 图片分辨率
        """
        names = []
        cnt = self.cnt
        param_cnt = self.args.params_cnt
        np_params = np.zeros((batch_size, param_cnt), dtype=np.float32)
        np_images = np.zeros((batch_size, 1, size, size), dtype=np.float32)
        for i in range(batch_size):
            ind = random.randint(0, cnt - 1)
            name = self.names[ind]
            np_params[i] = self.params[ind]
            name = name + ".jpg"
            names.append(name)
            path = os.path.join(self.path, name)
            image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if size != image.shape[0]:
                image = cv2.resize(image, (size, size), interpolation=cv2.INTER_LINEAR)
            np_images[i] = image[np.newaxis, :, :] / 255.0
        params = torch.from_numpy(np_params)
        params.requires_grad = True
        images = torch.from_numpy(np_images)
        log.debug("batch leaf:{0}  grad:{1} type:{2}".format(params.is_leaf, params.requires_grad, params.dtype))
        log.debug("numpy params type:{0}".format(np_params.dtype))
        return names, params, images

    def get_cache(self, cuda):
        """
        extractor 运行的时候 从cache获取batch
        cache 在训练的时候由引擎生成
        返回 64X64
        """
        cache = self.args.path_to_cache

        if os.path.exists(cache):
            try:
                for root, dirs, files in os.walk(cache, topdown=False):
                    for name in files:
                        path = os.path.join(root, name)
                        idx = name.rindex('_')
                        name2 = name[7:idx] + ".jpg"  # 7 is: neural_
                        path2 = os.path.join(self.path, name2)
                        image_1 = self.process_item(path, False, cuda=cuda)
                        image_2 = cv2.imread(path2, cv2.IMREAD_GRAYSCALE)
                        os.remove(path)
                        image_1 = torch.from_numpy(image_1 / 255.0)
                        image_2 = torch.from_numpy(image_2 / 255.0)
                        image_2.requires_grad_(True)
                        return image_2, image_1
            except Exception as e:
                log.warn(e)
        return None, None

    def pre_process(self, cuda):
        for name in self.names:
            path = os.path.join(self.path, name + ".jpg")
            self.process_item(path, save=True, cuda=cuda)

    def process_item(self, path, save, cuda):
        """
        预处理 change database to 64x64 edge pictures
        :param path: 图片路径
        :param save: 是否将处理好的图片保存本地
        :param cuda: gpu speedup
        """
        # log.info(path)
        img = utils.evalute_face(path, self.args.extractor_checkpoint, cuda)
        img = utils.img_edge(img)
        if img.shape[0] != 64:
            img = cv2.resize(img, (64, 64), interpolation=cv2.INTER_AREA)
        if save:
            cv2.imwrite(path, img)
        return img
