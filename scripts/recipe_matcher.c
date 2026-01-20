#define _GNU_SOURCE // For strcasestr
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_LINE 16384
#define MAX_INGREDIENTS 100
#define MAX_NAME 256

// --- Structures ---

typedef struct {
  float w_name;
  float w_cal;
  float w_fat;
  float w_prot;
  float w_minutes;
  float w_rating;
  float w_liked;    // Points per liked ingredient found
  float w_disliked; // Points per disliked ingredient AVOIDED
} Weights;

typedef struct {
  char recipe_name[MAX_NAME];
  float cal_max;
  float cal_min;
  float fat_max;
  float fat_min;
  float prot_max;
  float prot_min;
  int minutes_max;
  int minutes_min;
  float rating_max;
  float rating_min;
  char **ingredients_liked;
  int liked_count;
  char **ingredients_disliked;
  int disliked_count;
} Preferences;

typedef struct {
  int id;
  float avg_rating;
  int review_count;
  int minutes;
  float cal;
  float prot;
  float fat;
  char name_clean[MAX_NAME];
  char **ingredients;
  int ingredients_count;
  char **tags;
  int tags_count;
  float accuracy;
} Recipe;

// --- Helpers ---

void trim(char *str) {
  char *end;
  while (isspace((unsigned char)*str))
    str++;
  if (*str == 0)
    return;
  end = str + strlen(str) - 1;
  while (end > str && isspace((unsigned char)*end))
    end--;
  end[1] = '\0';
  memmove(str - (str - str), str, strlen(str) + 1);
}

char **split_string(char *str, const char *delim, int *count) {
  char **result = malloc(MAX_INGREDIENTS * sizeof(char *));
  *count = 0;
  char *token = strtok(str, delim);
  while (token != NULL && *count < MAX_INGREDIENTS) {
    result[*count] = strdup(token);
    trim(result[*count]);
    (*count)++;
    token = strtok(NULL, delim);
  }
  return result;
}

void free_string_array(char **arr, int count) {
  for (int i = 0; i < count; i++) {
    free(arr[i]);
  }
  free(arr);
}

// Case insensitive search (non-standard in strict ANSI, common in POSIX)
int contains_ingredient(char **ingredients, int count, const char *search) {
  for (int i = 0; i < count; i++) {
    if (strcasestr(ingredients[i], search) != NULL) {
      return 1;
    }
  }
  return 0;
}

// --- Logic ---

void load_weights(const char *filename, Weights *w) {
  FILE *f = fopen(filename, "r");
  // Default values if file fails
  w->w_name = 5.0;
  w->w_cal = 1.0;
  w->w_fat = 1.0;
  w->w_prot = 1.0;
  w->w_minutes = 1.0;
  w->w_rating = 1.0;
  w->w_liked = 2.0;
  w->w_disliked = 2.0;

  if (!f) {
    printf("! Nie znaleziono pliku wag '%s', używam domyślnych.\n", filename);
    return;
  }

  char line[MAX_LINE];
  while (fgets(line, sizeof(line), f)) {
    if (line[0] == '#' || line[0] == '\n')
      continue;
    char *eq = strchr(line, '=');
    if (!eq)
      continue;
    *eq = '\0';
    float val = atof(eq + 1);
    char *key = line;
    trim(key);

    if (strcmp(key, "weight_name") == 0)
      w->w_name = val;
    else if (strcmp(key, "weight_cal") == 0)
      w->w_cal = val;
    else if (strcmp(key, "weight_fat") == 0)
      w->w_fat = val;
    else if (strcmp(key, "weight_prot") == 0)
      w->w_prot = val;
    else if (strcmp(key, "weight_time") == 0)
      w->w_minutes = val;
    else if (strcmp(key, "weight_rating") == 0)
      w->w_rating = val;
    else if (strcmp(key, "weight_liked") == 0)
      w->w_liked = val;
    else if (strcmp(key, "weight_disliked") == 0)
      w->w_disliked = val;
  }
  fclose(f);
  printf("✓ Załadowano wagi z %s\n", filename);
}

