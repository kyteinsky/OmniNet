#
# Copyright 2019 Subhojeet Pramanik, Aman Husain, Priyanka Agrawal
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ======================================================================
"""
Authors: Subhojeet Pramanik

OmniNet prediction script.

"""
import os
import argparse
import pickle
import json
import cv2
import torch
import numpy as np
import libs.omninet as omninet
import sys, os
import warnings
warnings.filterwarnings("ignore")

from PIL import Image
from torchvision import transforms


penn_vocab_file='conf/penn_vocab.json'
vqa_vocab_file='conf/vqa_vocab.pkl'
hmdb_labels_file='conf/hmdblabels.txt'

video_resize_height=300
video_resize_width=300
clip_len=16
crop_size=224


def extract_frames_from_video(video_file):
    capture=cv2.VideoCapture(video)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    EXTRACT_FREQUENCY = 4
    if frame_count // EXTRACT_FREQUENCY <= 16:
        EXTRACT_FREQUENCY -= 1
        if frame_count // EXTRACT_FREQUENCY <= 16:
            EXTRACT_FREQUENCY -= 1
            if frame_count // EXTRACT_FREQUENCY <= 16:
                EXTRACT_FREQUENCY -= 1
    count = 0
    i = 0
    retaining = True
    frames=[]
    while (count < frame_count and retaining):
        retaining, frame = capture.read()
        if frame is None:
            continue

        if count % EXTRACT_FREQUENCY == 0:
            if (frame_height != video_resize_height) or (frame_width != video_resize_width):
                frame = cv2.resize(frame, (video_resize_width, video_resize_height))
            frames.append(frame)
            i += 1
        count += 1
    capture.release()

    frame_count = len(frames)
    buffer = np.empty((frame_count, video_resize_height, video_resize_width, 3), np.dtype('float32'))
    for i, frame in enumerate(frames):
        buffer[i] = np.array(frame)
    time_index=0
    height_index=0
    width_index=0

    buffer = buffer[time_index:time_index + clip_len,
                height_index:height_index + crop_size,
                width_index:width_index + crop_size, :]
    #Normalize
    buffer=buffer/255
    for i, frame in enumerate(buffer):
        frame -= np.array([[[0.485, 0.456, 0.406]]])
        frame /= np.array([[[0.229, 0.224, 0.225]]])
        buffer[i] = frame
    buffer=buffer.transpose((0, 3, 1, 2))
    buffer=torch.from_numpy(buffer)
    return buffer.unsqueeze(0)

def extract_pixels_from_image(image):
    img = Image.open(image)
    img = img.convert('RGB')
    normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    tfs=transforms.Compose([
                                    transforms.Resize(int(224*1.14)),
                                    transforms.CenterCrop(224),
                                    transforms.ToTensor(),
                                    normalize,
                                ])
    img=tfs(img)
    img=img.unsqueeze(0)
    return img

def image_filenames(folder):
    """
    Returns list of images in a folder that are in correct format.
    Images are checked using OpenCV imread()
    """
    img_files = []
    for filename in os.listdir(folder):
        img = cv2.imread(os.path.join(folder,filename))
        if img is not None:
            img_files.append(os.path.join(folder,filename))
    return img_files


def download_model(task):
    """
    Download the pre-trained model files if not present in current directory.
    """
    try:
        if not os.path.isfile('model.pth'):
            with open('checkpoint_urls.json') as f:
                os.system(f'wget {json.loads(f.read())[task]} -O model_file.zip')
                os.system('unzip model_file.zip')
                os.system('rm -rf model_file.zip')
    except Exception as e:
        raise e


def decoding(task, model):
    """
    Returns decoded text based on task
    """
    if task=='caption':
        prediction = model.decode_greedy('IMAGE_CAPTION',num_steps=100)
        prediction = prediction.argmax(-1)
        prediction = model.english_language_perph.decode_tokens(prediction)
        # print('Caption Prediction: %s'%prediction[0])
        return prediction[0]

    elif task=='hmdb':
        prediction = model.decode_greedy('HMDB', num_steps=1)
        prediction = prediction.argmax(-1).cpu().tolist()[0][0]
        with open(hmdb_labels_file,'r') as  f:
            lines=f.readlines()
        id_to_label=dict()
        for l in lines:
            id,label=l.split(' ')
            id_to_label[id]=label
        prediction=id_to_label[str(prediction)]
        # print('Action recognition prediction: %s'%prediction)
        return prediction

    elif task=='vqa':
        prediction = model.decode_greedy('VQA', num_steps=1)
        prediction = prediction.argmax(-1).cpu().tolist()[0][0]
        with open(vqa_vocab_file,'rb') as f:
            ans_to_id,id_to_ans=pickle.loads(f.read())
        prediction=id_to_ans[prediction]
        # print('VQA Prediction: %s'%prediction)
        return prediction

    elif task=='penn':
        if text is None:
            raise Exception('No text has been provided. POS tagging cannot proceed.')
        prediction= model.decode_greedy('PENN', num_steps=len(text.split(' ')))
        prediction=prediction.argmax(-1).cpu().tolist()[0]
        with open(penn_vocab_file,'r') as f:
            data=json.loads(f.read())
        id_to_tag=data['id_to_tag']
        penn_text=''
        for p in prediction:
            penn_text='%s %s'%(penn_text,id_to_tag[str(p)])
        # print('POS tagging Prediction: %s'%penn_text)
        return penn_text


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='OmniNet prediction script.')
    parser.add_argument('task', help='Task to predict for.')
    parser.add_argument('--model_file', default='model.pth', help='Location to pretrained model file.')
    parser.add_argument('--image', default=None, help='Image file to encode')
    parser.add_argument('--image_folder', default=None, help='Image folder path')
    parser.add_argument('--video', default=None, help='Video file to encodre')
    parser.add_argument('--text', default=None, help='Text to encode')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()
    model_file=args.model_file
    task=args.task
    image=args.image
    image_folder=args.image_folder
    video=args.video
    text=str(args.text)
    verbose=args.verbose
    if verbose==False:
        sys.stdout = open(os.devnull, 'w')
    #Load Omninet model
    download_model(task)
    model = omninet.OmniNet(gpu_id=0)
    model.restore_file(model_file)
    model=model.to(0)
    model=model.eval()
    print_decor = {'caption':'Caption Prediction:','hmdb':'Action recognition prediction:',
                   'vqa':'VQA Prediction:', 'penn':'POS tagging Prediction:'}
    if verbose==False:
        sys.stdout = sys.__stdout__

    if image_folder != None:
        for im in image_filenames(image_folder):
            name = im
            model.reset(1)
            im=extract_pixels_from_image(im)
            im=im.to(0)
            model.encode_images(im)
            print(name,' == %s'%decoding(task, model))
    else:
        if image is not None:
            image=extract_pixels_from_image(image)
            image=image.to(0)
            model.encode_images(image)
        if text is not None:
            model.encode_englishtexts([text])
        if video is not None:
            video=extract_frames_from_video(video)
            video=video.to(0)
            model.encode_videos(video)
        print(print_decor[task], decoding(task, model))
    
    
    


        

        

        