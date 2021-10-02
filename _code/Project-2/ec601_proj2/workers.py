"""
    Defines workers for scraping and analyzing twitter data.
"""
from collections import defaultdict

from dataclasses import dataclass
from datetime import datetime, timedelta
import os
import json
import logging

import dateparser
from dotenv import load_dotenv
from playhouse.shortcuts import dict_to_model, model_to_dict
import redis

from . import models
from . import twitter_utils
from . import google_nlp

load_dotenv()

REDIS_SERVER_HOST = os.getenv("REDIS_SERVER_HOST")
REDIS_SERVER_PORT = int(os.getenv("REDIS_SERVER_PORT"))
REDIS_SERVER_DB = int(os.getenv("REDIS_SERVER_DB"))

def get_redis_client():
    return redis.Redis(REDIS_SERVER_HOST,
                       port=REDIS_SERVER_PORT,
                       db=REDIS_SERVER_DB)


class Queues:
    """Namespace for redis queue names used by workers."""

    # Contains user id strings
    SCRAPE_USER_TWEETS_REQUEST = "worker:scrape_user_tweets"

    # Contains JSON serialized twitter_utils.Tweet objects
    SCRAPE_USER_TWEETS_RESULTS = "db:store_user_tweets"

    # Contains JSON serialized twitter_utils.Tweet objects
    ENTITY_ANALYSIS_REQUEST = "worker:analyze_tweet_entities"

    # Contains JSON serialized EntityAnalysisResult objects
    ENTITY_ANALYSIS_RESULTS = "db:store_entity_analysis_results"

    CLASSIFICATION_REQUESTS = "worker:classify_user_tweets"

    CLASSIFICATION_RESULTS = "db:store_classification_results"


@dataclass
class EntityAnalysisResult:
    tweet: models.Tweet
    entities: list[google_nlp.Entity]

    def to_json(self):
        data = dict(tweet=model_to_dict(self.tweet, backrefs=True),
                    entities=[google_nlp.Entity.to_dict(e) for e in self.entities])

        return json.dumps(data)

    @classmethod
    def from_json(cls, data: str):
        data = json.loads(data)
        tweet = dict_to_model(models.Tweet, data['tweet'])
        entities = [google_nlp.Entity(**e) for e in data['entities']]
        return cls(tweet=tweet, entities=entities)


@dataclass
class ClassificationRequest:
    user_id: str
    tweets: list[models.Tweet]

    def to_json(self):
        data = dict(user_id=self.user_id,
                    tweets=[model_to_dict(t) for t in self.tweets])
        return json.dumps(data)

    @classmethod
    def from_json(cls, data):
        data = json.loads(data)
        tweets = [dict_to_model(models.Tweet, t) for t in data['tweets']]
        user_id = data['user_id']
        return cls(user_id=user_id, tweets=tweets)


@dataclass
class ClassificationResult:
    user_id: str
    categories: list[google_nlp.ClassificationCategory]
    tweets: list[models.Tweet]

    def to_json(self):
        cats = [google_nlp.ClassificationCategory.to_dict(c) for c in self.categories]
        return json.dumps(dict(user_id=self.user_id,
                               categories=cats,
                               tweets=[model_to_dict(t) for t in self.tweets]))

    @classmethod
    def from_json(cls, data: str):
        data = json.loads(data)
        cats = [google_nlp.ClassificationCategory(**c) for c in data['categories']]
        tweets = [dict_to_model(models.Tweet, t) for t in data['tweets']]
        return cls(user_id=data['user_id'], categories=cats, tweets=tweets)


class RedisWorker:

    def __init__(self, redis_client: redis.Redis):
        self._client = redis_client


