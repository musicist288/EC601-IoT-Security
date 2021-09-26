This folder contains scripts developed to experiment with the different Google
NLP and Twitter Development APIs.

## tweet_search.py

**Usage:** `tweet_search.py [-h] [--since SINCE] [--until UNTIL] [--sentiments] query`

**Example:** `python tweet_search.py --since="1 hour ago" "boston mayor"`

**Description:**

This script provides a CLI interface to interact with the Twitter V2 search
API. It accepts any string and passes it along as the search query. It can
accept an advanced search query as documented by twitter's API

There are two optional parameters for `--since` and `--until` that allow you to
limit the date range of tweets returned. One nice python package I found was
`dateparser`  It takes in human readable strings such as "yesterday" and "1
hour ago" and converts them into datetime objects that can then be passed. I
used this package to add a more intuitive interface to the since and until
parameters. However, keep in mind that Twitter's standard API only allows
users to query tweets composed within the last seven days.

Passing the `--sentiment` flag will categorize the tweet's sentiment as
neutral, mixed, positive or negative based on the Google's NLP sentiment
analysis. As a first step I used a [table from the
documentation](https://cloud.google.com/natural-language/docs/basics#interpreting_sentiment_analysis_values)
to categorize the sentiments. The categorization results are pretty crude
and not always accurate, especially in the case of sarcastic tweets.

### Results

**Query:** "#Boston"

**Result:** Returns a list of tweets that contain the hashtag "#Boston". Pretty simple 
and works as expected.

---

**Query:** "boston food (delicious OR amazing) -apartment -festival"

**Result:**
This query is an example of [Twitter's advanced filter
syntax](https://developer.twitter.com/en/docs/twitter-api/tweets/search/integrate/build-a-query)
that allows the searcher to be more specific about what combinations of words
to include and exclude from results.

Running the above query returns a list of tweets that must contain the words
"boston" and "food" somewhere in the tweet. The results must also contain
either "delicious" or "amazing" in the tweet's text. After running this
query with just those specifiers, I received a few irrelevant tweets that were
advertising apartments that are near restaurants or festivals in the area so I
added the negative terms to filter out those results.

