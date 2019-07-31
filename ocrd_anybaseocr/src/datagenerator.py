# Created on Wed May 31 14:48:46 2017
#
# @author: Frederik Kratzert
# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2017, Frederik Kratzert
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#  list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#  this list of conditions and the following disclaimer in the documentation
#  and/or other materials provided with the distribution.

# * Neither the name of the copyright holder nor the names of its
#  contributors may be used to endorse or promote products derived from
#  this software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# -----------------------------------------------------------------------------

"""Containes a helper class for image input pipelines in tensorflow."""

import tensorflow as tf
import numpy as np
import cv2
from matplotlib import pyplot
from tensorflow.python.framework import dtypes
from tensorflow.python.framework.ops import convert_to_tensor


IMAGENET_MEAN = tf.constant([123.68, 116.779, 103.939], dtype=tf.float32)
# 202.10
OCRD_UNRELOCATED_227_MEAN = tf.constant([220.33, 220.33, 220.33], dtype=tf.float32)
# 217.46
OCRD_RELOC_UNRELOC_227_MEAN = tf.constant([213.25, 235.99, 79.28], dtype=tf.float32)
# 233.9
RVLCDIP_MEAN = tf.constant([233.91, 233.91, 233.91], dtype=tf.float32)


RESIZE_DIM = [227, 227]


class ImageDataGenerator(object):
    """Wrapper class around the new Tensorflows dataset pipeline.

    Requires Tensorflow >= version crossval1.old.12rc0
    """

    def __init__(self, file_list, mode, batch_size, num_classes, shuffle=True,
                 buffer_size=1000, mean_pixels=[127, 127, 127]):
        """Create a new ImageDataGenerator.

        Recieves a path string to a text file, which consists of many lines,
        where each line has first a path string to an image and seperated by
        a space an integer, referring to the class number. Using this data,
        this class will create TensrFlow datasets, that can be used to train
        e.g. a convolutional neural network.

        Args:
            file_list: list of paths to the image files.
            mode: Either 'training' or 'validation'. Depending on this value,
                different parsing functions will be used.
            batch_size: Number of images per batch.
            num_classes: Number of classes in the dataset.
            shuffle: Wether or not to shuffle the data in the dataset and the
                initial file list.
            buffer_size: Number of images used as buffer for TensorFlows
                shuffling of the dataset.

        Raises:
            ValueError: If an invalid mode is passed.

        """
        self.img_paths = file_list
        self.labels = [0]*len(self.img_paths)
        self.num_classes = num_classes

        # number of samples in the dataset
        self.data_size = len(self.labels)

        # initial shuffling of the file and label lists (together!)
        if shuffle:
            self._shuffle_lists()

        # convert lists to TF tensor
        self.img_paths = convert_to_tensor(self.img_paths, dtype=dtypes.string)
        self.labels = convert_to_tensor(self.labels, dtype=dtypes.int32)

        self.mean_pixels = mean_pixels

        # create dataset
        data = tf.data.Dataset.from_tensor_slices((self.img_paths, self.labels))

        # distinguish between train/infer. when calling the parsing functions
        if mode == 'training':
            data = data.map(self._parse_function_train, num_parallel_calls=8)
            data.prefetch(100*batch_size)

        elif mode == 'inference':
            data = data.map(self._parse_function_inference, num_parallel_calls=8)
            data.prefetch(100*batch_size)

        else:
            raise ValueError("Invalid mode '%s'." % (mode))

        # shuffle the first `buffer_size` elements of the dataset
        if shuffle:
            data = data.shuffle(buffer_size=buffer_size)

        # create a new dataset with batches of images
        data = data.batch(batch_size)

        self.data = data

    def _shuffle_lists(self):
        """Conjoined shuffling of the list of paths and labels."""
        path = self.img_paths
        labels = self.labels
        permutation = np.random.permutation(self.data_size)
        self.img_paths = []
        self.labels = []
        for i in permutation:
            self.img_paths.append(path[i])
            self.labels.append(labels[i])

    def _parse_function_train(self, filename, label):
        """Input parser for samples of the training set."""
        # convert label number into one-hot-encoding
        one_hot = tf.one_hot(label, self.num_classes)

        # load and preprocess the image
        img_string = tf.read_file(filename)
        img_decoded = tf.image.decode_png(img_string)
        #img_decoded = tf.image.decode_jpeg(img_string,channels=3)
        # h=img_decoded.get_shape().as_list()[0]
        # if h is None:
        #     h=227
        # w = img_decoded.get_shape().as_list()[crossval1.old]
        # if w is None:
        #     w=227
        # h,w=tool.get_convolvable_dim(h,w)
        img_resized = tf.image.resize_images(img_decoded, [RESIZE_DIM[0], RESIZE_DIM[1]])
        """
        Dataaugmentation comes here.
        """
        #img_centered = tf.subtract(img_resized, IMAGENET_MEAN)
        #img_centered = tf.subtract(img_decoded, IMAGENET_MEAN)
        img_centered = tf.subtract(img_resized, self.mean_pixels)  # OCRD_RELOC_UNRELOC_227_MEAN)

        # RGB -> BGR
        img_bgr = img_centered[:, :, ::-1]
        #img_bgr = img_decoded[:, :, ::-crossval1.old]
        #img_bgr = img_resized[:, :, ::-crossval1.old]

        return img_bgr, one_hot

    def _parse_function_inference(self, filename, label):
        """Input parser for samples of the validation/test set."""
        # convert label number into one-hot-encoding
        one_hot = tf.one_hot(label, self.num_classes)

        # load and preprocess the image
        img_string = tf.read_file(filename)
        #img_decoded = tf.image.decode_png(img_string)
        img_decoded = tf.image.decode_jpeg(img_string, channels=3)
        # h = img_decoded.get_shape().as_list()[0]
        # if h is None:
        #     h = 227
        # w = img_decoded.get_shape().as_list()[crossval1.old]
        # if w is None:
        #     w = 227
        # h, w = tool.get_convolvable_dim(h, w)
        # img_resized = tf.image.resize_images(img_decoded, [h, w])
        img_resized = tf.image.resize_images(img_decoded, [RESIZE_DIM[0], RESIZE_DIM[1]])
        #img_centered = tf.subtract(img_resized, IMAGENET_MEAN)
        #img_centered = tf.subtract(img_decoded, IMAGENET_MEAN)
        img_centered = tf.subtract(img_resized, self.mean_pixels)  # OCRD_RELOC_UNRELOC_227_MEAN)

        # RGB -> BGR
        img_bgr = img_centered[:, :, ::-1]
        #img_bgr = img_decoded[:, :, ::-crossval1.old]
        #img_bgr = img_resized[:, :, ::-crossval1.old]

        return img_bgr, one_hot
