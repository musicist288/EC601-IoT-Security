"""
    This module containt the model defintions and helper function
    for storing data as it is scraped and classified.
"""
from peewee import *

from . import twitter_utils

database = SqliteDatabase("project.db")

class BaseModel(Model):
    class Meta:
        database = database


class User(BaseModel):
    id = CharField(primary_key=True)
    name = CharField()
    username = CharField()
    url = CharField()
    description = CharField()
    verified = BooleanField()


class Tweet(BaseModel):
    id = CharField(primary_key=True)
    user = ForeignKeyField(User, backref='tweets')
    created_at = DateTimeField()
    text = CharField()


class Topic(BaseModel):
    name = CharField()


class UserTopic(BaseModel):
    user = ForeignKeyField(User, backref="user_topics")
    topic = ForeignKeyField(Topic, backref="user_topics")


class Entity(BaseModel):
    name = CharField(unique=True)
    type = CharField()


class TweetEntity(BaseModel):
    tweet = ForeignKeyField(Tweet, backref="tweet_entities")
    entity = ForeignKeyField(Entity, backref="tweet_entities")


def add_user_topic(user: twitter_utils.TwitterUser, topic: str):
    topic, created = Topic.get_or_none(topic)
    if created:
        topic.save()

    user = User.get_by_id(user.id)
    user_topic = UserTopic.create(user, topic)
    user_topic.save()


def create_user(twitter_user: twitter_utils.TwitterUser):
    user, created = User.get_or_create(**twitter_user.to_dict())

    if created:
        user.save()

    return user

def get_user(author_id):
    user = User.get(id=author_id)
    return user


def add_tweet(tweet: twitter_utils.Tweet, user: twitter_utils.TwitterUser):
    user_model = User.get_by_id(user.id)
    try:
        tweet_model = Tweet.get_by_id(tweet.id)
    except Exception as err:
        data = tweet.to_dict()
        data.pop("author_id")
        data['user'] = user_model
        tweet_model = Tweet.create(**data)

    tweet_model.save()

    return tweet_model

TABLES = [User, Tweet, Topic, UserTopic, Entity, TweetEntity]
def createdb(filename):
    global database
    database = SqliteDatabase(filename)
    database.connect()
    database.create_tables(TABLES)
