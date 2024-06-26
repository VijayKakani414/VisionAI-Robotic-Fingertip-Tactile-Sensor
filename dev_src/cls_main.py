# --------------------------------------------------------------------------
# Tensorflow Implementation of Tacticle Sensor Project
# Licensed under The MIT License [see LICENSE for details]
# Written by Cheng-Bin Jin
# Email: sbkim0407@gmail.com
# Re-used for Vision-based tactile sensor mechanism for the estimation of contact position and force distribution using deep learning
# --------------------------------------------------------------------------
import os
import cv2
import logging
import numpy as np
import tensorflow as tf
from datetime import datetime

import utils as utils
from cls_dataset import Dataset
from cls_resnet import ResNet18
from cls_solver import Solver


FLAGS = tf.flags.FLAGS
tf.flags.DEFINE_string('gpu_index', '0', 'gpu index if you have multiple gpus, default: 0')
tf.flags.DEFINE_integer('mode', 0, '0 for left-and-right input, 1 for only one camera input, default: 0')
tf.flags.DEFINE_string('img_format', '.jpg', 'image format, default: .jpg')
tf.flags.DEFINE_integer('batch_size', 128, 'batch size for one iteration, default: 256')
tf.flags.DEFINE_float('resize_factor', 0.5, 'resize the original input image, default: 0.5')
tf.flags.DEFINE_string('shape', 'circle', 'shape folder select from [circle|hexagon|square], default: circle')
tf.flags.DEFINE_bool('is_train', True, 'training or inference mode, default: True')
tf.flags.DEFINE_float('learning_rate', 1e-4, 'initial learning rate for optimizer, default: 0.0001')
tf.flags.DEFINE_float('weight_decay', 1e-6, 'weight decay for model to handle overfitting, default: 1e-6')
tf.flags.DEFINE_integer('epoch', 1000, 'number of epochs, default: 1000')
tf.flags.DEFINE_integer('print_freq', 5, 'print frequence for loss information, default:  5')
tf.flags.DEFINE_string('load_model', None, 'folder of saved model that you wish to continue training '
                                           '(e.g. 20191110-144629), default: None')


def print_main_parameters(logger, flags):
    if flags.is_train:
        logger.info('\nmain func parameters:')
        logger.info('gpu_index: \t\t{}'.format(flags.gpu_index))
        logger.info('mode: \t\t{}'.format(flags.mode))
        logger.info('img_format: \t\t{}'.format(flags.img_format))
        logger.info('resize_factor: \t{}'.format(flags.resize_factor))
        logger.info('shape: \t\t{}'.format(flags.shape))
        logger.info('is_train: \t\t{}'.format(flags.is_train))
        logger.info('learning_rate: \t{}'.format(flags.learning_rate))
        logger.info('weight_decay: \t{}'.format(flags.weight_decay))
        logger.info('epoch: \t\t{}'.format(flags.epoch))
        logger.info('print_freq: \t\t{}'.format(flags.print_freq))
        logger.info('load_model: \t\t{}'.format(flags.load_model))
    else:
        print('main func parameters:')
        print('-- gpu_index: \t\t{}'.format(flags.gpu_index))
        print('-- mode: \t\t{}'.format(flags.mode))
        print('-- format: \t\t{}'.format(flags.img_format))
        print('-- resize_factor: \t{}'.format(flags.resize_factor))
        print('-- shape: \t\t{}'.format(flags.shape))
        print('-- is_train: \t\t{}'.format(flags.is_train))
        print('-- learning_rate: \t{}'.format(flags.learning_rate))
        print('-- weight_decay: \t{}'.format(flags.weight_decay))
        print('-- epoch: \t\t{}'.format(flags.epoch))
        print('-- print_freq: \t\t{}'.format(flags.print_freq))
        print('-- load_model: \t\t{}'.format(flags.load_model))

