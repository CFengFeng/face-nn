#!/usr/bin/python
# -*- encoding: utf-8 -*-


from faceparsing.model import BiSeNet
import os
import cv2
from tqdm import tqdm
import torch
import torch.nn as nn
import os.path as osp
import numpy as np
from PIL import Image
import torchvision.transforms as transforms


def vis_parsing_maps(im, parsing_anno, stride, save_im, save_path):
    part_colors = [[255, 255, 255], [255, 85, 0], [255, 170, 0], [255, 0, 85], [255, 0, 170], [0, 255, 0], [85, 255, 0],
                   [170, 255, 0], [255, 255, 85], [0, 255, 170], [0, 0, 255], [85, 0, 255], [170, 0, 255], [0, 85, 255],
                   [255, 255, 255], [255, 255, 0], [255, 255, 255], [255, 255, 255], [255, 255, 255], [255, 85, 255],
                   [255, 170, 255], [0, 255, 255], [85, 255, 255], [170, 255, 255]]

    im = np.array(im)
    vis_im = im.copy().astype(np.uint8)
    vis_parsing_anno = parsing_anno.copy().astype(np.uint8)
    vis_parsing_anno = cv2.resize(vis_parsing_anno, None, fx=stride, fy=stride, interpolation=cv2.INTER_NEAREST)
    vis_parsing_anno_color = np.zeros((vis_parsing_anno.shape[0], vis_parsing_anno.shape[1], 3)) + 255

    num_of_class = np.max(vis_parsing_anno)
    for pi in range(1, num_of_class + 1):
        index = np.where(vis_parsing_anno == pi)
        vis_parsing_anno_color[index[0], index[1], :] = part_colors[pi]

    vis_parsing_anno_color = vis_parsing_anno_color.astype(np.uint8)
    vis_im = cv2.addWeighted(cv2.cvtColor(vis_im, cv2.COLOR_RGB2BGR), 0.2, vis_parsing_anno_color, 0.8, 0)
    if save_im:
        cv2.imwrite(save_path, img_edge(vis_parsing_anno_color))
    return vis_im


def img_edge(img):
    """
    提取原始图像的边缘
    :param img: input image
    :return: edge image
    """
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    x_grad = cv2.Sobel(gray, cv2.CV_16SC1, 1, 0)
    y_grad = cv2.Sobel(gray, cv2.CV_16SC1, 0, 1)
    return cv2.Canny(x_grad, y_grad, 30, 50)


def build_net(cp, cuda=False):
    n_classes = 19
    net = BiSeNet(n_classes=n_classes)

    if cuda:
        net.cuda()
        net.load_state_dict(torch.load(cp))
    else:
        net.load_state_dict(torch.load(cp, map_location="cpu"))
    net.eval()
    to_tensor = transforms.Compose(
        [transforms.ToTensor(), transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)), ])
    return net, to_tensor


_net_ = None
_to_tensor_ = None


def out_evaluate(image, cp, cuda=False):
    """
    global _net_, _to_tensor_ for performance
    """
    global _net_
    global _to_tensor_
    if _net_ is None or _to_tensor_ is None:
        _net_, _to_tensor_ = build_net(cp)
    with torch.no_grad():
        img = _to_tensor_(image)
        img = torch.unsqueeze(img, 0)
        if cuda:
            img = img.cuda()
            _net_.cuda()
        out = _net_(img)[0]
        parsing = out.squeeze(0).cpu().numpy().argmax(0)
        return vis_parsing_maps(image, parsing, stride=1, save_im=False, save_path="")


def inner_evaluate(dst_pth, src_path):
    if not os.path.exists(dst_pth):
        os.makedirs(dst_pth)
    net, to_tensor = build_net('../dat/79999_iter.pth')
    with torch.no_grad():
        list_image = os.listdir(src_path)
        total = len(list_image)
        progress = tqdm(range(0, total), initial=0, total=total)
        for step in progress:
            img = Image.open(osp.join(src_path, list_image[step]))
            image = img.resize((512, 512), Image.BILINEAR)
            img = to_tensor(image)
            img = torch.unsqueeze(img, 0)
            out = net(img)[0]
            parsing = out.squeeze(0).cpu().numpy().argmax(0)
            vis_parsing_maps(image, parsing,
                             stride=1, save_im=True,
                             save_path=osp.join(dst_pth, list_image[step]))

