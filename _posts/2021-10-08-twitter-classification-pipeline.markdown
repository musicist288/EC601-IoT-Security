---
layout: single
slug: twitter-classifications
title:  "Classifying Twitter Users"
author: Joseph Rossi
date:   2021-10-08 12:00:00 -0400
excerpt: ""
show_date: True
---

## A Re-introduction to Twitter

Twitter has changed a lot since I last used it. Over the years I've poked my head in occasionally, but I never really integrated Twitter into my everyday social media usage, so I had a lot to catch up on. It seems like, while hashtags are still a central feature, Twitter's search API has gotten much more robust and many users don't seem to use hashtags as much. When poking around, searching for hashtags returned just the kind of results I try to avoid, marketing and advertising.

After a bit of noodling with the site, I decided I wanted to find more users to that talk about topics I like reading about and follow them. Searching wasn't doing it for me, and a lot of the people I already followed are well-established, industry-leading programmers. They often tweeted about new tools, core knowledge, or relevant experiences they are having in their professional and hobby projects. I figured the best place to start finding more people who share my interests would be to look at whom they follow.

Queue the next roadblock: they follow a lot more people than I do. I did not want to spend hours scrolling through their followers, clicking on their feed and deciphering whether they are people I am interested in following. So the idea for my application was to analyze the tweets of the people that I follow, and who then follow, to find interesting users to my Twitter feed.

## Finding Like-minded Tweeters

The problem essentially came down to asking, "Can I get a list of people who talk about a topic?" Often times people tweet about different things about the same topic. For example, I follow a lot of programmers. They often tweet about Python, Rust, or other programming languages, but their tweets almost never contain the words "programming". So I wanted to find a way to programmatically figure out, "does this person talk about programming?" Turns out that Google Language Services has the right tools, when matched with Twitter's API, to start attacking this problem. I was able to break it down into the following steps:

1. Using Twitter's API, I can pull down tweets from the people I might want to follow.
2. Using Google's entity analysis, I can create an index of the entities that a user has tweeted about.
3. Grouping tweets by their entities, I can ask Google's classification service what these tweets are talking about.
4. Then I can store the topics that people tweet about.
5. Finally, I can search for users by topics they talk about.

## The Nuts & Bolts

To achieve the flow above, I created a pipeline to scrape and classify users by their tweets. It's architected using a queues and workers as depicted below. The intent is that the different workers could act as their own microservices at scale:

![Classification Pipeline Diagram](/assets/images/Project2_ClassificationPipeline.png)

The different worker roles are as follows:

* The database worker powers the logic behind what gets work gets queued and storing the results. It queries the database for users that should be scraped, tweets that should be analyzed, and groups of tweets that should be classified.
* The "Twitter Worker" is responsible for fetching user tweets and storing them in a database. When it's done, it puts the results in a queue for the database worker to store.
* The "Entity Analysis" worker takes tweets that have been pulled by users and analyzes them for entities they contain.
* The "Classification Worker" groups tweets by user and common entities and submits them to Google's service for classification.

All workers store their results in isolated result queues and the database worker comes back around to store the results in the database, updating the models appropriately, so they are not reanalyzed.

There is an example application for [classifying Twitter users](https://github.com/musicist288/EC601-IoT-Security/blob/dev/_code/Project-2/applications/classify_user_tweets.py) that runs all the database and workers all in one loop. There needs to be a more coordination added to ensure operation ordering, but the workers could be run independently so long as they have access to the queue. The application has a CLI interface from which you can manually queue users who will get analyzed. As a test, I also wrote a script that builds a database of Twitter users by gathering the followers of followers. (Spoiler: It turns out this is NOT a good idea... Twitter is huge in a way I cannot comprehend.)

Finally, I built a simple web page to search for users by topic and see if there are any new people I want to follow.

If you're interested in the tech stack, all business logic was written in Python using open-source libraries (See [pyproject.toml](https://github.com/musicist288/EC601-IoT-Security/blob/dev/_code/Project-2/pyproject.toml) for the list). The data layers are supported by two open-source projects:

- (Redis)[https://redis.io] is used for all worker queues and to handling rate limiting
- (Peewee)[http://docs.peewee-orm.com/] is the database ORM on top of SQLite, but any relational database it supports could be used.

## Results and Retrospective

In the end, I did get a dataset I could query to group users by topics they Tweet about. There are a lot of quality tuning to explore, but the way the problem was modeled did result in something interesting. I didn't really factor in confidence scores returned through the different APIs, mostly due to time constraints and a general weariness of the interpreting them. Additionally, while the "group by entities" approach to classifying tweets kind of worked, it often resulted in only a single tweet being classified at a time. This often wasn't enough text for Google's classification service, many tweets don't contribute to the user analysis.

As this application was build in just a handful of hours, it is not the most performant. The pipeline could definitely be optimized in the usual ways (more efficient database queries, throttling to hit rate limits less often, etc), but the architecture is fairly flexible and allows for the logic flow to be manipulated and rules changes without having to tear things apart too much.

The user discovery piece (which users to scrape) is another puzzle to solve for. My attempt here was to do a simple "linked-followers" search, which quickly grows out of hand. The database worker knows not to scrape users too often and to ignore duplicates if the same person comes up multiple times. However, after just going two levels deep, the application started to discover thousands of users and hundreds of thousands of tweets. Due to rate limits (and fear of running out of all my free-trial credits), I had to cut it short before processing even two levels deep.
