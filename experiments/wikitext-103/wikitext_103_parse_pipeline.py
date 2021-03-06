import os

import tensorflow as tf

from graph_lm.data.read_wikitext import FILES_RAW, PARSED, read_wikitext_raw
from graph_lm.data.write_records import write_sentences_parsed
from graph_lm.data.parser import get_pipeline, parse_docs


def main(_argv):
    os.makedirs(tf.flags.FLAGS.output_dir, exist_ok=True)
    pipeline = get_pipeline()
    data_files = [os.path.join(tf.flags.FLAGS.data_dir, f) for f in FILES_RAW]
    data_doc_counts = [sum(1 for _ in read_wikitext_raw(f)) for f in data_files]
    data_parsed = [
        parse_docs(read_wikitext_raw(f), pipeline=pipeline, total=count)
        for f, count
        in zip(data_files, data_doc_counts)
    ]
    for f, sentences in zip(PARSED, data_parsed):
        write_sentences_parsed(
            sentences=sentences,
            output_file=os.path.join(tf.flags.FLAGS.output_dir, f)
        )


if __name__ == '__main__':
    tf.logging.set_verbosity(tf.logging.INFO)
    tf.flags.DEFINE_string('data_dir', '/mnt/data/projects/data/wikitext-103-raw', 'Data directory')
    tf.flags.DEFINE_string('output_dir', '../../data/wikitext-103', 'Data directory')
    tf.flags.DEFINE_string('stanfordnlp_dir', '/mnt/data/projects/stanfordnlp_resources', 'Data directory')
    tf.app.run()