def main(_):
    os.environ["CUDA_VISIBLE_DEVICES"] = FLAGS.gpu_index

    # Initialize model and log folders
    if FLAGS.load_model is None:
        cur_time = datetime.now().strftime("%Y%m%d-%H%M%S")
    else:
        cur_time = FLAGS.load_model

    model_dir, log_dir = utils.make_folders_simple(cur_time=cur_time)

    # Logger
    logger = logging.getLogger(__name__)  # logger
    logger.setLevel(logging.INFO)
    utils.init_logger(logger=logger, log_dir=log_dir, is_train=FLAGS.is_train, name='main')
    print_main_parameters(logger, flags=FLAGS)

    # Initialize dataset
    data = Dataset(shape=FLAGS.shape,
                   mode=FLAGS.mode,
                   img_format=FLAGS.img_format,
                   resize_factor=FLAGS.resize_factor,
                   is_train=FLAGS.is_train,
                   log_dir=log_dir,
                   is_debug=True)

    # # Initialize model
    # model = ResNet18(input_shape=data.input_shape,
    #                  num_classes=5,
    #                  lr=FLAGS.learning_rate,
    #                  weight_decay=FLAGS.weight_decay,
    #                  total_iters=int(np.ceil(FLAGS.epoch * data.num_train / FLAGS.batch_size)),
    #                  is_train=FLAGS.is_train,
    #                  log_dir=log_dir)
    #
    # # Initialize solver
    # solver = Solver(model, data)
    #
    # # Initialize saver
    # saver = tf.compat.v1.train.Saver(max_to_keep=1)
    #
    # if FLAGS.is_train is True:
    #     train(solver, saver, logger, model_dir, log_dir)
    # else:
    #     test(solver, saver, model_dir, log_dir)


def train(solver, saver, logger, model_dir, log_dir):
    best_acc = 0.
    iter_time, eval_time = 0, 0
    total_iters = int(np.ceil(FLAGS.epoch * solver.data.num_train / FLAGS.batch_size))
    eval_iters = total_iters // 100

    if FLAGS.load_model is not None:
        flag, iter_time = load_model(saver=saver, solver=solver, model_dir=model_dir, logger=logger, is_train=True)
        if flag is True:
            logger.info(' [!] Load Success! Iter: {}'.format(iter_time))
        else:
            exit(' [!] Failed to restore model {}'.format(FLAGS.load_model))

    # Tensorbaord writer
    tb_writer = tf.compat.v1.summary.FileWriter(logdir=log_dir, graph=solver.sess.graph_def)

    while iter_time < total_iters:
        total_loss, data_loss, reg_term, batch_acc, summary = solver.train(batch_size=FLAGS.batch_size)

        # Print loss information
        if iter_time % FLAGS.print_freq == 0:
            msg = "[{0:5} / {1:5}] Total loss: {2:.3f}, Data loss: {3:.3f}, Reg. term: {4:.5f}, Batch acc. {5:.2%}"
            print(msg.format(iter_time, total_iters, total_loss, data_loss, reg_term, batch_acc))

            # Write to tensorbaord
            tb_writer.add_summary(summary, iter_time)
            tb_writer.flush()

        if (iter_time != 0) and ((iter_time % eval_iters == 0) or (iter_time + 1 == total_iters)):
            cur_acc, eval_summary = solver.eval(batch_size=FLAGS.batch_size)

            # Write the summary of evaluation on tensorboard
            tb_writer.add_summary(eval_summary, eval_time)
            tb_writer.flush()

            if cur_acc > best_acc:
                best_acc = cur_acc

            print('Acc.: {:.2%}, Best Acc.: {:.2%}'.format(cur_acc, best_acc))
            eval_time += 1

        iter_time += 1


def test (solver, saver, model_dir, log_dir):
    print("Hello test function")


def load_model(saver, solver, model_dir, logger=None, is_train=False):
    if is_train:
        logger.info(' [*] Reading checkpoint...')
    else:
        print(' [*] Reading checkpoint...')

    ckpt = tf.train.get_checkpoint_state(model_dir)
    if ckpt and ckpt.model_checkpoint_path:
        ckpt_name = os.path.basename(ckpt.model_checkpoint_path)
        saver.restore(solver.sess, os.path.join(model_dir, ckpt_name))

        meta_graph_path = ckpt.model_checkpoint_path + '.meta'
        iter_time = int(meta_graph_path.split('-')[-1].split('.')[0])

        return True, iter_time
    else:
        return False, None

if __name__ == '__main__':
    tf.compat.v1.app.run()