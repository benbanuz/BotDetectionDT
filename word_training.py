from gensim.models import Word2Vec
import pandas as pd
import re
from random import randint
import numpy as np
import nltk
import torch

from nltk.tokenize import word_tokenize as wt


def w2v_pre_process(string: str, mentions, urls):
    string = re.sub(r"(?<=[\s^])@(?=[\s$])", "at", string)

    # replace mentions with @
    for mention in mentions:
        screen_name = mention["screen_name"]
        string = string.replace(f"@{screen_name}", "@")

    # remove $
    string = string.replace("$", " ")

    # replace the urls with $
    for url in urls:
        url_str = url["url"]
        string = string.replace(url_str, "$")

    # remove special chars
    string = re.sub(r"[^\w@\$]", " ", string)

    tokens = wt(string)
    return tokens


def train(model: Word2Vec, db: pd.DataFrame, batch_size: int, num_epoches: int = None):
    word_lists = [w2v_pre_process(row["seq"], row["mentions"], row["urls"]) for _, row in db.iterrows()]
    model.train(word_lists, total_examples=len(word_lists), epochs=num_epoches)
    return model


def embed(model: Word2Vec, tweets: list):
    seq_list = []
    for tweet in tweets:
        word_list = w2v_pre_process(tweet.text, tweet.entities["user_mentions"],
                                    tweet.entities["urls"] + tweet.entities["media"])
        seq_list.append(torch.stack([torch.from_numpy(model.wv.word_vec(word)) for word in word_list]))
    return seq_list
