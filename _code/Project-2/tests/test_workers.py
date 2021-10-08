from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import random
import subprocess
import shutil
import time
import unittest
from unittest import mock
import uuid
from playhouse.shortcuts import model_to_dict

import redis

from ec601_proj2 import (
    workers,
    models,
    twitter_utils,
    google_nlp
)

DB_FILENAME = "test.db"

def random_date(start: datetime, end: datetime) -> datetime:
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

        if cls.base_path.exists():
            shutil.rmtree(cls.base_path)

        cls.base_path.mkdir()
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


class DatabaseTestCase(unittest.TestCase):

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
        if os.path.exists(DB_FILENAME):
            os.unlink(DB_FILENAME)

        self.database = models.init_db(DB_FILENAME)
        self.worker = workers.DatabaseWorker(self.redis_client)


    def tearDown(self):
        self.database.drop_tables(models.TABLES)
        self.database.close()
        self.redis_client.flushdb()
        os.unlink(DB_FILENAME)


    def _populate_users(self, num_users):
        for user_id in range(num_users):
            user = models.User.create(
                id=str(user_id),
                name="Rand",
                username="User %d" % user_id,
                url="https://google.com",
                description="",
                verified = False,
            )
            user.save()


    def _generate_user_tweets(self, user_id, num_tweets) -> twitter_utils.Tweet:
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()

        for i in range(num_tweets):
            tweet_id = str(uuid.uuid4())
            tweet = twitter_utils.Tweet(
                id=tweet_id,
                author_id=user_id,
                created_at=random_date(start_date, end_date).strftime(
                    twitter_utils.DATE_FORMAT),
                text=f"This is tweet {tweet_id} from user {user_id}"
            )

            yield tweet


    def _populate_queue_with_user_tweets(self, user_id, num_tweets):
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()
        for tweet in self._generate_user_tweets(user_id, num_tweets):
            self.redis_client.rpush(
                workers.Queues.SCRAPE_USER_TWEETS_RESULTS,
                json.dumps(tweet.to_dict())
            )


    def _populate_db_with_user_tweets(self, user_id, num_tweets):
        for tweet in self._generate_user_tweets(user_id, num_tweets):
            models.add_tweet(tweet)


    def _generate_dummy_entities(self, num_entities):
        for i in range(num_entities):
            yield google_nlp.Entity(**{
                "name": "Dummy Entity %s" % i,
                "type_": 0,
                "metadata": {},
                "salience": 0.13003,
                "mentions": [],
                "sentiment": {"magnitude": 2, "score": 0.33493}
            })


    def _populate_database_with_entities(self, num_entities):
        for entity in self._generate_dummy_entities(num_entities):
            models.Entity.create(name=entity.name, type=entity.type_)


