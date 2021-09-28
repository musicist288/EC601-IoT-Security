"""
    A simple script to search for tweets using the Twitter
    V2 API.
"""
from argparse import ArgumentParser

from google.api_core.exceptions import InvalidArgument
from ec601_proj2 import twitter_utils, google_nlp
from ec601_proj2.google_nlp import LanguageClient

def cli_main():
    """
        Entry point when called as the main module.
    """
    parser = ArgumentParser()
    parser.add_argument("--count", type=int, help="Number of tweets to pull.")
    parser.add_argument("--classify", action="store_true", default=False)
    args = parser.parse_args()

    # This will raise an exception if there is a problem
    # searching.
    tweets = twitter_utils.home_timeline(args.count)
    if not tweets:
        print("Query did not return any results.")
    else:
        for tweet in tweets:
            print(str(tweet))
            if args.classify:
                try:
                    response = LanguageClient.classify_text(tweet.text)
                    category = google_nlp.choose_category(response.categories)
                    if category:
                        category = category.name
                except InvalidArgument:
                    category = None

                print(f"Category: {category}")
            print("=" * 100)

if __name__ == "__main__":
    cli_main()
