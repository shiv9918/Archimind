import os


def add(a, b):
    return a + b


def slugify(text):
    return text.lower().replace(" ", "-")


def data_dir() -> str:
    return os.getcwd()
