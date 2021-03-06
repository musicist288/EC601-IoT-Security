"""
    This module containt the model defintions and helper function
    for storing data as it is scraped and classified.

    Note that not all models have a primary key. In thses cases
    the ORM will generate a primary key field and use it for
    building the model relations.
"""
import os

from peewee import (
    Model,
    DateTimeField,
    CharField,
    BooleanField,
    ForeignKeyField,
    IntegerField,
    FloatField,
    SqliteDatabase
)

from . import twitter_utils

class BaseModel(Model):
    pass


class User(BaseModel):
    id = CharField(primary_key=True)
    name = CharField()
    username = CharField(unique=True)
    url = CharField(null=True)
    description = CharField(null=True)
    verified = BooleanField()
    last_scraped = DateTimeField(null=True)
    scraped_following = BooleanField(default=False)
    protected = BooleanField()


class Tweet(BaseModel):
    id = CharField(primary_key=True)
    user = ForeignKeyField(User, backref='tweets')
    created_at = DateTimeField()
    text = CharField()
    analyzed = BooleanField(default=False)
    classified = BooleanField(default=False)


class Topic(BaseModel):
    """
        Stored list of topic names that come back from
        Google's NLP classifcations.
    """
    name = CharField()


class UserTopic(BaseModel):
    """
        A many-to-many model for cataloging topics
        that a user discusses.
    """
    user = ForeignKeyField(User, backref="user_topics")
    topic = ForeignKeyField(Topic, backref="user_topics")

    ## How many tweets this topic came up in.
    tweet_count = FloatField(default=0)

    # User added this explicitly as one of thier topics
    # even though it's not detected by their tweet history.
    user_identified = BooleanField(default=False)


class Entity(BaseModel):
    """Store entitiy results from Google"""
    name = CharField()
    type = IntegerField()


Entity.add_index(Entity.index(Entity.name, Entity.type, unique=True))


class TweetEntity(BaseModel):
    """
        Many-to-many mappy to group tweets by entities
        they share in common.
    """
    tweet = ForeignKeyField(Tweet, backref="tweet_entities")
    entity = ForeignKeyField(Entity, backref="tweet_entities")


## Helper functions for working with models

def create_user(twitter_user: twitter_utils.TwitterUser) -> User:
    user, created = User.get_or_create(**twitter_user.to_dict())

    if created:
        user.save()

    return user

def get_user(author_id):
    user = User.get(id=author_id)
    return user


def add_tweet(tweet: twitter_utils.Tweet):
    """
        Add a tweet and user id
    """
    user_model = User.get_by_id(tweet.author_id)
    try:
        tweet_model = Tweet.get_by_id(tweet.id)
    except Exception:
        data = tweet.to_dict()
        data.pop("author_id")
        data['user'] = user_model
        tweet_model = Tweet.create(**data)

    tweet_model.save()

    return tweet_model

TABLES = [User, Tweet, Topic, UserTopic, Entity, TweetEntity]

def init_db(filename):
    #pylint: disable=global-statement
    existed = os.path.exists(filename)
    database = SqliteDatabase(filename)
    database.bind(TABLES)
    database.connect()
    if not existed:
        database.create_tables(TABLES)

    return database
