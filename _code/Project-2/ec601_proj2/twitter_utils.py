"""
    This module contains exploritory code for interating
    with twitter's search API using the TwitterAPI
    python package.
"""

import os
from datetime import datetime, timedelta
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


def _add_payload_dates(payload, start_date, end_date):
    """
        Will modify the twitter payload to include start_time
        and end_time criteria base on the values of start_date and
        end_date
    """
    if start_date and end_date and (start_date > end_date):
        raise ValueError("Start date must be before end date.")

    now = datetime.now()
    max_delta = timedelta(days=7)
    start_too_early = start_date and ((now - start_date) > max_delta)
    end_too_early = end_date and ((now - end_date) > max_delta)

    if start_too_early or end_too_early:
        raise ValueError("Twitter API can only search for the past 7 days.")

    if start_date:
        payload['start_time'] = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")

    if end_date:
        payload['end_time'] = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")



def search(query, start_date=None, end_date=None, max_results=10):
    """
        Test that the twitter API is reachable from the configured credentials.
    """
    if max_results > 20:
        raise ValueError("max_results hard capped to 10 so we don't hit the "
                         "search limit for the month.")

    payload = {
        "query": query,
        "tweet.fields": "created_at,author_id",
        "expansions": "author_id",
        "user.fields": "description,url",
        "max_results": max_results
    }

    _add_payload_dates(payload, start_date, end_date)
    response = API.request("tweets/search/recent", payload)

    # TODO Report/warn about rate-limiting
    if response.status_code != 200:
        raise TwitterRequestError(status_code=response.status_code,
                                  msg=response.text)

    payload = response.json()
    count = payload['meta']['result_count']
    tweets = []

    if count > 0:
        data = payload['data']
        users = [TwitterUser(**user) for user in payload['includes']['users']]
        users_by_author_id = {user.author_id: user for user in users}

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
