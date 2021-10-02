"""
    Utilities to wrap the google cloud API for the actions
    performed in this repository.
"""
import enum
from functools import wraps

#pylint: disable=unused-import
from google.api_core.exceptions import InvalidArgument

#pylint: disable=unused-import
from google.cloud.language_v1.types.language_service import (
    Entity,
    ClassificationCategory
)
from google.cloud import language_v1

from dotenv import load_dotenv

load_dotenv()

def format_request(text, language="en"):
    """
        Helper function to format a request object to make a
        Google NLP query.
    """
    document = language_v1.Document(content=text,
                                    type_=language_v1.Document.Type.PLAIN_TEXT,
                                    language=language)
    return dict(document=document)


def text_api(func):
    @wraps(func)
    def inner(self, text, *args, **kwargs):
        return func(self, format_request(text), *args, **kwargs)
    return inner


def textapis(apis_to_wrap):
    """
        I'm restricting my use cases to plain-text english documents, this class
        decorator is used to wrap all the client APIs so I can pass in a string of
        text to call them instead of having to prepare the reqest for all of them.
    """
    def wrapper(cls):
        for func in apis_to_wrap:
            wrapped = text_api(getattr(language_v1.LanguageServiceClient, func))
            setattr(cls, func, wrapped)
        return cls
    return wrapper


@textapis([
    "analyze_sentiment",
    "analyze_entity_sentiment",
    "analyze_entities",
    "classify_text"
])
class EnglishTextLanguageClientService(language_v1.LanguageServiceClient):
    pass


LanguageClient = EnglishTextLanguageClientService()

class SentimentCategory(enum.IntEnum):
    """
        Categories for sentiment analysis
    """
    NEGATIVE = 0
    POSITIVE = 1
    NEUTRAL = 2
    MIXED = 3


def categorize_sentiment(sentiment):
    """
        Sentiment analysis categorized by the char on this page:
        https://cloud.google.com/natural-language/docs/basics#interpreting_sentiment_analysis_values
    """
    score = sentiment.score
    magnitude = sentiment.magnitude

    if  magnitude < 1:
        return SentimentCategory.NEUTRAL

    if -0.5 < score < 0.5:
        return SentimentCategory.MIXED

    if score < -0.5 and magnitude > 1:
        return SentimentCategory.NEGATIVE

    if score > 0.5 and magnitude > 1:
        return SentimentCategory.POSITIVE

    print("Warning: returning neutral sentiment because the score and magnitude did not" +
         f" fit any above criteria: Score: {score}, Magnitude: {magnitude}")

    return SentimentCategory.NEUTRAL

def choose_category(categories):
    if not categories:
        return None

    confidences = [cat.confidence for cat in categories]
    max_conf = max(confidences)
    index = confidences.index(max_conf)
    return categories[index]
