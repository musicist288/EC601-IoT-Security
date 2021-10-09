"""
    Defines workers for scraping and analyzing twitter data.
"""
from collections import defaultdict

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import time
import logging

import dateparser
from playhouse.shortcuts import dict_to_model, model_to_dict
import redis

from . import models
from . import twitter_utils
from . import google_nlp
from . import LOGGER

TWITTER_RATE_LIMIT_EXPIRES_KEY = "twitter:rate_limit_up"
GOOGLE_RATE_LIMIT_EXPIRES_KEY = "google:rate_limit_up"

def _get_rate_limit_time(redis_client: redis.Redis, key: str):
    expires = redis_client.get(key)
    if not expires:
        return 0

    return float(expires.decode()) - time.time()

def get_google_rate_limit_expires(redis_client: redis.Redis):
    return _get_rate_limit_time(redis_client, GOOGLE_RATE_LIMIT_EXPIRES_KEY)

def set_google_rate_limit_expires(redis_client: redis.Redis, exp: float):
    redis_client.set(GOOGLE_RATE_LIMIT_EXPIRES_KEY, exp)


def get_twitter_rate_limt_expires(redis_client: redis.Redis):
    return _get_rate_limit_time(redis_client, TWITTER_RATE_LIMIT_EXPIRES_KEY)


def set_twitter_rate_limit_expires(redis_client: redis.Redis, exp: float):
    redis_client.set(TWITTER_RATE_LIMIT_EXPIRES_KEY, exp)