class TestDatabaseWorker(DatabaseTestCase):

    def setUp(self):
        super().setUp()
        self.worker = workers.DatabaseWorker(self.redis_client)


    def test_queue_scrape_new_user(self):
        self._populate_users(10)
        self.worker.queue_users_to_scrape()
        for i in range(10):
            self.assertTrue(
                self.redis_client.sismember(
                    workers.Queues.SCRAPE_USER_TWEETS_REQUEST,
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
            self.redis_client.scard(workers.Queues.SCRAPE_USER_TWEETS_REQUEST),
            0
        )

        user.last_scraped = datetime.now() - timedelta(days=3)
        self.worker.queue_users_to_scrape()
        self.assertEqual(
            self.redis_client.scard(workers.Queues.SCRAPE_USER_TWEETS_REQUEST),
            0
        )

        user.last_scraped = datetime.now() - timedelta(days=7)
        user.save()
        self.worker.queue_users_to_scrape()
        self.assertTrue(
            self.redis_client.sismember(
                workers.Queues.SCRAPE_USER_TWEETS_REQUEST,
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
            user = models.User.get_by_id(user_id)
            self.assertIsNotNone(user.last_scraped)


    def test_queue_entity_analysis_requests(self):
        self._populate_users(1)
        self._populate_db_with_user_tweets("0", 1)

        self.worker.queue_entity_analysis_requests()

        request = self.redis_client.lpop(workers.Queues.ENTITY_ANALYSIS_REQUEST)
        model = workers.EntityAnalysisWorker.deserialize_request(request)
        self.assertEqual(model.user_id, "0")


        # That should be the only request.
        request = self.redis_client.lpop(workers.Queues.ENTITY_ANALYSIS_REQUEST)
        self.assertIsNone(request)


    def test_queue_entity_pending_only(self):
        self._populate_users(1)
        self._populate_db_with_user_tweets("0", 1)

        # Make sure we don't queue the same thing twice.
        self.worker.queue_entity_analysis_requests()
        self.worker.queue_entity_analysis_requests()

        request = self.redis_client.lpop(workers.Queues.ENTITY_ANALYSIS_REQUEST)
        self.assertIsNotNone(request)

        request = self.redis_client.lpop(workers.Queues.ENTITY_ANALYSIS_REQUEST)
        self.assertIsNone(request)



    def test_store_entity_analysis_result(self):
        self._populate_users(1)
        self._populate_db_with_user_tweets("0", 1)

        tweet = models.Tweet.select()[0]
        entity = google_nlp.Entity(**{
            "name": "Dummy Entity",
            "type_": 0,
            "metadata": {},
            "salience": 0.13003,
            "mentions": [],
            "sentiment": {"magnitude": 2, "score": 0.33493}
        })

        result = workers.EntityAnalysisResult(tweet=tweet, entities=[entity])
        self.redis_client.lpush(
            workers.Queues.ENTITY_ANALYSIS_RESULTS,
            result.to_json()
        )

        self.worker.store_entity_analysis_results()

        query = models.Entity.select().where(models.Entity.name == entity.name)
        self.assertEqual(query.count(), 1)
        ent = query[0]
        self.assertEqual(ent.type, entity.type_)


    def test_queue_classification_request(self):
        self._populate_users(1)
        self._populate_db_with_user_tweets("0", 10)
        self._populate_database_with_entities(2)

        entities = list(models.Entity.select())
        tweets = list(models.Tweet.select())
        for i, tweet in enumerate(tweets):
            if i >= 5:
                entity = entities[1]
            else:
                entity = entities[0]
            tweet.analyzed = True
            tweet.save()

            models.TweetEntity.create(tweet=tweet, entity=entity)

        self.worker.queue_classification_requests()

        req1 = self.redis_client.lpop(workers.Queues.CLASSIFICATION_REQUESTS)
        self.assertIsNotNone(req1)
        req1 = workers.ClassificationRequest.from_json(req1)
        self.assertEqual(req1.user_id, "0")
        expected_tweet_ids = {t.id for t in tweets[:5]}
        request_tweet_ids = {t.id for t in req1.tweets}
        self.assertEqual(request_tweet_ids, expected_tweet_ids)

        req2 = self.redis_client.lpop(workers.Queues.CLASSIFICATION_REQUESTS)
        self.assertIsNotNone(req2)
        req2 = workers.ClassificationRequest.from_json(req2)
        self.assertEqual(req2.user_id, "0")
        expected_tweet_ids = {t.id for t in tweets[5:]}
        request_tweet_ids = {t.id for t in req2.tweets}
        self.assertEqual(request_tweet_ids, expected_tweet_ids)

    def test_queue_classification_request(self):
        self._populate_users(1)
        self._populate_db_with_user_tweets("0", 10)
        self._populate_database_with_entities(1)

        entities = list(models.Entity.select())
        tweets = list(models.Tweet.select())
        for i, tweet in enumerate(tweets):
            entity = entities[0]
            tweet.analyzed = True
            tweet.save()
            models.TweetEntity.create(tweet=tweet, entity=entity)

        self.worker.queue_classification_requests()
        self.worker.queue_classification_requests()
        request = self.redis_client.lpop(workers.Queues.CLASSIFICATION_REQUESTS)
        self.assertIsNotNone(request)

        request = self.redis_client.lpop(workers.Queues.CLASSIFICATION_REQUESTS)
        self.assertIsNone(request)


    def test_store_classification_result(self):
        self._populate_users(1)
        self._populate_db_with_user_tweets("0", 10)
        tweets = list(models.Tweet.select())

        categories = [
            google_nlp.ClassificationCategory(name="Cat 1", confidence=0.5),
            google_nlp.ClassificationCategory(name="Cat 2", confidence=0.5)
        ]

        result = workers.ClassificationResult(user_id="0",
                                              tweets=tweets,
                                              categories=categories)

        self.redis_client.rpush(workers.Queues.CLASSIFICATION_RESULTS, result.to_json())
        self.worker.store_classification_results()
        uts = models.UserTopic.select().where(models.UserTopic.user_id == "0")
        self.assertEqual(uts.count(), len(categories))

        ut_cats = {ut.topic.name for ut in uts}
        cats = {cat.name for cat in categories}
        self.assertEqual(ut_cats, cats)
        for ut in uts:
            self.assertEqual(ut.tweet_count, len(tweets))



class TestScrapeTwitterWorker(DatabaseTestCase):

    def setUp(self):
        super().setUp()
        self.db_worker = workers.DatabaseWorker(self.redis_client)
        self.scrape_worker = workers.ScrapeUserTweetsWorker(self.redis_client)

    def tearDown(self):
        return super().tearDown()

    @mock.patch("ec601_proj2.workers.twitter_utils")
    def test_scrape_single_user_tweets(self, mock_twitter):
        self._populate_users(1)
        self.db_worker.queue_users_to_scrape()

        tweets = list(self._generate_user_tweets("0", 2))
        mock_twitter.Tweet = twitter_utils.Tweet
        mock_twitter.get_user_tweets.return_value = tweets

        self.scrape_worker.process()
        mock_twitter.get_user_tweets.assert_called_once_with("0")

        for tweet in tweets:
            result = self.redis_client.lpop(workers.Queues.SCRAPE_USER_TWEETS_RESULTS)
            self.assertIsNotNone(result)
            result_tweet = self.scrape_worker.deserialize_result(result)
            self.assertEqual(result_tweet.id, tweet.id)

        # Make sure the queue is empty
        self.scrape_worker.process()
        self.assertEqual(mock_twitter.get_user_tweets.call_count, 1)


    @mock.patch("ec601_proj2.workers.twitter_utils")
    def test_rate_limit_hit(self, mock_twitter):
        rate_limit_expires = time.time() + 300
        mock_twitter.TwitterRateLimitError = twitter_utils.TwitterRateLimitError
        error = twitter_utils.TwitterRateLimitError(rate_limit_expires)
        mock_twitter.get_user_tweets.side_effect = error
        self._populate_users(1)
        self.db_worker.queue_users_to_scrape()

        self.scrape_worker.process()
        exp = workers.twitter_rate_limit_time(self.redis_client)
        self.assertIsNotNone(exp)
        self.assertGreater(exp, 0)
        self.assertEqual(mock_twitter.get_user_tweets.call_count, 1)

        self.scrape_worker.process()
        # Make sure it didn't call it again
        self.assertEqual(mock_twitter.get_user_tweets.call_count, 1)

        # Simulate that the rate limit has reset expired.
        workers.set_twitter_rate_limit_time(self.redis_client, time.time() - 1)
        self.assertLessEqual(workers.twitter_rate_limit_time(self.redis_client), 0)
        tweets = list(self._generate_user_tweets("0", 2))
        mock_twitter.Tweet = twitter_utils.Tweet
        mock_twitter.get_user_tweets.side_effect = None
        mock_twitter.get_user_tweets.return_value = tweets
        self.scrape_worker.process()
        self.assertEqual(mock_twitter.get_user_tweets.call_count, 2)


class TestEntityAnalysisWorker(DatabaseTestCase):


    def setUp(self):
        super().setUp()
        self.db_worker = workers.DatabaseWorker(self.redis_client)
        self.scrape_worker = workers.ScrapeUserTweetsWorker(self.redis_client)
        self.entity_analysis_worker = workers.EntityAnalysisWorker(self.redis_client)


    def test_analyze_entities(self):
        self._populate_users(1)
        self.db_worker.queue_users_to_scrape()

        tweets = list(self._generate_user_tweets("0", 1))
        with mock.patch("ec601_proj2.workers.twitter_utils") as mock_twitter:
            mock_twitter.get_user_tweets.return_value = tweets
            self.scrape_worker.process()


        self.db_worker.process()

        with mock.patch("ec601_proj2.workers.google_nlp") as mock_nlp:
            mock_nlp.Entity = google_nlp.Entity
            response = mock.Mock()
            response.entities = entities = self._generate_dummy_entities(2)
            mock_nlp.LanguageClient.analyze_entities.return_value = response
            self.entity_analysis_worker.process()
            mock_nlp.LanguageClient.analyze_entities.assert_called_once_with(
                tweets[0].text)

        result = self.redis_client.lpop(workers.Queues.ENTITY_ANALYSIS_RESULTS)
        result = self.entity_analysis_worker.deserialize_result(result)
        self.assertEqual(result.tweet.id, tweets[0].id)
        for i, ent in enumerate(entities):
            self.assertEqual(result.entities[i].name, ent.name)


class TestClassificationWorker(DatabaseTestCase):

    def setUp(self):
        super().setUp()
        self.worker = workers.ClassificationWorker(self.redis_client)


    def test_classify_tweets(self):
        self._populate_users(1)
        self._populate_db_with_user_tweets("0", 5)
        tweets = list(models.Tweet.select().where(models.Tweet.user_id == "0"))
        req = workers.ClassificationRequest(user_id="0", tweets=tweets)

        self.redis_client.rpush(workers.Queues.CLASSIFICATION_REQUESTS, req.to_json())
        tweet_text = " ".join([t.text for t in tweets])

        with mock.patch("ec601_proj2.workers.google_nlp") as mock_nlp:
            mock_nlp.ClassificationCategory = google_nlp.ClassificationCategory
            categories = [
                google_nlp.ClassificationCategory(name="Cat 1", confidence=0.5),
                google_nlp.ClassificationCategory(name="Cat 2", confidence=0.5)
            ]
            response = mock.Mock()
            response.categories = categories
            mock_nlp.LanguageClient.classify_text.return_value = response
            self.worker.process()
            mock_nlp.LanguageClient.classify_text.assert_called_once_with(tweet_text)

            result = self.redis_client.lpop(workers.Queues.CLASSIFICATION_RESULTS)
            self.assertIsNotNone(result)
            result = workers.ClassificationResult.from_json(result)

            self.assertEqual(result.user_id, "0")
            expected_tweets_ids = {t.id for t in tweets}
            result_tweet_ids = {t.id for t in result.tweets}
            self.assertEqual(expected_tweets_ids, result_tweet_ids)

            category_names = [c.name for c in result.categories]
            expected_categories = [c.name for c in categories]
            self.assertEqual(expected_categories, category_names)