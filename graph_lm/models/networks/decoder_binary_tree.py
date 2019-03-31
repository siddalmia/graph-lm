from tensorflow.contrib import slim

from .tree_utils import infix_indices, stack_tree
from .bintree_utils import binary_tree_resnet

from .ctc_output import calc_output


def decoder_binary_tree(latent, vocab_size, params, weights_regularizer=None, is_training=True, reuse=None):
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
    tree_layers = binary_tree_resnet(
        x0=h,
        depth=params.tree_depth,
        hidden_dim=params.decoder_dim,
        reuse=reuse
    )
    indices = infix_indices(depth)
    flat_layers = stack_tree(tree_layers, indices=indices)  # (L,N,V)
    logits = calc_output(
        flat_layers,
        vocab_size=vocab_size,
        params=params,
        weights_regularizer=weights_regularizer,
        is_training=is_training)
    return tree_layers, logits
