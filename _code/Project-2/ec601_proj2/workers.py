from re import I
from dotenv import load_dotenv
from dataclasses import dataclass
from datetime import datetime, timedelta
import os
import redis
import json
from time import sleep
from . import models
from . import twitter_utils

load_dotenv()

REDIS_CLIENT = None
REDIS_SERVER_HOST = os.getenv("REDIS_SERVER_HOST")
REDIS_SERVER_PORT = int(os.getenv("REDIS_SERVER_PORT"))
REDIS_SERVER_DB = int(os.getenv("REDIS_SERVER_DB"))

def get_redis_client():
    global REDIS_CLIENT

    if REDIS_CLIENT is None:
        REDIS_CLIENT = redis.Redis(REDIS_SERVER_HOST, port=REDIS_SERVER_PORT, db=REDIS_SERVER_DB)

    return REDIS_CLIENT


class RedisWorker:

    def __init__(self, redis_client: redis.Redis):
        self._client = redis_client


class Queues:
    """
        Namespace class for storing redis queue names. Queue names should
        follow the format: "<destination>:<description>" where <destination> is
        the output of the work should be stored (i.e. db:<descrition>) means
        the output should be stored in the database.
    """

    # This queue contains a SET of tweeets that should be stored in
    # the database. The tweets are required to have the author_id set
    # and the user should exist in the database.
    STORE_USER_TWEETS_KEY = "db:store_user_tweets"

    # Contains a list of twitter user ids to scrape tweets from.
    SCRAPE_USER_TWEETS_KEY = "worker:scrape_user_tweets"


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
        """
        while True:
            tweet = self._client.lpop(Queues.STORE_USER_TWEETS_KEY)
            if not tweet:
                break

            tweet = twitter_utils.Tweet(**json.loads(tweet))
            models.add_tweet(tweet)


    def queue_users_to_scrape(self):
        """
            A worker whose job is to poll the database for users that should
            be scraped. Users should not scraped more than once a week. When
            finished, this worker should put user IDs in a redis list.
        """
        last_week = datetime.now() - timedelta(days=7)
        query = models.User.select().where(
            (models.User.last_scraped == None) |
            (models.User.last_scraped <= last_week)
        )
        for user in query:
            self._client.sadd(Queues.SCRAPE_USER_TWEETS_KEY, user.id)


    def store_entities(self):
        pass


    def store_classifications(self):
        pass


    def process(self):
        self.store_scraped_tweets()
        self.queue_users_to_scrape()
        self.store_entities()
        self.store_classifications()


class ScrapeUserTweetsWorker(RedisWorker):
    """
        A worker whose job is to pull a user's tweets. After a user's
        tweets are scraped, this worker should queue the up for entity
        analysis. When a user
    """


class EntityAnalysisWorker(RedisWorker):
    """
        This worker is responsible for grouping entities in
        Tweets.
    """


class ClassifyUserTweets(RedisWorker):
    """
        This worker is responsible for taking
    """


################################################
# The dataclasses represent the payloads of the
# jobs in the queue.
@dataclass
class AnanlyzeTweetEntitiesRequest:
    pass

@dataclass
class AnanlyzeTweetEntitiesResult:
    pass
