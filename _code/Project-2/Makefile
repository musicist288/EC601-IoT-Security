
reset:
	- rm classify_user_tweets.log
	pgrep redis-server | xargs kill
	sleep 1
	- rm redis_data/*
	- rm user-classifications.db

queue:
	redis-server redis.conf &
	python applications/classify_user_tweets.py queue-user psycript