class Queues:
    """Namespace for redis queue names used by workers."""

    DB_TWEET_PROCESSING_PENDING = "db:tweet_processing_requested"
    DB_USER_PROCESSING_PENDING = "db:user_processing_requested"

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

    def _get_pending_tweets_query(self):
        pending_tweet_ids = self._client.smembers(Queues.DB_TWEET_PROCESSING_PENDING)
        return models.Tweet.select().where(models.Tweet.id << pending_tweet_ids)


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
                LOGGER.debug("No user tweets to store.")
                break

            tweet = ScrapeUserTweetsWorker.deserialize_result(data)
            LOGGER.debug("Storing tweet %s for user: %s", tweet.id, tweet.author_id)

            models.add_tweet(tweet)
            user = models.User.get_by_id(tweet.author_id)
            user.last_scraped = datetime.now().strftime(twitter_utils.DATE_FORMAT)
            user.save()
            self._client.srem(Queues.DB_USER_PROCESSING_PENDING, user.id)


    def queue_users_to_scrape(self):
        """
            Poll the database for users that should be scraped. Users should not
            scraped more than once a week. When finished, this worker should put
            user IDs in a redis list.
        """
        pending_user_ids = self._client.smembers(Queues.DB_USER_PROCESSING_PENDING)
        last_week = datetime.now() - timedelta(days=7)

        pending_query = models.User.select().where(models.User.id.in_(pending_user_ids))
        query = models.User.select().where(
            ((models.User.last_scraped.is_null()) |
             (models.User.last_scraped <= last_week)) &
             ~(models.User.id << pending_query)
        )
        for user in query: #pylint: disable=not-an-iterable
            LOGGER.debug("Queuing user to scrape %s",  user.id)
            data =  ScrapeUserTweetsWorker.serialize_request(user)
            self._client.sadd(Queues.SCRAPE_USER_TWEETS_REQUEST, data)
            self._client.sadd(Queues.DB_USER_PROCESSING_PENDING, user.id)


    def store_entity_analysis_results(self):
        while True:
            data = self._client.lpop(Queues.ENTITY_ANALYSIS_RESULTS)
            if not data:
                LOGGER.debug("No entity analysis results to store.")
                break

            result = EntityAnalysisWorker.deserialize_result(data)
            tweet = models.Tweet.get_by_id(result.tweet.id)
            LOGGER.debug("Storing entity analysis for tweet: %s", tweet.id)
            for entity in result.entities:
                ent_model, _ = models.Entity.get_or_create(name=entity.name,
                                                           type=entity.type_.value)
                models.TweetEntity.create(tweet=tweet, entity=ent_model)
            self._client.srem(Queues.DB_TWEET_PROCESSING_PENDING, tweet.id)
            tweet.analyzed = True
            tweet.save()


    def queue_entity_analysis_requests(self):
        tweets = models.Tweet.select().where(
            (models.Tweet.analyzed >> False)
        )
        for tweet in tweets: #pylint: disable=not-an-iterable
            if self._client.sismember(Queues.DB_TWEET_PROCESSING_PENDING, tweet.id):
                continue
            LOGGER.debug("Queue tweet for entity analysis: %s", tweet.id)
            request = EntityAnalysisWorker.serialize_request(tweet)
            self._client.rpush(Queues.ENTITY_ANALYSIS_REQUEST, request)
            self._client.sadd(Queues.DB_TWEET_PROCESSING_PENDING, tweet.id)


    def store_classification_results(self):
        while True:
            result = self._client.lpop(Queues.CLASSIFICATION_RESULTS)
            if not result:
                LOGGER.debug("No classification results to store.")
                break

            result = ClassificationResult.from_json(result)
            LOGGER.debug("Storing classification results for user: %s", result.user_id)
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

            ## Mark these tweets as classified so they don't get used
            ## again.
            for tweet in result.tweets:
                self._client.srem(Queues.DB_TWEET_PROCESSING_PENDING, tweet.id)
                t = models.Tweet.get_by_id(tweet.id)
                t.classified = True
                t.save()


    def queue_classification_requests(self):
        """
            Build the queue of twweets that should be classified to determine
            user's topics.
        """

        ## Grab all the tweets and their entities.
        pending_tweet_ids = {s.decode() for s in self._client.smembers(Queues.DB_TWEET_PROCESSING_PENDING)}
        query = models.Tweet.select().where(models.Tweet.classified >> False)

        tweets_by_user = defaultdict(list)
        for tweet in query: #pylint: disable=not-an-iterable
            tweets_by_user[tweet.user_id].append(tweet)

        mapping = defaultdict(list)
        for user_id, tweets in tweets_by_user.items():
            all_analyzed = all([t.analyzed for t in tweets])
            all_free = all([t.id not in pending_tweet_ids for t in tweets])

            if all_analyzed and all_free:
                for tweet in tweets:
                    for tweet_entity in tweet.tweet_entities:
                        key = (tweet.user_id, tweet_entity.entity.name)
                        mapping[key].append(tweet)

                    self._client.sadd(Queues.DB_TWEET_PROCESSING_PENDING, tweet.id)
            else:
                LOGGER.debug("Not querying user tweets. Outstanding opreations required.")

        for (user_id, _), tweets in mapping.items():
            LOGGER.debug("Queuing classification request for user: %s", user_id)
            request = ClassificationRequest(user_id=user_id, tweets=tweets)
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

    def __init__(self, *args, **kwargs):
        self.tweet_count_per_fetch = kwargs.pop("tweet_count", 10)
        super().__init__(*args, **kwargs)


    @classmethod
    def serialize_request(cls, user: models.User) -> str:
        return user.id


    @classmethod
    def deserialize_result(cls, data) -> twitter_utils.Tweet:
        return twitter_utils.Tweet(**json.loads(data))


    def scrape_user_tweets(self, user_id: str):
        if get_twitter_rate_limt_expires(self._client) > 0:
            ## Can't do anything waiting for the rate limit.
            LOGGER.debug("Not scraping user tweets. Waiting for rate limit to reset.")
            self._client.sadd(Queues.SCRAPE_USER_TWEETS_REQUEST, user_id)
            return

        ## Query to make sure user exists
        user = models.User.get_by_id(user_id)
        if not user:
            LOGGER.debug("Not scraping user. Does not exist: %s", user_id)
            return

        try:
            # TODO: Limit by last scraped date range.
            LOGGER.debug("Querying tweets for user.")
            tweets = twitter_utils.get_user_tweets(user.id, limit=self.tweet_count_per_fetch)
            for tweet in tweets:
                self._client.rpush(
                    Queues.SCRAPE_USER_TWEETS_RESULTS,
                    json.dumps(tweet.to_dict())
                )
        except twitter_utils.TwitterRateLimitError as err:
            set_twitter_rate_limit_expires(self._client, err.reset_epoch_seconds)
            self._client.sadd(Queues.SCRAPE_USER_TWEETS_REQUEST, user_id)
            LOGGER.debug("Rate limit hit.")
        except twitter_utils.TwitterRequestError as err:
            LOGGER.error("Received unknonw error from twitter (%s): %s ",
                         err.status_code, err.msg)


    def process(self):
        if get_twitter_rate_limt_expires(self._client) > 0:
            ## Can't do anything waiting for the rate limit.
            LOGGER.debug("Not scraping user tweets. Waiting for rate limit to reset.")
            return "wait"

        user_id = self._client.spop(Queues.SCRAPE_USER_TWEETS_REQUEST)
        if user_id:
            self.scrape_user_tweets(user_id.decode())
            return True
        else:
            return False


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
        try:
            response = google_nlp.LanguageClient.analyze_entities(tweet.text)
            return EntityAnalysisResult(tweet=tweet,
                                        entities=list(response.entities))
        except google_nlp.ResourceExhausted as err:
            LOGGER.warning("Hit google rate limit when analyzing tweets.")
            set_google_rate_limit_expires(self._client, time.time() + 60*15)
            return False


    def analyze_queue(self):
        # TODO: Rate limit checks
        tweet_req = self._client.lpop(Queues.ENTITY_ANALYSIS_REQUEST)
        if tweet_req:
            tweet = dict_to_model(models.Tweet, json.loads(tweet_req))
            LOGGER.debug("Analysing tweet: %s", tweet.id)
            result = self.analyze_tweet(tweet)
            if result is False:
                self._client.lpush(Queues.ENTITY_ANALYSIS_REQUEST, tweet_req)
                return "wait"
            else:
                self._client.lpush(Queues.ENTITY_ANALYSIS_RESULTS, result.to_json())
                return True
        else:
            return False


    def process(self):
        if get_google_rate_limit_expires(self._client) > 0:
            return "wait"

        return self.analyze_queue()


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
        req = self._client.lpop(Queues.CLASSIFICATION_REQUESTS)
        if not req:
            return False

        request = ClassificationRequest.from_json(req)

        LOGGER.debug("Classifying tweets from user: %s", request.user_id)
        tweet_text = " ".join([t.text for t in request.tweets])
        try:
            results = google_nlp.LanguageClient.classify_text(tweet_text)
            cr = ClassificationResult(user_id = request.user_id,
                                        categories=results.categories,
                                        tweets=request.tweets)
        except google_nlp.InvalidArgument as err:
            LOGGER.warning("Could not classify tweet text: %s", err)
            cr = ClassificationResult(user_id=request.user_id,
                                      categories=[],
                                      tweets=request.tweets)
        except google_nlp.ResourceExhausted as err:
            LOGGER.warning("Hit google rate limit when classifying tweets.")
            self._client.lpush(Queues.CLASSIFICATION_REQUESTS, req)
            set_google_rate_limit_expires(self._client, time.time() + 60*15)
            return False


        self._client.rpush(Queues.CLASSIFICATION_RESULTS, cr.to_json())
        return True


    def process(self):
        if get_google_rate_limit_expires(self._client) > 0:
            return "wait"

        return self.classify_user_tweets()
