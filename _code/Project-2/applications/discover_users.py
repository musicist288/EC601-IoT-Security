
import os
import time
import logging
import sys

from dotenv import load_dotenv
import peewee
import redis

from ec601_proj2 import (
    twitter_utils,
    models,
    LOGGER
)

from ec601_proj2.workers import (
    set_twitter_rate_limit_time,
    twitter_rate_limit_time
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


class DiscoverUsers:

    def __init__(self, redis_client: redis.Redis, database: peewee.Database):

        self.redis_client = redis_client
        self.database = database

        try:
            self.redis_client.keys()
        except (ConnectionError, TimeoutError) as err:
            msg = ("Could not communicate with redis server. "
                   "Make sure it's running")
            raise RuntimeError(msg) from err


    def scrape_user_following(self, user: models.User):
        if twitter_rate_limit_time(self.redis_client) > 0:
            LOGGER.info("Not sraping user because twitter rate limit has not expired.")
            return

        try:
            for following in twitter_utils.iterate_following(user.id):
                count = models.User.select().where(models.User.id == following.id).count()
                if count > 0:
                    continue

                model = models.create_user(following)
                LOGGER.debug("Added user: %s (id: %s)",
                                model.username,
                                model.id)

            user.scraped_following = True
            user.save()
        except twitter_utils.TwitterRateLimitError as err:
            set_twitter_rate_limit_time(self.redis_client, err.reset_epoch_seconds)


    def _run_forever(self):
        while True:
            self._run_single()


    def _run_single(self):
        wait_time = twitter_rate_limit_time(self.redis_client)

        if wait_time > 0:
            LOGGER.info("Sleeping for %s seconds until twitter rate limit expires.", wait_time)
            time.sleep(wait_time + 5)
            return

        to_scrape_following = list(models.User.select().where(models.User.scraped_following == False).limit(1))
        if to_scrape_following:
            #print("Will scrape: ", to_scrape_following[0].username)
            self.scrape_user_following(to_scrape_following[0])


    def run(self, single=True):
        if single:
            self._run_single()
        else:
            self._run_forever()


def main():
    from argparse import ArgumentParser
    from pathlib import Path
    parser = ArgumentParser()
    filename = Path(__file__).with_suffix(".log").name
    parser.add_argument("-f", "--log-file", default=filename, help="Log file to log to.")
    parser.add_argument("-l", "--log-level", default="debug", help="Log file to log to.")
    parser.add_argument("-d", "--as-daemon", action="store_true", default=False)

    args = parser.parse_args()

    try:
        log_level = getattr(logging, args.log_level.upper())
    except AttributeError as err:
        raise ValueError("Invalid log level: %s." % args.log_level) from err

    init_loging(args.log_file, log_level)

    LOGGER.debug("Setting up redis client. Host: %s, Port: %s, DB: %s",
                  REDIS_SERVER_HOST, REDIS_SERVER_PORT, REDIS_SERVER_DB)
    redis_client = redis.Redis(REDIS_SERVER_HOST,
                               REDIS_SERVER_PORT,
                               REDIS_SERVER_DB)

    LOGGER.debug("Using database file: %s", DB_FILE)
    database = models.init_db(DB_FILE)

    app = DiscoverUsers(redis_client, database)
    app.run(single=not args.as_daemon)

if __name__ == "__main__":
    main()
