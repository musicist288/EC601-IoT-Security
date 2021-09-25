"""
    Utilities to wrap the google cloud API for the actions
    performed in this repository.
"""
import enum
from google.cloud import language_v1

CLIENT = language_v1.LanguageServiceClient()

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


def get_sentiment_analysis(text: str):
    """
        Perform a sentiment analysis on a string of text
    """
    document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)
    sentiment = CLIENT.analyze_sentiment(request={'document': document}).document_sentiment
    return sentiment
