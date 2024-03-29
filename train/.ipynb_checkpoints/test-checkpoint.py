#!/usr/bin/python3
# coding=utf-8

import os
import sys
import argparse
sys.path.insert(0, '../')
sys.dont_write_bytecode = True

import cv2
import numpy as np
import matplotlib.pyplot as plt
plt.ion()

import torch
import dataset
from tqdm import tqdm
from torch.utils.data import DataLoader
from net import DEFER, Res_CBAM_Block
from torchvision      import transforms, models
from PIL import Image

from pytorch_grad_cam import GradCAM, HiResCAM, GradCAMElementWise, GradCAMPlusPlus, XGradCAM, AblationCAM, ScoreCAM, EigenCAM, EigenGradCAM, LayerCAM, FullGrad
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
import matplotlib.pyplot as plt
import torchcam
from torchcam.utils import overlay_mask
from scipy.ndimage import grey_dilation

def miou(pred, mask):
    mini  = 1
    maxi  = 1
    nbins = 1
    predict = (pred > 0).float()
    intersection = predict * ((predict == mask).float())

    area_inter, _ = np.histogram(intersection.cpu(), bins=nbins, range=(mini, maxi))
    area_pred, _  = np.histogram(predict.cpu(), bins=nbins, range=(mini, maxi))
    area_lab, _   = np.histogram(mask.cpu(), bins=nbins, range=(mini, maxi))
    area_union = area_pred + area_lab - area_inter
    iou = 1 * area_inter / (np.spacing(1) + area_union)

    return iou.mean()

class Test(object):
    def __init__(self, Dataset, Network, args):
        # dataset
        self.args = args
        datapath  = '/home/DEFER-master/data/' + args.dataset
        outpath   = './out/' + args.dataset + '/model-best'

        # test dataloader
        self.cfg    = Dataset.Config(datapath=datapath, snapshot=outpath, mode='test')
        self.data   = Dataset.Data(self.cfg)
        self.loader = DataLoader(self.data, batch_size=1, shuffle=False, num_workers=0)

        # network
        self.device = torch.device('cuda:0' if torch.cuda.is_available() else "cpu")
        print("Using {} device testing.".format(self.device))
        self.net    = Network(self.cfg, block=Res_CBAM_Block,  nb_filter=[16, 32, 64, 128, 256], block_nums=[2, 2, 2, 2])
        self.net.to(self.device)

    def save(self):
        test_iou = 0.0
        test_iou_num = 0
        test_tbar = tqdm(self.loader)
        self.net.eval()
        test_transform = transforms.Compose([transforms.Resize(256),
                                     # transforms.CenterCrop(512),
                                     transforms.ToTensor(),
                                     transforms.Normalize(
                                         mean=[0.485, 0.456, 0.406], 
                                         std=[0.229, 0.224, 0.225])
                                    ])
        with torch.no_grad():
            for step, (image, mask, (H, W), name) in enumerate(test_tbar):
                image, mask, shape = image.to(self.device).float(), mask.to(self.device), (H, W)
                out = self.net(image, shape)
                pred = torch.sigmoid(out[0, 0]).cpu().numpy() * 255
                pred = np.round(pred)

                out = torch.round(torch.sigmoid(out) * 255)
                mask = mask.unsqueeze(1)
                iou  = miou(out, mask)
                test_iou += iou.item() * image.size(0)
                test_iou_num += image.size(0)
                test_iou_all = test_iou / test_iou_num
                test_tbar.set_description('test iou=%.6f' % (test_iou_all))

                head = '../eval/maps/DNF/'+ self.cfg.datapath.split('/')[-1]
                if not os.path.exists(head):
                    os.makedirs(head)
                cv2.imwrite(head+'/'+name[0]+'.png', pred)
            print('test iou:{:.4f}'.format(test_iou / test_iou_num))


def parse_args():
    parser = argparse.ArgumentParser(description='DEFERNet')
    # dataset
    parser.add_argument('--dataset', type=str, default='NUAA-SIRST',
                        help='dataset name:  NUAA-SIRST, NUDT-SIRST')
    args = parser.parse_args()
    return args


if __name__=='__main__':
    args = parse_args()
    t = Test(dataset, DEFER, args)
    t.save()
