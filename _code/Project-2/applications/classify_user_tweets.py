import os
import time
import logging
import sys

from dotenv import load_dotenv
import peewee
import redis

from ec601_proj2 import models, twitter_utils, LOGGER

from ec601_proj2.workers import (
    DatabaseWorker,
    EntityAnalysisWorker,
    ClassificationWorker,
    ScrapeUserTweetsWorker,
    get_google_rate_limit_expires,
    get_twitter_rate_limt_expires
)

load_dotenv()

REDIS_SERVER_HOST = os.getenv("REDIS_SERVER_HOST")
REDIS_SERVER_PORT = int(os.getenv("REDIS_SERVER_PORT"))
REDIS_SERVER_DB = int(os.getenv("REDIS_SERVER_DB"))

DB_FILE = os.getenv("SQLITE_DATABASE")

def init_loging(filename, log_level):
    log_formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(name)-15s %(message)s [%(module)s:%(lineno)s]")
    file_handler = logging.FileHandler(filename)
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(log_level)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(log_formatter)
    stream_handler.setLevel(log_level)

    LOGGER.addHandler(file_handler)
    LOGGER.addHandler(stream_handler)
    LOGGER.setLevel(log_level)


class ClassifyUsers:

    def __init__(self, redis_client: redis.Redis, database: peewee.Database):

        self.redis_client = redis_client
        self.database = database

        try:
            self.redis_client.keys()
        except (ConnectionError, TimeoutError) as err:
            msg = ("Could not communicate with redis server. "
                   "Make sure it's running")
            raise RuntimeError(msg) from err


        self.db_worker = DatabaseWorker(self.redis_client)
        self.entity_worker = EntityAnalysisWorker(self.redis_client)
        self.classify_worker = ClassificationWorker(self.redis_client)
        # Grab 50 tweets per user.
        self.twitter_worker = ScrapeUserTweetsWorker(self.redis_client, tweet_count=50)


    def _run_forever(self):
        while True:
            LOGGER.debug("Process db_worker")
            self.db_worker.process()
            LOGGER.debug("Process twitter_worker")
            self.twitter_worker.process()
            LOGGER.debug("Process entity_worker")
            self.entity_worker.process()
            LOGGER.debug("Process classify_worker")
            self.classify_worker.process()
            time.sleep(0.2)


    def _run_single(self):
        # Scrape Twitter
        self.db_worker.queue_users_to_scrape()
        while True:
            rc = self.twitter_worker.process()
            if rc == False:
                break

            if rc == "wait":
                LOGGER.info("Waiting for twitter rate limit to expire.")
                time.sleep(get_twitter_rate_limt_expires(self.redis_client))
        self.db_worker.store_scraped_tweets()

        # Entity Analysis
        self.db_worker.queue_entity_analysis_requests()
        while True:
            rc = self.entity_worker.process()
            if rc == False:
                break

            if rc == "wait":
                tts = get_google_rate_limit_expires(self.redis_client)
                LOGGER.info("Waiting for google rate limit to expire: %s", tts)
                time.sleep(tts)
        self.db_worker.store_entity_analysis_results()

        # Classify Worker
        self.db_worker.queue_classification_requests()
        while True:
            rc = self.classify_worker.process()
            if rc == False:
                break

            if rc == "wait":
                tts = get_google_rate_limit_expires(self.redis_client)
                LOGGER.info("Waiting for google rate limit to expire: %s", tts)
                time.sleep(tts)
        self.db_worker.store_classification_results()
        time.sleep(1)



    def run(self, single=True):
        if single:
            self._run_single()
        else:
            self._run_forever()


def queue_user(database, redis_client, username):
    try:
        user = models.User.get(models.User.username == username)
        LOGGER.debug("User exists, clearing last scraped time.")
        user.last_scraped = None
        user.save()
    except models.User.DoesNotExist:
        LOGGER.debug("Fetching user from twitter.")
        twitter_user = twitter_utils.get_user_by_username(username)
        user = models.create_user(twitter_user)


def run_worker_pipline_command(database, redis_client, args):
    app = ClassifyUsers(redis_client, database)
    app.run(single=not args.as_daemon)


# TODO: Figure out if there's a better way to use subparsers
# so we can have heterogenous commands
def queue_user_command(database, redis_client: redis.Redis, args):
    queue_user(database, redis_client, args.username)


def main():
    from argparse import ArgumentParser
    from pathlib import Path
    parser = ArgumentParser()
    filename = Path(__file__).with_suffix(".log").name
    parser.add_argument("-f", "--log-file", default=filename, help="Log file to log to.")
    parser.add_argument("-l", "--log-level", default="info", help="Log file to log to.")
    subparsers = parser.add_subparsers()
    worker_parser = subparsers.add_parser("process")
    worker_parser.add_argument("-d", "--as-daemon", action="store_true", default=False)
    worker_parser.set_defaults(func=run_worker_pipline_command)

    queue_user_parser = subparsers.add_parser("queue-user")
    queue_user_parser.add_argument("username")
    queue_user_parser.set_defaults(func=queue_user_command)

    args = parser.parse_args()

    try:
        log_level = getattr(logging, args.log_level.upper())
    except AttributeError as err:
        raise ValueError("Invalid log level: %s." % args.log_level) from err

    init_loging(args.log_file, log_level)
    LOGGER.debug("Running command: %s", args.func.__name__)

    LOGGER.debug("Setting up redis client. Host: %s, Port: %s, DB: %s",
                  REDIS_SERVER_HOST, REDIS_SERVER_PORT, REDIS_SERVER_DB)
    redis_client = redis.Redis(REDIS_SERVER_HOST,
                               REDIS_SERVER_PORT,
                               REDIS_SERVER_DB)

    LOGGER.debug("Using database file: %s", DB_FILE)
    database = models.init_db(DB_FILE)
    args.func(database, redis_client, args)

if __name__ == "__main__":
    main()
