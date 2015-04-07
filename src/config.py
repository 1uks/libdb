from os import path


PROJECT_DIR = path.dirname(path.realpath(__file__))
LIBRARY_DIR = path.join(PROJECT_DIR, "libs")
CONNECTION_STRING = "sqlite:///db.sqlite"