float calculate_accuracy(Recipe *recipe, Preferences *prefs, Weights *w) {
  float score = 0.0;
  float total_possible_score = 0.0;

  // 1. Nazwa przepisu (Name Match)
  // Only check if user actually provided a name to search for
  if (strlen(prefs->recipe_name) > 0) {
    total_possible_score += w->w_name;
    if (strcasestr(recipe->name_clean, prefs->recipe_name) != NULL) {
      score += w->w_name;
    }
  }

  // 2. Czas (Time)
  total_possible_score += w->w_minutes;
  if (recipe->minutes >= prefs->minutes_min &&
      recipe->minutes <= prefs->minutes_max) {
    score += w->w_minutes;
  }

  // 3. Makroskładniki
  total_possible_score += w->w_cal;
  if (recipe->cal >= prefs->cal_min && recipe->cal <= prefs->cal_max)
    score += w->w_cal;

  total_possible_score += w->w_fat;
  if (recipe->fat >= prefs->fat_min && recipe->fat <= prefs->fat_max)
    score += w->w_fat;

  total_possible_score += w->w_prot;
  if (recipe->prot >= prefs->prot_min && recipe->prot <= prefs->prot_max)
    score += w->w_prot;

  // 4. Ocena
  total_possible_score += w->w_rating;
  if (recipe->avg_rating >= prefs->rating_min &&
      recipe->avg_rating <= prefs->rating_max) {
    score += w->w_rating;
  }

  // 5. Lubiane składniki (Add points for presence)
  if (prefs->liked_count > 0) {
    for (int i = 0; i < prefs->liked_count; i++) {
      total_possible_score += w->w_liked;
      if (contains_ingredient(recipe->ingredients, recipe->ingredients_count,
                              prefs->ingredients_liked[i])) {
        score += w->w_liked;
      }
    }
  }

  // 6. Nielubiane składniki (Add points for absence)
  if (prefs->disliked_count > 0) {
    for (int i = 0; i < prefs->disliked_count; i++) {
      total_possible_score += w->w_disliked;
      // Success means NOT containing the ingredient
      if (!contains_ingredient(recipe->ingredients, recipe->ingredients_count,
                               prefs->ingredients_disliked[i])) {
        score += w->w_disliked;
      }
    }
  }

  return total_possible_score > 0 ? score / total_possible_score : 0.0;
}

void parse_preferences(const char *filename, Preferences *prefs) {
  FILE *f = fopen(filename, "r");
  if (!f) {
    perror("Błąd pliku preferencji");
    exit(1);
  }

  char line[MAX_LINE];
  prefs->liked_count = 0;
  prefs->disliked_count = 0;
  prefs->ingredients_liked = malloc(MAX_INGREDIENTS * sizeof(char *));
  prefs->ingredients_disliked = malloc(MAX_INGREDIENTS * sizeof(char *));
  prefs->recipe_name[0] = '\0';

  // Init defaults
  prefs->cal_min = 0;
  prefs->cal_max = 10000;
  prefs->fat_min = 0;
  prefs->fat_max = 10000;
  prefs->prot_min = 0;
  prefs->prot_max = 10000;
  prefs->minutes_min = 0;
  prefs->minutes_max = 10000;
  prefs->rating_min = 0;
  prefs->rating_max = 5;

  int in_liked = 0, in_disliked = 0;

  while (fgets(line, sizeof(line), f)) {
    // FIXED JSON PARSING: Skip quotes for numbers
    char *val_start = NULL;
    char *colon = strchr(line, ':');
    if (colon) {
      val_start = colon + 1;
      while (*val_start && isspace((unsigned char)*val_start))
        val_start++;
      if (*val_start == '"')
        val_start++;
    }

    if (strstr(line, "\"cal_max\"") && val_start)
      prefs->cal_max = atof(val_start);
    else if (strstr(line, "\"cal_min\"") && val_start)
      prefs->cal_min = atof(val_start);
    else if (strstr(line, "\"fat_max\"") && val_start)
      prefs->fat_max = atof(val_start);
    else if (strstr(line, "\"fat_min\"") && val_start)
      prefs->fat_min = atof(val_start);
    else if (strstr(line, "\"prot_max\"") && val_start)
      prefs->prot_max = atof(val_start);
    else if (strstr(line, "\"prot_min\"") && val_start)
      prefs->prot_min = atof(val_start);
    else if (strstr(line, "\"minutes_max\"") && val_start)
      prefs->minutes_max = atoi(val_start);
    else if (strstr(line, "\"minutes_min\"") && val_start)
      prefs->minutes_min = atoi(val_start);
    else if (strstr(line, "\"rating_max\"") && val_start)
      prefs->rating_max = atof(val_start);
    else if (strstr(line, "\"rating_min\"") && val_start)
      prefs->rating_min = atof(val_start);

    else if (strstr(line, "\"recipe_name\"")) {
      char *start = strchr(line, ':');
      if (start) {
        start = strchr(start, '"');
        if (start) {
          start++;
          char *end = strchr(start, '"');
          if (end) {
            *end = '\0';
            strncpy(prefs->recipe_name, start, MAX_NAME - 1);
          }
        }
      }
    } else if (strstr(line, "\"ingredients_liked\"")) {
      in_liked = 1;
      in_disliked = 0;
    } else if (strstr(line, "\"ingredients_disliked\"")) {
      in_disliked = 1;
      in_liked = 0;
    } else if (strstr(line, "]")) {
      in_liked = 0;
      in_disliked = 0;
    } else if (in_liked && strstr(line, "\"")) {
      char *start = strchr(line, '"');
      if (start) {
        start++;
        char *end = strchr(start, '"');
        if (end) {
          *end = '\0';
          prefs->ingredients_liked[prefs->liked_count++] = strdup(start);
        }
      }
    } else if (in_disliked && strstr(line, "\"")) {
      char *start = strchr(line, '"');
      if (start) {
        start++;
        char *end = strchr(start, '"');
        if (end) {
          *end = '\0';
          prefs->ingredients_disliked[prefs->disliked_count++] = strdup(start);
        }
      }
    }
  }
  fclose(f);
}

