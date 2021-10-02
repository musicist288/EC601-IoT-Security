from dataclasses import dataclass
from datetime import datetime, timedelta
import os
import json
from time import sleep

import dateparser
import redis
from dotenv import load_dotenv

from . import models
from . import twitter_utils
from . import google_nlp

load_dotenv()

REDIS_CLIENT = None
REDIS_SERVER_HOST = os.getenv("REDIS_SERVER_HOST")
REDIS_SERVER_PORT = int(os.getenv("REDIS_SERVER_PORT"))
REDIS_SERVER_DB = int(os.getenv("REDIS_SERVER_DB"))

def get_redis_client():
    global REDIS_CLIENT

    if REDIS_CLIENT is None:
        REDIS_CLIENT = redis.Redis(REDIS_SERVER_HOST,
                                  port=REDIS_SERVER_PORT,
                                  db=REDIS_SERVER_DB)

    return REDIS_CLIENT


class Queues:
    """Namespace for redis queue names used by workers."""

    # Contains user id strings
    SCRAPE_USER_TWEETS_KEY = "worker:scrape_user_tweets"

    # Contains JSON serialized twitter_utils.Tweet objects
    STORE_USER_TWEETS_KEY = "db:store_user_tweets"

    # Contains JSON serialized twitter_utils.Tweet objects
    ENTITY_ANALYSIS_REQUEST = "worker:analyze_tweet_entities"

    # Contains JSON serialized EntityAnalysisResult objects
    ENTITY_ANALYSIS_RESULTS = "db:store_entity_analysis_results"

    CLASSIFICATION_REQUESTS = "worker:classify_user_tweets"

    CLASSIFICATION_RESULTS = "db:store_classification_results"


@dataclass
class EntityAnalysisResult:
    tweet: twitter_utils.Tweet
    entities: list[google_nlp.Entity]

    def to_json(self):
        data = dict(tweet=self.tweet.to_dict(),
                    entities=[google_nlp.Entity.to_dict(e) for e in self.entities])

        return json.dumps(data)

    @classmethod
    def from_json(cls, data):
        data = json.loads(data)
        tweet = twitter_utils.Tweet.from_dict(data['tweet'])
        entities = [google_nlp.Entity.from_dict(e) for e in data['entities']]
        return cls(tweet=tweet, entities=entities)


@dataclass
class ClassificationRequest:
    tweets: list[models.Tweet]
    user: models.User


@dataclass
class ClassificationResult:
    user: models.User
    topics: list[str]


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
            data = self._client.lpop(Queues.STORE_USER_TWEETS_KEY)
            if not data:
                break

            tweet = ScrapeUserTweetsWorker.deserialze_result(data)

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
            (models.User.last_scraped == None) |
            (models.User.last_scraped <= last_week)
        )
        for user in query:
            data =  ScrapeUserTweetsWorker.serialize_request(user)
            self._client.sadd(Queues.SCRAPE_USER_TWEETS_KEY, data)


    def store_entity_anlysis_results(self):
        while True:
            data = self._client.lpop(Queues.ENTITY_ANALYSIS_RESULTS)
            if not data:
                break

            result = EntityAnalysisWorker.deserialize_result(data)
            tweet = models.Tweet.get_by_id(result.tweet.id)
            for entity in result.entities:
                ent_model, created = models.Entity.get_or_create(name=entity.name,
                                                                 type=entity.type_)
                models.TweetEntity.create(tweet=tweet, entity=entity)
            tweet.analyzed = True
            tweet.save()


    def queue_entity_analysis_requests(self):
        tweets = models.Twitter.select().where(models.Twitter.analyzed == False)
        for tweet in tweets:
            request = EntityAnalysisWorker.serialize_request(tweet)
            self._client.rpush(Queues.ENTITY_ANALYSIS_REQUEST, request)


    def store_classification_results(self):
        pass


    def queue_classification_requests(self):
        pass


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
    def serialize_request(self, user: models.User) -> str:
        return user.id


    @classmethod
    def deserialze_result(self, data) -> twitter_utils.Tweet:
        return twitter_utils.Tweet(**json.loads(data))


    def scrape_user_tweets(self, user_id: str):
        rate_limit = self._client.get(self.RATE_LIMIT_EXPIRES_KEY)
        if rate_limit is not None:
            rate_limit = dateparser.parse(rate_limit)

        if rate_limit > datetime.now():
            ## Can't do anything waiting for the rate limit.
            return

        user = models.User.get_by_id(user_id)
        try:
            # TODO: Limit by last scraped date range.
            tweets = twitter_utils.get_user_tweets(user_id)
            for tweet in tweets:
                self._client.rpush(
                    Queues.STORE_USER_TWEETS_KEY,
                    json.dumps(tweet.to_dict())
                )
        except twitter_utils.TwitterRequestError as err:
            if err.status_code == 429:
                pass # TODO: How to get rate limiting in here from header



class EntityAnalysisWorker(RedisWorker):
    """
        Peform entity analysis on tweets and stash the
        results for storage.
    """

    @classmethod
    def serialize_request(cls, tweet: twitter_utils.Tweet) -> str:
        pass


    @classmethod
    def deserialize_result(cls, data: str) -> EntityAnalysisResult:
        return EntityAnalysisResult.from_json(data)


    def analyze_tweet(self, tweet: twitter_utils.Tweet) -> EntityAnalysisResult:
        response = google_nlp.LanguageClient.analyze_entities(tweet.text)
        return EntityAnalysisResult(tweet=tweet,
                                    entities=list(response.entities))


    def analyze_queue(self):
        # TODO: Rate limit checks

        while True:
            tweet = self._client.lpop(Queues.ENTITY_ANALYSIS_REQUEST)
            if not tweet:
                break
            else:
                tweet = twitter_utils.Tweet.from_dict(json.loads(tweet))
                result = self.analyze_tweet(tweet)
                self._client.lpush(Queues.ENTITY_ANALYSIS_RESULTS, result.to_json())


    def process(self):
        self.analyze_queue()


class ClassificationWorker(RedisWorker):
    """
        Service classification jobs and stash results
        for persistance
    """
