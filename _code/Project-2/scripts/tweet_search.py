"""
    A simple script to search for tweets using the Twitter
    V2 API.
"""
from argparse import ArgumentParser
import dateparser
from ec601_proj2 import twitter_utils, google_nlp
from ec601_proj2.google_nlp import LanguageClient

def cli_main():
    """
        Entry point when called as the main module.
    """
    parser = ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--since", type=str)
    parser.add_argument("--until", type=str)
    parser.add_argument("--sentiments", action="store_true", default=False)

    args = parser.parse_args()

    if args.since:
        since = dateparser.parse(args.since)
    else:
        since = None

    if args.until:
        until = dateparser.parse(args.until)
    else:
        until = None

    # This will raise an exception if there is a problem
    # searching.
    tweets = twitter_utils.search(args.query, since, until)
    if not tweets:
        print("Query did not return any results.")
    else:
        for tweet in tweets:
            print(tweet)
            if args.sentiments:
                analysis = LanguageClient.analyze_sentiment(tweet.text)
                sentiment = google_nlp.categorize_sentiment(analysis)
                print(f"Sentiment: {sentiment.name}")
            print("=" * 100)

if __name__ == "__main__":
    cli_main()
