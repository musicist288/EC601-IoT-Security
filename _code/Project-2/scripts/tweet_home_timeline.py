"""
    A simple script to search for tweets using the Twitter
    V2 API.
"""
from argparse import ArgumentParser
from ec601_proj2 import twitter_utils

def cli_main():
    """
        Entry point when called as the main module.
    """
    parser = ArgumentParser()
    parser.add_argument("--count", type=int, help="Number of tweets to pull.")
    args = parser.parse_args()

    # This will raise an exception if there is a problem
    # searching.
    tweets = twitter_utils.home_timeline(args.count)
    if not tweets:
        print("Query did not return any results.")
    else:
        for tweet in tweets:
            print(str(tweet))
            print("=" * 100)

if __name__ == "__main__":
    cli_main()
