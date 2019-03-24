import math
import os

import tensorflow as tf
from tensorflow.contrib import slim
from tensorflow.contrib.cudnn_rnn.python.layers.cudnn_rnn import CudnnLSTM, CUDNN_RNN_BIDIRECTION
from .rnn_util import lstm
from ..callbacks.ctc_callback import CTCHook
from ..kl import kl
from ..sparse import sparsify


from .model_vae_ctc_flat import vae_flat_encoder


def calc_output(x, vocab_size, params, weights_regularizer=None):
    # X: (N,*, D)
    # Y: (N,*, V)
    with tf.variable_scope('output_mlp', reuse=tf.AUTO_REUSE):
        h = x
        h = slim.fully_connected(
            inputs=h,
            num_outputs=params.decoder_dim,
            activation_fn=tf.nn.leaky_relu,
            scope='output_mlp_1',
            weights_regularizer=weights_regularizer
        )
        h = slim.fully_connected(
            inputs=h,
            num_outputs=params.decoder_dim,
            activation_fn=tf.nn.leaky_relu,
            scope='output_mlp_2',
            weights_regularizer=weights_regularizer
        )
        h = slim.fully_connected(
            inputs=h,
            num_outputs=vocab_size + 1,
            activation_fn=None,
            scope='output_mlp_3',
            weights_regularizer=weights_regularizer
        )
    return h


def calc_children(x, params, weights_regularizer=None):
    # X: (N,x, D)
    # Y: (N,2x,D)
    with tf.variable_scope('children_mlp', reuse=tf.AUTO_REUSE):
        h = x
        h = slim.fully_connected(
            inputs=h,
            num_outputs=params.decoder_dim,
            activation_fn=tf.nn.leaky_relu,
            scope='output_mlp_1',
            weights_regularizer=weights_regularizer
        )
        h = slim.fully_connected(
            inputs=h,
            num_outputs=params.decoder_dim,
            activation_fn=tf.nn.leaky_relu,
            scope='output_mlp_2',
            weights_regularizer=weights_regularizer
        )
        h = slim.fully_connected(
            inputs=h,
            num_outputs=2 * params.decoder_dim,
            activation_fn=None,
            scope='output_mlp_3',
            weights_regularizer=weights_regularizer
        )
        kids = tf.reshape(h, (tf.shape(h)[0], 2 * h.shape[1].value, params.decoder_dim))  # params.decoder_dim))
        print("Calc child: {}->{}".format(x, kids))
        return kids


def infix_indices(depth, stack=[]):
    if depth >= 0:
        left = infix_indices(depth - 1, stack + [0])
        right = infix_indices(depth - 1, stack + [1])
        middle = stack
        return left + [middle] + right
    else:
        return []


def stack_tree(outputs, indices):
    # outputs:[ (N,V), (N,2,V), (N,2,2,V)...]
    # indices:[ paths]

    slices = []
    for idx in indices:
        depth = len(idx)
        output = outputs[depth]
        output_idx = 0
        mult = 1
        for i in reversed(idx):
            output_idx += mult * i
            mult *= 2
        slices.append(output[:, output_idx, :])
    stacked = tf.stack(slices, axis=0)  # (L,N,V)
    return stacked


def vae_decoder(latent, vocab_size, params, weights_regularizer=None):
    # latent (N, D)
    depth = params.tree_depth
    assert depth >= 0
    h = slim.fully_connected(
        latent,
        num_outputs=params.decoder_dim,
        scope='projection',
        activation_fn=None,
        weights_regularizer=weights_regularizer
    )
    h = tf.expand_dims(h, axis=1)

    layers = []
    layers.append(h)
    for i in range(depth):
        h = calc_children(h, params=params, weights_regularizer=weights_regularizer)
        layers.append(h)
    return layers


