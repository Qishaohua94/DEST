import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import numpy as np
import torch
import torch.optim as optim
import torch.nn as nn
import shutil,json
import argparse

from tools.Trainer import ModelNetTrainer
from tools.ImgDataset import MultiviewImgDataset, SingleImgDataset
from models.DEST import DESTM, DESTS

parser = argparse.ArgumentParser()
parser.add_argument("-name", "--name", type=str, help="Name of the experiment", default="DEST")
parser.add_argument("-bs", "--batchSize", type=int, help="Batch size for the second stage", default=6)
parser.add_argument("-num_models", type=int, help="number of models per class", default=2468)
parser.add_argument("-lr", type=float, help="learning rate", default=5e-5)
parser.add_argument("-weight_decay", type=float, help="weight decay", default=0.001)
parser.add_argument("-no_pretraining", dest='no_pretraining', action='store_true')
parser.add_argument("-backbone_name", "--backbone_name", type=str, help="backbone model name", default="swin")
parser.add_argument("-num_views", type=int, help="number of views", default=12)
parser.add_argument("-train_path", type=str, default="./modelnet40_12/*/train")
parser.add_argument("-val_path", type=str, default="./modelnet40_12/*/test")

parser.set_defaults(train=False)

def create_folder(log_dir):

    if not os.path.exists(log_dir):
        os.mkdir(log_dir)
    else:
        print('WARNING: summary folder already exists!! It will be overwritten!!')
        shutil.rmtree(log_dir)
        os.mkdir(log_dir)

if __name__ == '__main__':
    args = parser.parse_args()

    pretraining = not args.no_pretraining
    log_dir = args.name
    create_folder(args.name)
    config_f = open(os.path.join(log_dir, 'config.json'), 'w')
    json.dump(vars(args), config_f)
    config_f.close()

    # STAGE 1 
    log_dir = args.name+'_stage_1'
    create_folder(log_dir)
    cnet = DESTS(args.name, nclasses=40, pretraining=pretraining, backbone_name=args.backbone_name)

    optimizer = optim.Adam(cnet.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    
    n_models_train = args.num_models*args.num_views

    train_dataset = SingleImgDataset(args.train_path, scale_aug=False, rot_aug=False, num_models=n_models_train, num_views=args.num_views)
    train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=80, shuffle=True, num_workers=6)

    val_dataset = SingleImgDataset(args.val_path, scale_aug=False, rot_aug=False, test_mode=True)
    val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=80, shuffle=False, num_workers=6)
    print('num_train_files: '+str(len(train_dataset.filepaths)))
    print('num_val_files: '+str(len(val_dataset.filepaths)))
    trainer = ModelNetTrainer(cnet, train_loader, val_loader, optimizer, nn.CrossEntropyLoss(), 'dest-s', log_dir, num_views=1)
    trainer.train(30)

    # STAGE 2 
    log_dir = args.name+'_stage_2'
    create_folder(log_dir)
    cnet_2 = DESTM(args.name, cnet, nclasses=40, backbone_name='swin', num_views=args.num_views)
    del cnet

    optimizer = optim.Adam(cnet_2.parameters(), lr=args.lr, weight_decay=args.weight_decay, betas=(0.9, 0.999))
    
    train_dataset = MultiviewImgDataset(args.train_path, scale_aug=False, rot_aug=False, num_models=n_models_train, num_views=args.num_views)
    train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=args.batchSize, shuffle=False, num_workers=6)

    val_dataset = MultiviewImgDataset(args.val_path, scale_aug=False, rot_aug=False, num_views=args.num_views)
    val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=args.batchSize, shuffle=False, num_workers=6)
    print('num_train_files: '+str(len(train_dataset.filepaths)))
    print('num_val_files: '+str(len(val_dataset.filepaths)))
    trainer = ModelNetTrainer(cnet_2, train_loader, val_loader, optimizer, nn.CrossEntropyLoss(), 'dest-m', log_dir, num_views=args.num_views)
    trainer.train(50)
