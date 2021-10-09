---
layout: single
slug: twitter-classifications
title:  "Classifying Twitter Users"
author: Joseph Rossi
date:   2021-10-08 12:00:00 -0400
excerpt: ""
show_date: True
---

## A Re-Introduction to Twitter

Twitter has changed a lot since I last used it. Over the years, I've poked my head in occasionally, but I never really integrated Twitter into my everyday social media usage, so I had a lot to catch up on. Twitter's search API has gotten much more robust. While still often used, hashtags are not as critical to searching for and finding Tweets on a particular topic. When poking around, searching for hashtags returned just the kind of results I try to avoid, marketing and advertising.

After a bit of noodling with the site, I decided I wanted to find more users to that talk about topics I like reading about and follow them. Searching wasn't doing it for me, and a lot of the people I already followed are well-established, industry-leading programmers. They often tweeted about new tools, core knowledge, or relevant experiences they are having in their professional and hobby projects. I figured the best place to start finding more people who share my interests would be to look at the users they follow.

Queue the next roadblock: they follow a lot more people than I do. I did not want to spend hours scrolling through their followers, clicking on their feeds and deciphering whether they are people I am interested in following. So the idea for my application was to analyze the tweets of the people that I follow, and who they follow, to find interesting users to add to my Twitter feed.

## Finding Like-Minded Tweeters

The problem essentially came down to asking, "Can I get a list of people who talk about a topic?" Oftentimes people tweet about different things related the same broad topic. For example, I follow a lot of programmers. They often tweet about Python, Rust, or other programming languages, but their tweets almost never contain the words "programming." So I wanted to find a way to programmatically figure out: "does this person talk about programming?" Turns out that Google Language Services has the right tools, when matched with Twitter's API, to start attacking this problem.

I was able to break it down into the following steps:

1. Using Twitter's API, I can pull down tweets from the people I might want to follow.
2. Using Google's entity analysis, I can create an index of the entities that a user has tweeted about.
3. Grouping tweets by their entities, I can ask Google's classification service what these tweets are talking about.
4. Then, I can store the topics that people tweet about.
5. Finally, I can search for users by topics they talk about.

The third step of this flow (grouping by entities) was added to solve a constraint in Google's classification service. The service works best when given a lot of text. Often, single tweets are too short for Google to discern the topic the tweet is talking about. To get more text, the Database Worker groups a user's tweets by common entities and submits the concatenated text of those tweets to the classification API, assuming they are related to the same overall topic. This helped get higher quality results. It's a simple trick, and leaves a lot of assumptions on the table, but is illustrative of another sub-problem of this macro task to dive into.

## The Nuts & Bolts

To achieve the flow above, I created a pipeline to scrape and classify users by their tweets. It's architected using queues and workers, as depicted below. The intent is that the different workers could act as their own microservices at scale:

![Classification Pipeline Diagram]({{site.baseurl}}/assets/images/Project2_ClassificationPipeline.png)

The different worker roles are as follows:

* The Database Worker powers the logic behind what work gets queued and storing the results. It queries the database for users that should be scraped, tweets that should be analyzed, and groups of tweets that should be classified.
* The Twitter Worker is responsible for fetching user tweets and storing them in a database. When it's done, it puts the results in a queue for the Database Worker to store.
* The Entity Analysis Worker takes tweets that have been pulled by users and analyzes them for entities they contain.
* The Classification Worker groups tweets by user and common entities and submits them to Google's service for classification.

All workers store their results in isolated result queues and the Database Worker comes back around to store the results in the database, updating the models appropriately, so they are not reanalyzed.

There is an example application for [classifying Twitter users](https://github.com/musicist288/EC601-IoT-Security/blob/dev/_code/Project-2/applications/classify_user_tweets.py) that initializes the database and runs all the workers in one loop. There needs to be more coordination added to ensure operation ordering, but the workers could be run independently as long as they have access to the queue. The application has a CLI interface from which you can manually queue users who will get analyzed. As a test, I also wrote a script that builds a database of Twitter users by gathering the followers of followers. (Spoiler: It turns out this is NOT a good idea... Twitter is huge in a way I cannot comprehend.)

Finally, I built a simple web page to search for users by a topic and see if there are any new people I want to follow.

If you're interested in the tech stack, all business logic was written in Python using open-source libraries (see [pyproject.toml](https://github.com/musicist288/EC601-IoT-Security/blob/dev/_code/Project-2/pyproject.toml) for the list). The data layers are supported by two open-source projects:

- [Redis](https://redis.io) is used for all worker queues and to handle rate limiting.
- [Peewee](http://docs.peewee-orm.com/) is the database ORM. My application ran it on top of SQLite, but any relational database it supports could be used.

## Results and Retrospective

In the end, I did get a dataset I could query to group users by the topics they tweet about. There is a lot of quality tuning to explore, but the way the problem was modeled did result in something interesting. I didn't really factor in confidence scores returned through the different APIs, mostly due to time constraints and a general weariness of interpreting them. Additionally, while the "group by entities" approach to classifying tweets kind of worked, it often resulted in only a single tweet being classified at a time. This often wasn't enough text for Google's classification service, resulting in many tweets not contributing to the user analysis.

As this application was build in just a handful of hours, it is not the most performant. The pipeline could definitely be optimized in the usual ways (more efficient database queries, throttling to hit rate limits less often, etc.), but the architecture is fairly flexible and allows for the logic flow to be manipulated and the rules to be changed without having to tear things apart too much.

The user discovery piece (which users to scrape) is another puzzle to solve for. My attempt here was to do a simple "linked-followers" search, which quickly grows out of hand. The Database Worker knows not to scrape users too often and to ignore duplicates if the same person comes up multiple times. However, after just going two levels deep, the application started to discover thousands of users and hundreds of thousands of tweets. Due to rate limits (and fear of running out of all my free-trial credits), I had to cut it short before processing even two full levels.
