"""
    A simple script to search for tweets.
"""
from argparse import ArgumentParser
from ec601_proj2 import twitter_utils, google_nlp

def cli_main():
    """
        Entry point when called as the main module.
    """
    parser = ArgumentParser()
    parser.add_argument("query")

    args = parser.parse_args()

    # This will raise an exception if there is a problem
    # searching.
    tweets = twitter_utils.search(args.query)
    for tweet in tweets:
        sentiment = google_nlp.categorize_sentiment(google_nlp.get_sentiment_analysis(tweet.text))
        print(tweet)
        print(f"Sentiment: {sentiment.name}")
        print("=" * 100)


if __name__ == "__main__":
    cli_main()
