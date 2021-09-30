"""
    This script will pull the specified number of tweets from
    a user and attempt to create a list of categories the user
    discusses.
"""

import os
import json
from argparse import ArgumentParser
from collections import defaultdict
from typing import Dict

from google.cloud.language_v1.types.language_service import Entity

from ec601_proj2 import twitter_utils
from ec601_proj2.twitter_utils import (
    Tweet,
    TweetCount,
    TwitterUser
)

from ec601_proj2.google_nlp import (
    LanguageClient,
    InvalidArgument
)


def classify_tweets(grouping: Dict[str, list[Tweet]]):
    classifications = defaultdict(list)
    for entity, tweets in grouping.items():
        text = " ".join([t.text for t in tweets])
        try:
            classification = LanguageClient.classify_text(text)
            classifications[entity].append(classification)
        except InvalidArgument:
            # calssifying tweet failed, ignore it
            pass

    return classifications


def group_tweets_by_entities(tweets: list[Tweet]) -> Dict[str, list[Tweet]]:
    grouping = defaultdict(list)
    for tweet in tweets:
        response = LanguageClient.analyze_entities(tweet.text)
        for entity in response.entities:
            grouping[entity.name].append(tweet)

    return grouping

def cli_main():
    parser = ArgumentParser()
    parser.add_argument("username")
    parser.add_argument("--num-tweets", type=int, default=10)
    args = parser.parse_args()
    username = args.username

    user = twitter_utils.get_user_by_username(username)
    if not user:
        print(f"User not found: {username}")
        return

    filename = f"{username}_tweets.json"
    if os.path.exists(filename):
        print("Loading cached tweets.")
        with open(filename, 'r') as f:
            data = json.load(f)
        tweets = [Tweet.from_dict(e) for e in data]
    else:
        print("Query api for tweets.")
        tweets = twitter_utils.get_user_tweets(user, limit=args.num_tweets)
        with open(filename, 'w') as f:
            json.dump([t.to_dict() for t in tweets], f)


    grouped = group_tweets_by_entities(tweets)
    classifications = classify_tweets(grouped)
    topics = set()
    for classification in classifications.values():
        for cls in classification:
            for category in cls.categories:
                if category.confidence > 0.5:
                    topics.add(category.name)

    print(f"Username talks about:")
    for topic in sorted(list(topics)):
        print(topic)


if __name__ == "__main__":
    cli_main()
