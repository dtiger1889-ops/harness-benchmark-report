"""
Word frequency analyzer.
Goal: read a text file provided as a command-line argument,
count word frequencies (case-insensitive, strip punctuation),
and print the top 10 most common words with their counts,
one per line in the format: "<count> <word>"

Usage: python main.py <path_to_text_file>
"""

import sys
import string
# TODO: add 'collections' import — Counter will be useful here


def load_text(filepath: str) -> str:
    # TODO: implement — open the file and return its contents as a string
    pass


def count_words(text: str) -> dict:
    # TODO: implement — normalize to lowercase, strip punctuation,
    # split on whitespace, and return a dict of {word: count}
    pass


def top_n(word_counts: dict, n: int = 10) -> list[tuple[str, int]]:
    # TODO: implement — return the n most common (word, count) pairs,
    # sorted by count descending
    pass


def main():
    if len(sys.argv) != 2:
        print("Usage: python main.py <textfile>")
        sys.exit(1)

    filepath = sys.argv[1]
    text = load_text(filepath)
    counts = count_words(text)
    top = top_n(counts)

    for word, count in top:
        print(f"{count} {word}")


if __name__ == "__main__":
    main()
