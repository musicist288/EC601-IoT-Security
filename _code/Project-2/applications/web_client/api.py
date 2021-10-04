from collections import defaultdict
import os
from flask import (
    Flask,
    jsonify,
    request,
    render_template
)

from ec601_proj2 import models
from playhouse.shortcuts import model_to_dict

DB_FILE  = os.getenv("SQLITE_DATABASE")
models.init_db(DB_FILE)

API = Flask(__name__, static_url_path="/static", static_folder="static/")

@API.get("/api/topics")
def get_topics():
    topic_query = models.Topic.select()
    return jsonify(topics=[model_to_dict(t) for t in topic_query])


@API.get("/api/user-topics")
def get_user_topics():
    topics = request.args.getlist('topic')
    topic_query = models.Topic.select()

    if topics:
        topic_query = models.Topic.select().where(models.Topic.name << topics)

    query = (models.UserTopic.select()
                             .where(models.UserTopic.topic << topic_query))

    users_by_topic = defaultdict(list)
    for ut in query:
        users_by_topic[ut.topic.name].append(model_to_dict(ut.user))

    return jsonify(data=users_by_topic)

@API.route("/")
def index_rout():
    return render_template("index.html")