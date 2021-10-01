import os
import unittest
import random
import subprocess
import shutil
import json
import uuid
from pathlib import Path

from datetime import datetime, timedelta
import redis
import peewee

from ec601_proj2 import (
    workers,
    models,
    twitter_utils
)

MODELS = models.TABLES
DB_FILENAME = "test.db"
DATABASE = peewee.SqliteDatabase(DB_FILENAME)

def random_date(start, end):
    """
    This function will return a random datetime between two datetime
    objects.
    """
    delta = end - start
    int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
    random_second = random.randrange(int_delta)
    return start + timedelta(seconds=random_second)

class RedisServerHelper:

    base_path = Path(__file__).absolute().parent / "redis"
    template_file = Path(__file__).absolute().parent / "redis_template.conf"

    # In basepath
    config_path =  Path(__file__).absolute().parent / "redis" / "redis.conf"

    _proc = None

    @classmethod
    def start(cls):
        if cls._proc is not None:
            return

        cls.base_path.mkdir(exist_ok=True)
        with cls.template_file.open("r") as f:
            data = f.read()
            data = data.replace("{basepath}", str(cls.base_path))

        with cls.config_path.open("w") as f:
            f.write(data)

        cls._proc = subprocess.Popen([
            shutil.which("redis-server"),
            cls.config_path
        ])

    @classmethod
    def stop(cls):
        if cls._proc is None:
            return

        if cls._proc.poll() is None:
            # Process is still alive
            cls._proc.kill()
        else:
            cls._proc.communicate()

        cls._proc = None
        shutil.rmtree(cls.base_path)



class DatabaseWorker(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        RedisServerHelper.start()
        cls.redis_client = redis.Redis(host="127.0.0.1", port=6379, db=0)
        return super().setUpClass()


    @classmethod
    def tearDownClass(cls) -> None:
        RedisServerHelper.stop()
        return super().tearDownClass()


    def setUp(self):
        DATABASE.bind(MODELS, bind_refs=False, bind_backrefs=False)
        DATABASE.connect()
        DATABASE.create_tables(MODELS)
        self.worker = workers.DatabaseWorker(self.redis_client)


    def tearDown(self):
        DATABASE.drop_tables(MODELS)
        DATABASE.close()
        os.unlink(DB_FILENAME)


    def _populate_users(self, num_users):
        for worker_id in range(num_users):
            user = models.User.create(
                id=str(worker_id),
                name="Rand",
                username="Notrand",
                url="https://google.com",
                description="",
                verified = False,
            )
            user.save()

    def _populate_queue_with_user_tweets(self, user_id, num_tweets):
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()

        for i in range(num_tweets):
            tweet_id = str(uuid.uuid4())
            tweet = twitter_utils.Tweet(
                id=tweet_id,
                author_id=user_id,
                created_at=random_date(start_date, end_date).strftime(twitter_utils.DATE_FORMAT),
                text=f"This is tweet {tweet_id} from user {user_id}"
            )

            self.redis_client.rpush(
                workers.Queues.STORE_USER_TWEETS_KEY,
                json.dumps(tweet.to_dict())
            )

    def test_queue_scrape_new_user(self):
        self._populate_users(10)
        self.worker.queue_users_to_scrape()
        for i in range(10):
            self.assertTrue(
                self.redis_client.sismember(
                    workers.Queues.SCRAPE_USER_TWEETS_KEY,
                    str(i)
                )
            )

    def test_queue_rescrape_user(self):
        self._populate_users(1)
        user = models.User.get(models.User.id == "0")
        user.last_scraped = datetime.now()
        user.save()

        self.worker.queue_users_to_scrape()
        self.assertEqual(
            self.redis_client.scard(workers.Queues.SCRAPE_USER_TWEETS_KEY),
            0
        )

        user.last_scraped = datetime.now() - timedelta(days=3)
        self.worker.queue_users_to_scrape()
        self.assertEqual(
            self.redis_client.scard(workers.Queues.SCRAPE_USER_TWEETS_KEY),
            0
        )

        user.last_scraped = datetime.now() - timedelta(days=7)
        user.save()
        self.worker.queue_users_to_scrape()
        self.assertTrue(
            self.redis_client.sismember(
                workers.Queues.SCRAPE_USER_TWEETS_KEY,
                user.id
            )
        )


    def test_store_scraped_tweets(self):
        self._populate_users(10)
        user_id_tweet_count = {}
        for i in range(10):
            user_id = str(i)
            num = random.randrange(1, 10)
            self._populate_queue_with_user_tweets(user_id, num)
            user_id_tweet_count[user_id] = num

        self.worker.store_scraped_tweets()

        for i in range(10):
            user_id = str(i)
            query = models.Tweet.select().where(models.Tweet.user_id == user_id)
            self.assertEqual(query.count(), user_id_tweet_count[user_id])