class DatabaseWorker(RedisWorker):
    """
        To avoid threading/race contention isuses, this single
        worker will handle all of the database operations that the
        other workers use queues to manage.
    """

    def store_scraped_tweets(self):
        """
            Store scraped user tweets in the database.

            This should be done BEFORE getting new users to scrape as this
            will mark the last_scraped time for each user.

            After this is finished the last scraped time for the user should
            be updated.
        """
        while True:
            data = self._client.lpop(Queues.SCRAPE_USER_TWEETS_RESULTS)
            if not data:
                break

            tweet = ScrapeUserTweetsWorker.deserialize_result(data)

            models.add_tweet(tweet)
            user = models.User.get_by_id(tweet.author_id)
            user.last_scraped = datetime.now().strftime(twitter_utils.DATE_FORMAT)
            user.save()


    def queue_users_to_scrape(self):
        """
            Poll the database for users that should be scraped. Users should not
            scraped more than once a week. When finished, this worker should put
            user IDs in a redis list.
        """
        last_week = datetime.now() - timedelta(days=7)
        query = models.User.select().where(
            (models.User.last_scraped.is_null()) |
            (models.User.last_scraped <= last_week)
        )
        for user in query: #pylint: disable=not-an-iterable
            data =  ScrapeUserTweetsWorker.serialize_request(user)
            self._client.sadd(Queues.SCRAPE_USER_TWEETS_REQUEST, data)


    def store_entity_analysis_results(self):
        while True:
            data = self._client.lpop(Queues.ENTITY_ANALYSIS_RESULTS)
            if not data:
                break

            result = EntityAnalysisWorker.deserialize_result(data)
            tweet = models.Tweet.get_by_id(result.tweet.id)
            for entity in result.entities:
                ent_model, _ = models.Entity.get_or_create(name=entity.name,
                                                           type=entity.type_.value)
                models.TweetEntity.create(tweet=tweet, entity=ent_model)
            tweet.analyzed = True
            tweet.save()


    def queue_entity_analysis_requests(self):
        tweets = models.Tweet.select().where(models.Tweet.analyzed >> False)
        for tweet in tweets: #pylint: disable=not-an-iterable
            request = EntityAnalysisWorker.serialize_request(tweet)
            self._client.rpush(Queues.ENTITY_ANALYSIS_REQUEST, request)


    def store_classification_results(self):
        while True:
            result = self._client.lpop(Queues.CLASSIFICATION_RESULTS)
            if not result:
                break

            result = ClassificationResult.from_json(result)
            user_model = models.User.get_by_id(result.user_id)
            if result.categories:
                for cat in result.categories:
                    topic_model, created = models.Topic.get_or_create(name=cat.name)
                    ut, created = models.UserTopic.get_or_create(user=user_model,
                                                                 topic=topic_model)
                    if not created:
                        # We've detected this user's topic before,
                        # increment the count
                        ut.tweet_count += len(result.tweets)
                    else:
                        ut.tweet_count = len(result.tweets)

                    ut.save()

                    ## If a topic was found for these tweets,
                    ## mark them as having been part of a classification
                    for tweet in result.tweets:
                        t = models.Tweet.get_by_id(tweet.id)
                        t.classified = True
                        t.save()


    def queue_classification_requests(self):
        """
            Build the queue of twweets that should be classified to determine
            user's topics.
        """

        ## Grab all the tweets and their entities.
        query = models.Tweet.select().where(
            (models.Tweet.analyzed >> True) &
            (models.Tweet.classified >> False)
        )

        mapping = defaultdict(list)

        for tweet in query: #pylint: disable=not-an-iterable
            for tweet_entity in tweet.tweet_entities:
                key = (tweet.user_id, tweet_entity.entity.name)
                mapping[key].append(tweet)

        for (user_id, _), tweets in mapping.items():
            request = ClassificationRequest(user_id =user_id, tweets=tweets)
            self._client.rpush(Queues.CLASSIFICATION_REQUESTS,
                               ClassificationWorker.serialize_request(request))

    def process(self):
        self.store_scraped_tweets()
        self.store_entity_analysis_results()
        self.store_classification_results()

        self.queue_users_to_scrape()
        self.queue_entity_analysis_requests()
        self.queue_classification_requests()


