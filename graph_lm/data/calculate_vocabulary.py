from collections import Counter

from tqdm import tqdm
from typing import Iterable, List
from .word import Word
UNK = "_UNK_"
BLANK = "_BLANK_"


def calculate_map(vocab):
    return {k: i for i, k in enumerate(vocab)}


def decode_words(ids, vocab):
    return " ".join(vocab[i] if i < len(vocab) else BLANK for i in ids if i >= 0)


def decode_words_ctc(ids, vocab):
    return " ".join(vocab[i-1] if i-1 < len(vocab) and i > 0 else BLANK for i in ids if i >= 0)


def calculate_vocabulary(dataset, min_count=0):
    vocab = Counter()
    for sentence in dataset:
        vocab.update(sentence)
    print("Unique words: {}".format(len(vocab)))
    vocab = list(k for k, count in vocab.items() if count >= min_count)
    vocab.append(UNK)
    vocab.sort()
    return vocab


def calculate_vocabulary_and_tags(sentences:Iterable[List[Word]],total=None, min_count=0):
    vocab = Counter()
    taglist = set()
    for sentence in tqdm(sentences, desc="Calculating Vocabulary", total=total):
        vocab.update(word.text for word in sentence)
        taglist.update(word.tag for word in sentence)
    print("Unfiltered vocab: {}".format(len(vocab)))
    vocab = list(k for k, count in vocab.items() if count >= min_count)
    vocab.append(UNK)
    print("Filtered vocab: {}".format(len(vocab)))
    vocab.sort()
    taglist = list(taglist)
    taglist.append(UNK)
    taglist.sort()
    print("Tag count: {}".format(len(taglist)))
    return vocab, taglist
