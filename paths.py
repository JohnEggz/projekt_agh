import os
CACHE_PATH = os.path.abspath("./.cache")
SEARCH_CSV = os.path.abspath("./data/processed/search_db.csv")
DISPLAY_CSV = os.path.abspath("./data/processed/display_db.csv")

INGRIDIENTS_TRIE = os.path.join(CACHE_PATH, "ingredients_trie.json")
RECIPES_FOUND = os.path.join(CACHE_PATH, "recipes_found.json")
USER_OUTPUT = os.path.join(CACHE_PATH, "input.json")

