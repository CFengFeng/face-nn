#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: penghuailiang
# @Date  : 2019/10/16

import align
import utils
import ops
import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import util.logit as log
import numpy as np
from tqdm import tqdm
from dataset import FaceDataset
from net import Net
from module import ResidualBlock, group
from tensorboardX import SummaryWriter

"""
feature extractor
photo生成engine face's params
input: photo solution: 64x64
output: engine params [95]
"""


class Extractor(nn.Module):
    TRAIN_ASYN = 1
    TRAIN_SYNC = 2

    def __init__(self, name, args, imitator=None, momentum=0.5):
        """
        feature extractor
        :param name: model name
        :param args: argparse options
        :param imitator: imitate engine's behaviour
        :param momentum:  momentum for optimizer
        """
        super(Extractor, self).__init__()
        log.info("construct feature_extractor %s", name)
        self.name = name
        self.imitator = imitator
        self.initial_step = 0
        self.args = args
        self.model_path = "./output/extractor"
        self.prev_path = "./output/preview"
        self.training = False
        self.params_cnt = self.args.params_cnt
        self.dataset = None
        self.train_mode = Extractor.TRAIN_SYNC
        self.train_refer = 32
        self.net = Net(args.udp_port, args)
        self.clean()
        self.writer = SummaryWriter(comment="feature extractor", log_dir=args.path_tensor_log)
        self.model = nn.Sequential(
            nn.Conv2d(1, 4, kernel_size=7, stride=2, padding=3),  # 1. (batch, 4, 32, 32)
            nn.MaxPool2d(kernel_size=3, stride=2, padding=1),  # 2. (batch, 4, 16, 16)
            group(4, 8, kernel_size=3, stride=1, padding=1),  # 3. (batch, 8, 16, 16)
            ResidualBlock.make_layer(8, channels=8),  # 4. (batch, 8, 16, 16)
            group(8, 16, kernel_size=3, stride=1, padding=1),  # 5. (batch, 16, 16, 16)
            ResidualBlock.make_layer(8, channels=16),  # 6. (batch, 16, 16, 16)
            group(16, 64, kernel_size=3, stride=1, padding=1),  # 7. (batch, 64, 16, 16)
            ResidualBlock.make_layer(8, channels=64),  # 8. (batch, 64, 16, 16)
            group(64, self.params_cnt, kernel_size=3, stride=1, padding=1),  # 9. (batch, params_cnt, 16, 16)
            ResidualBlock.make_layer(4, channels=self.params_cnt),  # 10. (batch, params_cnt, 16, 16)
        )
        self.fc = nn.Linear(95 * 16 * 16, 95)
        self.optimizer = optim.Adam(self.parameters(), lr=args.extractor_learning_rate)

    def forward(self, input):
        output = self.model(input)
        output = output.view(output.size(0), -1)
        output = self.fc(output)
        output = F.dropout(output, training=self.training)
        output = torch.sigmoid(output)
        return output

    def itr_train(self, image):
        """
        第一种方法 这里train的方式使用的是imitator （同步）
        :param image: [batch, 3, 512, 512]
        :return: loss scalar
        """
        self.optimizer.zero_grad()
        param_ = self.forward(image)
        img_ = self.imitator.forward(param_)
        loss = utils.content_loss(image, img_)
        loss.backward()
        self.optimizer.step()
        return loss, param_

    def sync_train(self, image, name, step):
        """
        第二种方法是 通过net把params发生引擎生成image (异步)
        (这种方法需要保证同步，但效果肯定比imitator效果好)
        :param step: train step
        :param name: 图片名 [batch]
        :param image: [batch, 1, 64, 64]
        """
        self.train_refer = self.train_refer - 1
        if self.train_refer <= 0:
            self.change_mode(Extractor.TRAIN_ASYN)
        param_ = self.forward(image)
        self.net.send_params(param_, name, step)

    def asyn_train(self, cuda, step):
        """
        cache 中累计一定量的时候就可以asyn train
        :param cuda: gpu speed up
        :param step: step 0: not export to preview
        :return: loss, type scalar
        """
        self.train_refer = self.train_refer - 1

        image1, image2 = self.dataset.get_cache(cuda)
        if self.train_refer <= 0 or image1 is None:
            self.change_mode(Extractor.TRAIN_SYNC)
            return False, 0

        if step > 0:
            path = "{1}/ext_{0}.jpg".format(step, self.prev_path)
            ops.save_grey(path, image1, image2)
        self.optimizer.zero_grad()
        loss = F.mse_loss(image1, image2)
        loss.backward()
        self.optimizer.step()
        return True, loss

    def change_mode(self, mode):
        """
        切换train mode 并恢复计数
        :param mode: train mode
        """
        self.train_refer = 32
        if mode == Extractor.TRAIN_ASYN:
            self.train_refer = 33
        self.train_mode = mode

    def batch_train(self, cuda):
        log.info("feature extractor train")
        initial_step = self.initial_step
        total_steps = self.args.total_extractor_steps
        self.training = True
        self.dataset = FaceDataset(self.args, mode="train")

        rnd_input = torch.randn(self.args.batch_size, 1, 64, 64)
        if cuda:
            rnd_input = rnd_input.cuda()
        self.writer.add_graph(self, input_to_model=rnd_input)

        progress = tqdm(range(initial_step, total_steps + 1), initial=initial_step, total=total_steps)
        for step in progress:
            if self.train_mode == Extractor.TRAIN_SYNC:
                progress.set_description("sync mode")
                names, _, images = self.dataset.get_batch(batch_size=self.args.batch_size, size=64)
                if cuda:
                    images = images.cuda()
                self.sync_train(images, names, step)
            else:
                x_step = step if (step % self.args.extractor_prev_freq == 0) else 0
                valid, loss = self.asyn_train(cuda, step=x_step)
                if valid:
                    loss_ = loss.detach().numpy()
                    loss_display = loss_ * 100
                    progress.set_description("loss: {:.3f}".format(loss_display))
                    self.writer.add_scalar('extractor/loss', loss_display, step)
                    utils.update_optimizer_lr(self.optimizer, loss_)
                    if step % self.args.extractor_save_freq == 0:
                        lr = self.args.extractor_learning_rate * loss_display
                        utils.update_optimizer_lr(self.optimizer, lr)
                        self.writer.add_scalar('extractor/learning rate', lr, step)
                        self.save(step)
        self.writer.close()

    def load_checkpoint(self, path):
        """
        从checkpoint 中恢复net
        :param path: checkpoint's path
        """
        checkpoint = torch.load(path)
        self.model.load_state_dict(checkpoint['net'])
        self.optimizer.load_state_dict(checkpoint['optimizer'])
        self.initial_step = checkpoint['epoch']
        log.info("recovery imitator from %s", path)

    def clean(self):
        """
        清空前记得备份
        :return:
        """
        ops.clear_folder(self.model_path)
        ops.clear_files(self.args.path_to_cache)
        ops.clear_files(self.args.path_tensor_log)
        ops.clear_files(self.prev_path)

    def save(self, step):
        """
        save checkpoint
        :param step: train step
        """
        state = {'net': self.state_dict(), 'optimizer': self.optimizer.state_dict(), 'epoch': step}
        if not os.path.exists(self.model_path):
            os.mkdir(self.model_path)
        torch.save(state, '{1}/model_extractor_{0}.pth'.format(step, self.model_path))

    def inference(self, path, photo):
        """
        feature extractor: 由图片生成捏脸参数
        :param path: checkpoint's path
        :param photo: input photo
        :return: params [batch, 95]
        """
        align.align_face()
        self.load_checkpoint(path)
        _, params_ = self.forward(path)
        return params_

    def evaluate(self):
        """
        评估准确率
        :return: accuracy rate
        """
        self.model.eval()
        dataset = FaceDataset(self.args, mode="test")
        steps = 100
        accuracy = 0.0
        for step in range(steps):
            log.info("step: %d", step)
            names, params, images = dataset.get_batch(batch_size=self.args.batch_size)
            loss, _ = self.itr_train(images)
            accuracy += 1.0 - loss
        accuracy = accuracy / steps
        log.info("accuracy rate is %f", accuracy)
        return accuracy
