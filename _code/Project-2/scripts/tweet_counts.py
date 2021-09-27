"""
    A simple script to search for tweets using the Twitter
    V2 API.
"""
from argparse import ArgumentParser
import dateparser
from ec601_proj2 import twitter_utils

def cli_main():
    """
        Entry point when called as the main module.
    """
    parser = ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--since", type=str)
    parser.add_argument("--until", type=str)
    parser.add_argument("--granularity",
                        type=str,
                        default="hour",
                        choices=twitter_utils.COUNT_GRANULARITIES)

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
    tweets_counts = twitter_utils.counts(args.query,
                                  args.granularity,
                                  since,
                                  until)
    if not tweets_counts:
        print("Query did not return any results.")
    else:
        for tweet_count in sorted(tweets_counts, key=lambda x: x.count):
            print([
                f"Query: {tweet_count.query}",
                f"Start: {tweet_count.start_time}",
                f"End: {tweet_count.end_time}",
                f"Count: {tweet_count.count}"
            ])
            print("=" * 100)

if __name__ == "__main__":
    cli_main()
