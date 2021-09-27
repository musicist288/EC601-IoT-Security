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
to the root to the repo.

See the README file in the `scripts/` folder for a description of the different
scripts and their results.

