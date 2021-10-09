This directory contains experiments developed for Project 2 for EC601.

> All the directories are unimaginatively named while figuring out what to do
> with the APIs. They will likely be renamed once I have a better idea of what
> to build.

> If you're looking for the write-up of the interactions with Twitter's API,
> see [the scripts README](scripts/README.md).

## Requirements

* Python 3.7+
* This repo uses [Poetry](https://python-poetry.org/) for dependency
  management. If you are not running Poetry, you can use
  `pip install -r requirements.txt` to install dependencies with
  pip.
* Access to Twitter's Developer APIs
* Access to Google's NLP APIs
* Access to a redis server.

The following environment variables need to be set:

| Environment Variable Name        | Description                                                                       |
|----------------------------------|-----------------------------------------------------------------------------------|
| `TWITTER_CONSUMER_KEY`           | The API key used for OAuth2 access to Twitter APIs                                |
| `TWITTER_CONSUMER_SECRET`        | The API secret key used for authorization                                         |
| `TWITTER_ACCESS_KEY`             | An access token generated to access your personal account's data.                 |
| `TWITTER_ACCESS_SECRET`          | The corresponding access secret generated to access your personal account's data. |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to the file containing your Google Cloud credentials with NLP access.        |

For convenience, you may put these variables in a `.env` file your working directory
and the scripts will pick the environment variables up that way.

## Setup

1. To get started, install the dependencies: `poetry install`
1. You can then drop into a shell to run scripts in any of the playground
   directories: `poetry shell`

The utilities for interacting with the APIs are in the `ec601_proj2` folder.
Scripts that exercise these utilities are in the `scripts/` directory. They
depend on `import ec601_proj2` succeeding. Your options are to run all scripts
from the root of this repo, or you can set your PYTHONPATH environment variable
to the root to the repo. For example, in a bash shell:

```
export PYTHONPATH=$(pwd)
```

See the README file in the `scripts/` folder for a description of the different
scripts and their results.


## Classification Pipeline

The example application that runs the full classification pipeline is in
`applications/classify_twitter_users.py`. To run the pipline, you need
to have access to a running redis server. If you have redis installed
on your system, you can start an instance of the server from the root
of this repository using:

`redis-server redis.conf`

Then you need to have the following environement variables set (or in your `.env` file)

| Environment Variable Name | Description                                          |
|---------------------------|------------------------------------------------------|
| `REDIS_SERVER_HOST`       | The hostname of the redis server                     |
| `REDIS_SERVER_PORT`       | The port on which to connect                         |
| `REDIS_SERVER_DB`         | The redis database to use for the pipeline           |
| `SQLITE_DATABASE`         | The filename of the sqlite database to store results |

Once the environemnt is setup and redis is running, to kick things off, put things in
the users queue using:

`python applications/classify_user_tweets.py [username]`

Where `[username]` is the twitter user whom should be classified.

Once that is done, run `python applications/classify_user_tweets.py process`. This
will run the pipeline through once for all the users to scrape. If you run this
using `-d/--as-daemon`, it will process the queue inifintely, other programs
could submit work by adding users to the database so they will get picked up by
the classification pipeline.


## Web Client

Once there is some data in the database, you can run the web client to search for users
by topics they are interested in:

```
export FLASK_APP=applications.web_client.api
flask run
```

Then load `http://localhost:5000` in your browser and start searching (case sensitive for now, Type `/` to get a list of topics).