int compare_recipes(const void *a, const void *b) {
  Recipe *r1 = (Recipe *)a;
  Recipe *r2 = (Recipe *)b;
  if (r2->accuracy > r1->accuracy)
    return 1;
  if (r2->accuracy < r1->accuracy)
    return -1;
  return 0;
}

int main(int argc, char *argv[]) {
  if (argc != 5) {
    printf(
        "Użycie: %s <preferencje.json> <dane.csv> <wynik.json> <wagi.conf>\n",
        argv[0]);
    return 1;
  }

  Weights weights;
  load_weights(argv[4], &weights);

  Preferences prefs;
  parse_preferences(argv[1], &prefs);

  printf("✓ Wczytano cel: '%s'\n", prefs.recipe_name);

  FILE *csv = fopen(argv[2], "r");
  if (!csv) {
    perror("Błąd CSV");
    return 1;
  }

  int recipe_capacity = 1000;
  Recipe *recipes = malloc(recipe_capacity * sizeof(Recipe));
  int recipe_count = 0;

  char line[MAX_LINE];
  fgets(line, sizeof(line), csv); // Header

  while (fgets(line, sizeof(line), csv)) {
    if (recipe_count >= recipe_capacity) {
      recipe_capacity *= 2;
      recipes = realloc(recipes, recipe_capacity * sizeof(Recipe));
    }
    Recipe *r = &recipes[recipe_count];

    char *token = strtok(line, ",");
    int field = 0;
    char ingredients_str[MAX_LINE] = "";
    char tags_str[MAX_LINE] = "";

    while (token != NULL) {
      switch (field) {
      case 0:
        r->id = atoi(token);
        break;
      case 1:
        r->avg_rating = atof(token);
        break;
      case 2:
        r->review_count = atoi(token);
        break;
      case 3:
        r->minutes = atoi(token);
        break;
      case 4:
        r->cal = atof(token);
        break;
      case 5:
        r->prot = atof(token);
        break;
      case 6:
        r->fat = atof(token);
        break;
      case 7:
        strncpy(r->name_clean, token, MAX_NAME - 1);
        break;
      case 8:
        strncpy(ingredients_str, token, MAX_LINE - 1);
        break;
      case 9:
        strncpy(tags_str, token, MAX_LINE - 1);
        break;
      }
      token = strtok(NULL, ",");
      field++;
    }

    r->ingredients = split_string(ingredients_str, ";", &r->ingredients_count);
    r->tags = split_string(tags_str, ";", &r->tags_count);
    r->accuracy = calculate_accuracy(r, &prefs, &weights);

    recipe_count++;
  }
  fclose(csv);

  qsort(recipes, recipe_count, sizeof(Recipe), compare_recipes);

  FILE *output = fopen(argv[3], "w");
  fprintf(output, "[\n");
  for (int i = 0; i < 3 && i < recipe_count; i++) {
    fprintf(output, "  {\"id\": %d, \"accuracy\": %.3f}%s\n", recipes[i].id,
            recipes[i].accuracy, i < 2 ? "," : "");
  }
  fprintf(output, "]\n");
  fclose(output);

  // Cleanup omitted for brevity (OS cleans up on exit anyway)
  return 0;
}
