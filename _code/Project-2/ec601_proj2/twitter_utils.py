"""
    This module contains exploritory code for interating
    with twitter's search API using the TwitterAPI
    python package.
"""

#pylint: disable=unused-import,missing-class-docstring,missing-function-docstring
#pylint: disable=too-few-public-methods

import os
from typing import Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

import dateparser
from dotenv import load_dotenv
from TwitterAPI import TwitterAPI, TwitterRequestError
from requests.models import Response

load_dotenv()
TWITTER_CONSUMER_KEY = os.getenv("TWITTER_CONSUMER_KEY")
TWITTER_CONSUMER_SECRET = os.getenv("TWITTER_CONSUMER_SECRET")
TWITTER_ACCESS_KEY = os.getenv("TWITTER_ACCESS_KEY")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")
COUNT_GRANULARITIES = ("minute", "hour", "day")

RAGE_LIMIT_HEADERS = {
    "ceiling": "x-rate-limit-limit",
    "remaining": "x-rate-limit-remaining",
    "time_till_reset": "x-rate-limit-reset"
}

DATE_FORMAT = "%Y-%m-%dT%H:%M:SZ"

V2_API = TwitterAPI(TWITTER_CONSUMER_KEY,
                    TWITTER_CONSUMER_SECRET,
                    TWITTER_ACCESS_KEY,
                    TWITTER_ACCESS_SECRET,
                    api_version="2")

# Not all the old APIs have a V2 equivalent. (yet?)
# This API is used for retrieving the home_timeline
# for a user.
V11_API = TwitterAPI(TWITTER_CONSUMER_KEY,
                     TWITTER_CONSUMER_SECRET,
                     TWITTER_ACCESS_KEY,
                     TWITTER_ACCESS_SECRET)

class TweetCount:

    def __init__(self, query, **kwargs):
        self.query = query
        self.start_time = dateparser.parse(kwargs.get("start"))
        self.end_time = dateparser.parse(kwargs.get("end"))
        self.count = kwargs["tweet_count"]

class TwitterUser: #pylint: disable=too-few-public-methods
    """
        Twitter user data structure
    """

    def __init__(self, **kwargs):
        self.id = kwargs.get("id")
        self.name = kwargs.get("name")
        self.username = kwargs.get("username")
        self.url = kwargs.get("url")
        self.description = kwargs.get("description")
        self.verified = kwargs.get("verified")


    def __hash__(self):
        return hash((self.id, self.username))


    def __eq__(self, other):
        return self.id == other.id


    def to_dict(self):
        fields = 'id', 'name', 'username', 'url', 'description', 'verified'
        return {f: getattr(self, f) for f in fields}

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


class Tweet: #pylint: disable=too-few-public-methods
    """
        Object that represents the data and fields.
    """

    def __init__(self, **kwargs):
        self.id = kwargs.get("id")
        self.author_id = kwargs.get("author_id")
        self.created_at = kwargs.get("created_at")
        self.text = kwargs.get("text", "")


    def __str__(self):
        return f"""
Created: {self.created_at}
Text: {self.text}
"""

    def __repr__(self):
        return f"<{self.__class__.__name__}: id={self.id}>"

    def to_dict(self):
        fields = (
            ("id", "id"),
            ("author_id", "author_id"),
            ("created_at", "created_at"),
            ("text", "text")
        )
        return {field[1]: getattr(self, field[0]) for field in fields}

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


class ResponseMetadata:
    next_token: str
    previous_token: str
    result_count: int
    newest_id: str
    oldest_id: str

    def __init__(self, **kwargs):
        for arg, value in kwargs.items():
            setattr(self, arg, value)


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
    MAX_LIMIT = 20
    if max_results > MAX_LIMIT:
        raise ValueError(f"max_results hard capped to {MAX_LIMIT} so we don't hit the "
                         "search limit for the month.")

    payload = {
        "query": query,
        "tweet.fields": "created_at,author_id",
        "expansions": "author_id",
        "user.fields": "description,url",
        "max_results": max_results
    }

    _add_payload_dates(payload, start_date, end_date)
    response = V2_API.request("tweets/search/recent", payload)

    # TODO Report/warn about rate-limiting
    if response.status_code != 200:
        raise TwitterRequestError(status_code=response.status_code,
                                  msg=response.text)

    payload = response.json()
    count = payload['meta']['result_count']
    tweets = []

    if count > 0:
        data = payload['data']
        for tweet_json in data:
            tweet = Tweet(**tweet_json)
            tweets.append(tweet)

    return tweets


def counts(query, granularity="hour", start_time=None, end_time=None) -> list[TweetCount]:
    if granularity not in COUNT_GRANULARITIES:
        raise ValueError(f"Invalid granularity. Must be one of: {', '.join(COUNT_GRANULARITIES)}")

    payload = {
        "query": query,
        "granularity": granularity
    }

    _add_payload_dates(payload, start_time, end_time)
    response = V2_API.request("tweets/counts/recent", payload)

    # TODO Report/warn about rate-limiting
    if response.status_code != 200:
        raise TwitterRequestError(status_code=response.status_code,
                                  msg=response.text)

    payload = response.json()
    return [TweetCount(query, **count) for count in payload['data']]


def home_timeline(count=5) -> list[Tweet]:
    params = { "count": count }

    resp = V11_API.request("statuses/home_timeline", params)
    if resp.status_code != 200:
        raise TwitterRequestError(status_code=resp.status_code, msg=resp.text)

    data = resp.json()
    tweets = []
    for entry in data:
        tweet = Tweet(
            author_id=entry['user']['id_str'],
            id=entry['id_str'],
            created_at=entry['created_at'],
            text=entry['text']
        )
        tweets.append(tweet)

    return tweets


def get_user_by_id(user_id):
    """
        Get a Twitter profile data by the user id.
    """
    return V2_API.request(f"users/{user_id}")


def _check_response(response):
    if response.status_code != 200:
        raise TwitterRequestError(status_code=response.status_code,
                                  msg=response.text)

    return response


def _user_list_result(endpoint, pagination) -> Tuple[ResponseMetadata, list[TwitterUser]]:
    params = {
        "user.fields": "verified,description"
    }

    response = _check_response(V2_API.request(endpoint, params=params))

    json = response.json()
    metadata = ResponseMetadata(**json['meta'])
    count = metadata.result_count

    if count == 0:
        return []

    data = json['data']
    return metadata, [TwitterUser(**user) for user in data]


def _tweets_list_result(endpoint, limit):
    params = {
        "max_results": limit
    }
    response = _check_response(V2_API.request(endpoint, params=params))
    json = response.json()
    metadata = ResponseMetadata(**json['meta'])
    return metadata, [Tweet(**tweet) for tweet in json['data']]


def get_user_by_username(username) -> TwitterUser:
    """
        Get information for a list of usernames.
    """

    response = _check_response(V2_API.request(f"users/by/username/:{username}"))
    json = response.json()
    if not json.get('data'):
        return None

    return TwitterUser(**json['data'])


def get_following(user_id: str, pagination=None):
    return _user_list_result(f"users/:{user_id}/following", pagination)


def get_followers(user_id: str, pagination=None):
    return _user_list_result(f"users/:{user_id}/followers", pagination)


def get_blocking(user_id: str, pagination=None):
    return _user_list_result(f"users/:{user_id}/blocking", pagination)


def get_muting(user_id: str, pagination=None):
    return _user_list_result(f"users/:{user_id}/muting", pagination)

def get_user_tweets(user_id: str, limit=10):
    _, tweets = _tweets_list_result(f"users/:{user_id}/tweets", limit)
    return tweets
