"""
    This module contains exploritory code for interating
    with twitter's search API using the TwitterAPI
    python package.
"""

import os
from typing import List
from dotenv import load_dotenv
from TwitterAPI import TwitterAPI, TwitterRequestError

load_dotenv()
TWITTER_CONSUMER_KEY = os.getenv("TWITTER_CONSUMER_KEY")
TWITTER_CONSUMER_SECRET = os.getenv("TWITTER_CONSUMER_SECRET")

RAGE_LIMIT_HEADERS = {
    "ceiling": "x-rate-limit-limit",
    "remaining": "x-rate-limit-remaining",
    "time_till_reset": "x-rate-limit-reset"
}

API = TwitterAPI(TWITTER_CONSUMER_KEY,
                 TWITTER_CONSUMER_SECRET,
                 auth_type="oAuth2",
                 api_version="2")


class TwitterUser: #pylint: disable=too-few-public-methods
    """
        Twitter user data structure
    """

    def __init__(self, **kwargs):
        self.author_id = kwargs.get("id")
        self.name = kwargs.get("name")
        self.username = kwargs.get("username")
        self.url = kwargs.get("url")
        self.description = kwargs.get("description")


class Tweet: #pylint: disable=too-few-public-methods
    """
        Object that represents the data and fields.
    """

    def __init__(self, **kwargs):
        self.tweet_id = kwargs.get("id")
        self.author_id = kwargs.get("author_id")
        self.created_at = kwargs.get("created_at")
        self.text = kwargs.get("text", "")
        self._user = None


    @property
    def author(self) -> TwitterUser:
        """
            Return the author of the tweet.
        """

        if not self._user:
            author_data = get_user_by_id(self.author_id)
            self._user = TwitterUser(**author_data.json())

        return self._user

    @author.setter
    def author(self, value):
        if not isinstance(value, TwitterUser):
            raise TypeError("Invalide author type. Must be of type TwitterUser")

        self._user = value

    def __str__(self):
        return f"""
Tweet by: {self.author.username}
Created: {self.created_at}
Text: {self.text}
"""

    def __repr__(self):
        return f"<{self.__class__.__name__}: id={self.tweet_id}>"


def search(query):
    """
        Test that the twitter API is reachable from the configured credentials.
    """
    payload = {
        "query": query,
        "tweet.fields": "created_at,author_id",
        "expansions": "author_id",
        "user.fields": "description,url"
    }

    response = API.request("tweets/search/recent", payload)


    #TODO: Report/warn about rate-limiting
    if response.status_code != 200:
        raise TwitterRequestError(status_code=response.status_code,
                                  msg=response.text)

    payload = response.json()
    data = payload['data']
    users = [TwitterUser(**user) for user in payload['includes']['users']]
    users_by_author_id = {user.author_id: user for user in users}

    tweets = []
    for tweet_json in data:
        tweet = Tweet(**tweet_json)
        tweet.author = users_by_author_id[tweet.author_id]
        tweets.append(tweet)

    return tweets


def get_user_by_id(user_id):
    """
        Get a Twitter profile data by the user id.
    """
    return API.request(f"users/{user_id}")


def get_users_by_usernames(*usernames: List[str]):
    """
        Get information for a list of usernames.
    """

    query = {
        "usernames": ",".join(usernames),
        "user.fields": "location,url,entities"
    }

    return API.request("users/by", query)
