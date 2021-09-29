# User Story

## Motivation and Plan

Twitter's current discovery mechanism is a bit too open for my liking. After
years of not using Twitter, I find it difficult to curate my timeline to my
liking. I've tried finding relevant hashtags, but it seems they are not as
useful as they once were-- they mostly return marketing or advertising content.
I suspect that based on the network of people I followed last time I used
Twitter, I should be able to grow my network based on topics they Tweet about.

### What does it need to do?

**MVP**

- The application needs to build a dataset of Twitter accounts by topics I specify.
    + Find friends of friends through my network (graph search)
    + Detect what each Tweet it talking about (entity analysis)
    + Classify the content of those tweets (disambiguation)
- I should be able to query by topic to get a list of tweets or user accounts.

**Nice to Have**

- Be able to follow users I find interesting
- Add a nice UI around it
- It might be possible to rank accounts based on the sentiment of their Tweets.
  I'm not looking for negative energy in my Twitter timeline.


### How will I build it?

I'll use Twitter's API with credentials for my account and scrape. I will
define a custom database schema to catalog my dataset.

Google Cloud offers some great services for analyzing free text. Using
Twitter's API and Google's NLP services, I should be able to build a tool for
discovering friends of friends through a network.


### Challenges and Limitations

- Twitter and Google Cloud have pretty strict rate limits that limit my applications
  ability to scrape for data.
- If the process building the dataset hits rate limits, I need to be able to resume the
  scraping process when the APIs are available again.
- Google requires a decent amount of text to classify Tweets. From experimentation, many
  Tweets are not classified by their text alone. I will try to combine Tweets based on
  entities that they share in common and see if that yields better results.
