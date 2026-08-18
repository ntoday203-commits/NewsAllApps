"""Entry point: run the Google News -> Gemini summary -> JSON pipeline."""

from dotenv import load_dotenv

from src.processor import run_pipeline
from src.utils import setup_logging


def main() -> None:
    load_dotenv()
    setup_logging()
    run_pipeline()


if __name__ == "__main__":
    main()
