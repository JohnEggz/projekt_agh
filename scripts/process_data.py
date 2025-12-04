import pandas as pd
import ast
import os
import re
import sys

instrukcja = """
Wypakuj zipa z instrukcjami w głównym folderze projektu (./food-com-recipes-and-user-interactions/)
Dla bezpieczeństwa nie zmieniaj nazwy folderu, bo jest .gitignore (jeśli chcesz zmienić to błagam dodaj go do gitignore)
Po wygenerowaniu nowych csvek, możesz usunąć to cały folder zo pobrałeś
"""
# ================= CONFIGURATION =================


SOURCE_DIR = "data/raw/"
OUTPUT_DIR = "data/processed/"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def get_path(filename):
    return os.path.join(SOURCE_DIR, filename)

# ================= PROCESSING =================

print(f"--- Starting Processing from {SOURCE_DIR} ---")

# 1. VALIDATE INPUT FILES
required_files = [
    'interactions_train.csv', 'interactions_test.csv', 'interactions_validation.csv',
    'RAW_recipes.csv', 'PP_recipes.csv'
]

for f in required_files:
    if not os.path.exists(get_path(f)):
        print(f"CRITICAL ERROR: Missing required file: {f}")
        print(instrukcja)
        sys.exit(1)

# 2. PROCESS INTERACTIONS
print("Loading and aggregating interactions...")
cols = ['user_id', 'recipe_id', 'rating']

train = pd.read_csv(get_path('interactions_train.csv'), usecols=cols)
test = pd.read_csv(get_path('interactions_test.csv'), usecols=cols)
val = pd.read_csv(get_path('interactions_validation.csv'), usecols=cols)

all_interactions = pd.concat([train, test, val])

# Calculate stats
interaction_stats = all_interactions.groupby('recipe_id')['rating'].agg(
    avg_rating='mean',
    review_count='count'
).reset_index()

# 3. PROCESS RECIPES
print("Loading and merging recipes...")

raw_recipes = pd.read_csv(get_path('RAW_recipes.csv'))
pp_recipes = pd.read_csv(get_path('PP_recipes.csv'), usecols=['id', 'calorie_level'])

# Merge datasets
recipes = raw_recipes.merge(pp_recipes, on='id', how='left')
recipes = recipes.merge(interaction_stats, left_on='id', right_on='recipe_id', how='left')

recipes['avg_rating'] = recipes['avg_rating'].fillna(0.0)
recipes['review_count'] = recipes['review_count'].fillna(0)

# 4. PARSE NUTRITION
print("Parsing nutrition data...")

def extract_nutrition(nut_str):
    try:
        return ast.literal_eval(nut_str)
    except:
        return [0]*7

nut_data = recipes['nutrition'].apply(extract_nutrition).tolist()
nut_df = pd.DataFrame(nut_data, columns=['cal', 'fat', 'sugar', 'sodium', 'prot', 'sat_fat', 'carbs'])

recipes = pd.concat([recipes, nut_df], axis=1)

# 5. FORMATTING AND CLEANUP
print("Cleaning text and formatting lists...")

def clean_spaces(text):
    if pd.isna(text): return ""
    return re.sub(r'\s+', ' ', str(text)).strip()

recipes['name'] = recipes['name'].apply(clean_spaces)
recipes['description'] = recipes['description'].apply(clean_spaces)

def clean_list_string(str_list):
    # Converts "['a', 'b']" -> "a;b"
    try:
        actual_list = ast.literal_eval(str_list)
        return ";".join([str(x).lower().strip() for x in actual_list])
    except:
        return ""

recipes['ingredients_serialized'] = recipes['ingredients'].apply(clean_list_string)
recipes['tags_serialized'] = recipes['tags'].apply(clean_list_string)
recipes['name_clean'] = recipes['name'].astype(str).str.replace(';', '').str.replace(',', '')

# 6. EXPORT
print("Sorting and Exporting...")

# Sort by popularity (descending)
recipes.sort_values(by='review_count', ascending=False, inplace=True)

# Dataset A: Search DB (optimized for C)
search_columns = [
    'id', 'avg_rating', 'review_count', 'minutes', 
    'cal', 'prot', 'fat', 
    'name_clean', 'ingredients_serialized', 'tags_serialized'
]

recipes[search_columns].to_csv(
    os.path.join(OUTPUT_DIR, 'search_db.csv'), 
    index=False, 
    encoding='utf-8'
)

# Dataset B: Display DB (full text)
display_columns = ['id', 'name', 'description', 'steps', 'ingredients']

recipes[display_columns].to_csv(
    os.path.join(OUTPUT_DIR, 'display_db.csv'), 
    index=False, 
    encoding='utf-8'
)

print(f"SUCCESS! Output generated in {OUTPUT_DIR}")