def make_model_vae_binary_tree(
        run_config,
        vocab
):
    vocab_size = vocab.shape[0]
    print("Vocab size: {}".format(vocab_size))

    def model_fn(features, labels, mode, params):
        is_training = mode == tf.estimator.ModeKeys.TRAIN
        # Inputs
        tokens = features['features']  # (N, L)
        token_lengths = features['feature_length']  # (N,)
        sequence_mask = tf.sequence_mask(maxlen=tf.shape(tokens)[1], lengths=token_lengths)
        n = tf.shape(tokens)[0]
        depth = params.tree_depth

        with tf.control_dependencies([
            tf.assert_greater_equal(tf.pow(2, depth + 1) - 1, token_lengths, message="Tokens longer than tree size"),
            tf.assert_less_equal(tokens, vocab_size - 1, message="Tokens larger than vocab"),
            tf.assert_greater_equal(tokens, 0, message="Tokens less than 0")
        ]):
            tokens = tf.identity(tokens)

        if params.l2 > 0:
            weights_regularizer = slim.l2_regularizer(params.l2)
        else:
            weights_regularizer = None

        # Encoder
        mu, logsigma = vae_flat_encoder(
            tokens=tokens,
            token_lengths=token_lengths,
            vocab_size=vocab_size,
            params=params,
            n=n,
            weights_regularizer=weights_regularizer
        )
        # Sampling
        latent_sample, latent_prior_sample = kl(
            mu=mu,
            logsigma=logsigma,
            params=params,
            n=n)

        # Decoder
        with tf.variable_scope('vae_decoder') as decoder_scope:
            tree_layers = vae_decoder(
                latent=latent_sample,
                vocab_size=vocab_size,
                params=params,
                weights_regularizer=weights_regularizer)
            indices = infix_indices(depth)
            flat_layers = stack_tree(tree_layers, indices=indices)  # (L,N,V)
            logits = calc_output(
                flat_layers,
                vocab_size=vocab_size,
                params=params,
                weights_regularizer=weights_regularizer)
            sequence_length_ctc = tf.tile(tf.shape(logits)[0:1], (n,))

        print("Lengths: {} vs {}".format(len(indices), math.pow(2, depth + 1) - 1))
        assert len(indices) == int(math.pow(2, depth + 1) - 1)
        assert max(len(i) for i in indices) == depth
        assert len(tree_layers) == depth + 1

        ctc_labels_sparse = sparsify(tokens, sequence_mask)
        ctc_labels = tf.sparse_tensor_to_dense(ctc_labels_sparse, default_value=-1)
        # ctc_labels = tf.sparse_transpose(ctc_labels, (1,0))
        print("Labels: {}".format(ctc_labels))
        # tf.tile(tf.pow([2], depth), (n,))
        print("CTC: {}, {}, {}".format(ctc_labels, logits, sequence_length_ctc))
        ctc_loss_raw = tf.nn.ctc_loss(
            labels=ctc_labels_sparse,
            sequence_length=sequence_length_ctc,
            inputs=logits,
            # sequence_length=tf.shape(logits)[0],
            ctc_merge_repeated=False,
            # preprocess_collapse_repeated=False,
            # ctc_merge_repeated=True,
            # ignore_longer_outputs_than_inputs=False,
            time_major=True
        )
        ctc_loss = tf.reduce_mean(ctc_loss_raw)
        tf.losses.add_loss(ctc_loss)

        total_loss = tf.losses.get_total_loss()

        # Generated data
        with tf.variable_scope(decoder_scope, reuse=True):
            gtree_layers = vae_decoder(
                latent=latent_prior_sample,
                vocab_size=vocab_size,
                params=params,
                weights_regularizer=weights_regularizer)
            gflat_layers = stack_tree(gtree_layers, indices=indices)  # (L,N,V)
            glogits = calc_output(
                gflat_layers,
                vocab_size=vocab_size,
                params=params,
                weights_regularizer=weights_regularizer)

        autoencode_hook = CTCHook(
            logits=logits,
            lengths=sequence_length_ctc,
            vocab=vocab,
            path=os.path.join(run_config.model_dir, "autoencoded", "autoencoded-{:08d}.csv"),
            true=ctc_labels,
            name="Autoencoded"
        )
        generate_hook = CTCHook(
            logits=glogits,
            lengths=sequence_length_ctc,
            vocab=vocab,
            path=os.path.join(run_config.model_dir, "generated", "generated-{:08d}.csv"),
            true=ctc_labels,
            name="Generated"
        )
        evaluation_hooks = [autoencode_hook, generate_hook]

        tf.summary.scalar('ctc_loss', ctc_loss)
        tf.summary.scalar('total_loss', total_loss)

        # Train
        optimizer = tf.train.AdamOptimizer(params.lr)
        train_op = slim.learning.create_train_op(
            total_loss,
            optimizer,
            clip_gradient_norm=params.clip_gradient_norm)
        eval_metric_ops = {
            'ctc_loss_eval': tf.metrics.mean(ctc_loss_raw),
            'token_lengths_eval': tf.metrics.mean(token_lengths)
        }

        return tf.estimator.EstimatorSpec(
            mode=mode,
            loss=total_loss,
            eval_metric_ops=eval_metric_ops,
            evaluation_hooks=evaluation_hooks,
            train_op=train_op)

    return model_fn