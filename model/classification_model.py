from .tweet_feature_extractor import TweetFeatureExtractor
from data.user import User
import torch
from torch import nn
from typing import List
from wikidata.wikidata import calculate_similarity_wikidata
from data.utils import get_tweets_avg_diffs, get_tweets_diffs
from data.utils import intensity_indexes


class BotClassifier(nn.Module):
    def __init__(self, word2vec_model, embedding_dim, rec_hidden_dim, tweet_features_dim, hidden_dim,
                 use_gdelt=False, use_TCN=False,
                 effective_history=91,
                 num_rec_layers=1, rec_dropout=0):
        super().__init__()

        self.use_gdelt = use_gdelt

        self.tweet_feature_extractor = TweetFeatureExtractor(word2vec_model, embedding_dim, rec_hidden_dim,
                                                             tweet_features_dim, num_layers=num_rec_layers,
                                                             dropout=rec_dropout, use_gdelt=self.use_gdelt,
                                                             use_TCN=use_TCN, effective_history=effective_history)

        num_handmade_features = 3
        self.hidden_dim = hidden_dim

        self.num_tweets_per_user = 100

        self.tweets_combiner = nn.Sequential(
            nn.BatchNorm1d(self.num_tweets_per_user * tweet_features_dim),
            nn.ReLU(),
            nn.Linear(self.num_tweets_per_user * tweet_features_dim, tweet_features_dim)
        )

        tweet_features_dim += num_handmade_features

        # account for the addition of general user data to the tensors
        if self.use_gdelt:
            tweet_features_dim += 1

        self.feature_extractor = nn.Sequential(
            nn.BatchNorm1d(tweet_features_dim),
            nn.ReLU(),
            nn.Linear(tweet_features_dim, hidden_dim)
        )

        self.classifier = nn.Sequential(
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 2),
            nn.Softmax(dim=1)
        )

        if use_gdelt:
            self.means = torch.Tensor([5.6675e+04, 6.6008e-01, 3.2708e+03, 6.6564e+02])
            self.stds = torch.Tensor([2.2061e+04, 2.8933e+00, 2.1951e+04, 1.3241e+03])
        else:
            self.means = torch.Tensor([5.6675e+04, 3.2708e+03, 6.6564e+02])
            self.stds = torch.Tensor([2.2061e+04, 2.1951e+04, 1.3241e+03])

    def forward(self, inputs: List[User], important_topics=None):
        """
        TODO:
        1) use the tweet feature extractor on the users
        2) combine the features of each user's tweets into a single feature vector per user
        3) add some more general user data to the batch (for each user)
        4) classify using these features
        """
        handmade_features = []

        # TASK 1
        tweet_lists = [user.tweets for user in inputs]
        device = next(self.parameters()).device

        users_tweets_features = self.tweet_feature_extractor(tweet_lists, [len(user.tweets) for user in inputs])

        # TASK 2
        users_tweets_features = self.tweets_combiner(users_tweets_features.view(len(inputs), -1))

        # for user data
        if self.use_gdelt:
            intense_indexes = intensity_indexes(get_tweets_diffs(tweet_lists), [len(user.tweets) for user in inputs])
        else:
            intense_indexes = None

        diffs = get_tweets_avg_diffs(tweet_lists)
        handmade_features.append(diffs.to(device).unsqueeze(1))

        # TASK 3
        if self.use_gdelt:
            sims = calculate_similarity_wikidata(tweet_lists, important_topics, intense_indexes)
            handmade_features.append(torch.Tensor(sims).to(device).unsqueeze(1))

        handmade_features.append(torch.Tensor([user.followers_count for user in inputs]).to(device).unsqueeze(1))
        handmade_features.append(torch.Tensor([user.friends_count for user in inputs]).to(device).unsqueeze(1))

        handmade_features = (torch.cat(handmade_features, dim=1) - self.means.to(device)) / self.stds.to(device)

        # TASK 4
        users_tweets_features = torch.cat((users_tweets_features, handmade_features), dim=1)
        features = self.feature_extractor(users_tweets_features)
        return self.classifier(features)
