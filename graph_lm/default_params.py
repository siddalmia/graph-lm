import json
import os

import six
import tensorflow as tf
from tensorflow.contrib.training import HParams


def load_hparams(model_dir):
    hparams = default_params()
    hparams_path = os.path.join(model_dir, 'configuration-hparams.json')
    assert os.path.exists(hparams_path)

    with open(hparams_path) as f:
        return hparams.parse_json(f.read())


def get_hparams(model_dir, validate=True):
    config_file = tf.flags.FLAGS.config
    hparams = default_params()
    hparams_path = os.path.join(model_dir, 'configuration-hparams.json')
    with open(config_file) as f:
        hparams.parse_json(f.read())

    if os.path.exists(hparams_path):
        if validate:
            with open(hparams_path) as f:
                hparam_dict = json.load(f)
            for k, v in six.iteritems(hparam_dict):
                oldval = getattr(hparams, k)
                assert oldval == v, "Incompatible key {}: save {}-> config {}".format(k, oldval, v)
    else:
        with open(hparams_path, 'w') as f:
            json.dump(hparams.values(), f)
    return hparams


def default_params():
    return HParams(
        model='ctasdsac',

        encoder_dim=256,
        decoder_dim=256,
        latent_dim=256,
        attention_dim=128,

        bias_smoothing=0.05,

        tree_depth=8,
        flat_length=300,

        lr=3e-4,
        l2=1e-7,
        clip_gradient_norm=1.,

        anneal_start=5000,
        anneal_end=200000,
        anneal_min=1e-4,

        model_version='v1',
        attn_mode='softmax',
        subsample=3,
        depth=6,
        listener_dim=320,
        dropout=0.,
        vae_depth=3,
        vae_dropout=0.,
        vae_dim=320,

        kl_min=1e-2,
        kernel_size=7
    )


"""
        encoder_dim=256,
        # query_dim=128,
        # value_dim=128,
        # decoder_dim=256,
        latent_dim=128,
        attention_dim=128,


        discriminator_dim=128,
        dis_lr=3e-4,
        gen_lr=3e-4,
        dis_steps=5
        """
