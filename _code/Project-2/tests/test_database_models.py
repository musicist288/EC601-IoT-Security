"""
    Unit tests to make sure the models are behaving as expected.
"""
import os
import unittest
import peewee

from ec601_proj2 import models
from ec601_proj2 import twitter_utils

MODELS = models.TABLES
DB_FILENAME = "test.db"
DATABASE = peewee.SqliteDatabase(DB_FILENAME)

class DatabaseTests(unittest.TestCase):

    def setUp(self):
        DATABASE.bind(MODELS, bind_refs=False, bind_backrefs=False)
        DATABASE.connect()
        DATABASE.create_tables(MODELS)

    def tearDown(self):
        DATABASE.drop_tables(MODELS)
        DATABASE.close()
        os.unlink(DB_FILENAME)

    def test_create_user(self):
        twitter_user = twitter_utils.TwitterUser(
            id="5678",
            name="Jake",
            username="thesnake",
            url="",
            description="Some guy on the Internet",
            verified=False
        )

        models.create_user(twitter_user)

        user = models.User.get_by_id(twitter_user.id)
        attrs = ('id', 'username', 'url', 'description', 'verified')
        for attr in attrs:
            self.assertEqual(getattr(user, attr), getattr(twitter_user, attr))

    def test_create_tweet(self):
        twitter_user = twitter_utils.TwitterUser(
            id="5678",
            name="Jake",
            username="thesnake",
            url="",
            description="Some guy on the Internet",
            verified=False
        )

        models.create_user(twitter_user)

        tweet = twitter_utils.Tweet(
            id="1234",
            author_id=twitter_user.id,
            created_at="2021-09-30T15:33:23Z",
            text="This is a text object"
        )

        models.add_tweet(tweet)

        model = models.Tweet.get_by_id(tweet.id)
        for attr in ('id', 'created_at', 'text'):
            self.assertEqual(getattr(model, attr), getattr(tweet, attr))

        self.assertEqual(model.user.id, twitter_user.id)


    def test_entity(self):
        name = "MY ENTITY"
        type_ = "ORGANIZATION"

        model = models.Entity.create(name=name, type=type_)
        model.save()

        ent = models.Entity.get(models.Entity.name == name)
        self.assertEqual(ent.name, model.name)
        self.assertEqual(ent.type, model.type)


    def test_tweet_entity(self):
        twitter_user = twitter_utils.TwitterUser(
            id="5678",
            name="Jake",
            username="thesnake",
            url="",
            description="Some guy on the Internet",
            verified=False
        )
        tweet = twitter_utils.Tweet(
            id="1234",
            author_id=twitter_user.id,
            created_at="2021-09-30T15:33:23Z",
            text="This is a text object"
        )

        models.create_user(twitter_user)
        tweet_model = models.add_tweet(tweet)
        entity_model = models.Entity.create(name="MYENT", type="ORG")

        tweet_ent = models.TweetEntity.create(tweet=tweet_model, entity=entity_model)
        tweet_ent.save()

        ret = models.TweetEntity.get(models.TweetEntity.tweet == tweet_model and models.TweetEntity.entity == entity_model)
        self.assertEqual(ret.tweet.id, tweet.id)
        self.assertEqual(ret.entity.name, "MYENT")



    def test_topic(self):
        topic_name = "/Arts & Entertainment"
        topic = models.Topic.create(name=topic_name)
        topic.save()

        result = models.Topic.get(name=topic_name)
        self.assertEqual(result.name, topic_name)


    def test_user_topic(self):
        twitter_user = twitter_utils.TwitterUser(
            id="5678",
            name="Jake",
            username="thesnake",
            url="",
            description="Some guy on the Internet",
            verified=False
        )

        user_model = models.create_user(twitter_user)
        topic_name = "/Arts & Entertainment"
        topic_model = models.Topic.create(name=topic_name)

        user_topic = models.UserTopic.create(user=user_model, topic=topic_model)

        ret = models.UserTopic.get(models.UserTopic.user == user_model and models.UserTopic.topic == topic_model)
        self.assertEqual(ret.user.id, twitter_user.id)
        self.assertEqual(ret.topic.name, topic_name)

        user_model = models.User.get_by_id(twitter_user.id)
        self.assertEqual(len(user_model.user_topics), 1)
        self.assertEqual(user_model.user_topics[0].topic.name, topic_name)
