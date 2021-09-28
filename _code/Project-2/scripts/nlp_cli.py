from argparse import ArgumentParser
from google.api_core.exceptions import InvalidArgument
from ec601_proj2.google_nlp import LanguageClient

def cli_main():
    parser = ArgumentParser()
    subparsers = parser.add_subparsers()

    default_help = "The text to analyze"
    commands = (
        ("sentiment", LanguageClient.analyze_sentiment, default_help),
        ("entities", LanguageClient.analyze_entities, default_help),
        ("entity-sentiment", LanguageClient.analyze_entity_sentiment, default_help),
        ("classify", LanguageClient.classify_text, "The text to classify.")
    )

    for name, func, help_text in commands:
        cmd_parser = subparsers.add_parser(name)
        cmd_parser.set_defaults(func=func)
        cmd_parser.add_argument("text", help=help_text)

    args = parser.parse_args()
    try:
        print(args.func(args.text))
    except InvalidArgument as err:
        if err.code == 400:
            print(f"Error: {err.message}")

if __name__ == "__main__":
    cli_main()