class ScrapeUserTweetsWorker(RedisWorker):
    """
        A worker whose job is to pull a user's tweets. After a user's tweets are
        scraped, this worker should queue the up for entity analysis.
    """

    RATE_LIMIT_EXPIRES_KEY = "twitter:rate_limit_up"

    @classmethod
    def serialize_request(cls, user: models.User) -> str:
        return user.id


    @classmethod
    def deserialize_result(cls, data) -> twitter_utils.Tweet:
        return twitter_utils.Tweet(**json.loads(data))


    def scrape_user_tweets(self, user_id: str):
        rate_limit = self._client.get(self.RATE_LIMIT_EXPIRES_KEY)
        if rate_limit is not None:
            if dateparser.parse(rate_limit) > datetime.now():
                ## Can't do anything waiting for the rate limit.
                return

        ## Query to make sure user exists
        user = models.User.get_by_id(user_id)
        if not user:
            logging.debug("Not scraping user. Does not exist: %s", user_id)

        try:
            # TODO: Limit by last scraped date range.
            tweets = twitter_utils.get_user_tweets(user.id)
            for tweet in tweets:
                self._client.rpush(
                    Queues.SCRAPE_USER_TWEETS_RESULTS,
                    json.dumps(tweet.to_dict())
                )
        except twitter_utils.TwitterRequestError as err:
            if err.status_code == 429:
                pass # TODO: How to get rate limiting in here from header


    def process(self):
        user_id = self._client.spop(Queues.SCRAPE_USER_TWEETS_REQUEST)
        if user_id:
            self.scrape_user_tweets(user_id.decode())


class EntityAnalysisWorker(RedisWorker):
    """
        Peform entity analysis on tweets and stash the
        results for storage.
    """

    @classmethod
    def serialize_request(cls, tweet: models.Tweet) -> str:
        return json.dumps(model_to_dict(tweet))


    @classmethod
    def deserialize_request(cls, data: str) -> models.Tweet:
        return dict_to_model(models.Tweet, json.loads(data))


    @classmethod
    def deserialize_result(cls, data: str) -> EntityAnalysisResult:
        return EntityAnalysisResult.from_json(data)


    def analyze_tweet(self, tweet: models.Tweet) -> EntityAnalysisResult:
        response = google_nlp.LanguageClient.analyze_entities(tweet.text)
        return EntityAnalysisResult(tweet=tweet,
                                    entities=list(response.entities))


    def analyze_queue(self):
        # TODO: Rate limit checks
        tweet = self._client.lpop(Queues.ENTITY_ANALYSIS_REQUEST)
        if tweet:
            tweet = dict_to_model(models.Tweet, json.loads(tweet))
            result = self.analyze_tweet(tweet)
            self._client.lpush(Queues.ENTITY_ANALYSIS_RESULTS, result.to_json())


    def process(self):
        self.analyze_queue()


class ClassificationWorker(RedisWorker):
    """
        Service classification jobs and stash results
        for persistance
    """

    @classmethod
    def serialize_request(cls, request: ClassificationRequest):
        return request.to_json()


    @classmethod
    def deserialize_result(cls, data: str):
        return ClassificationResult.from_json(data)


    def classify_user_tweets(self):
        request = self._client.lpop(Queues.CLASSIFICATION_REQUESTS)
        if not request:
            return

        request = ClassificationRequest.from_json(request)

        tweet_text = " ".join([t.text for t in request.tweets])
        results = google_nlp.LanguageClient.classify_text(tweet_text)
        if len(results.categories) > 0:
            cr = ClassificationResult(user_id = request.user_id,
                                      categories=results.categories,
                                      tweets=request.tweets)
            self._client.rpush(Queues.CLASSIFICATION_RESULTS, cr.to_json())


    def process(self):
        self.classify_user_tweets()
