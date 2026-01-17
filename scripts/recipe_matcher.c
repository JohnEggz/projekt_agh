#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_LINE 16384
#define MAX_INGREDIENTS 100
#define MAX_NAME 256

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

int contains_ingredient(char **ingredients, int count, const char *search) {
  for (int i = 0; i < count; i++) {
    if (strcasestr(ingredients[i], search) != NULL) {
      return 1;
    }
  }
  return 0;
}

float calculate_accuracy(Recipe *recipe, Preferences *prefs) {
  float score = 0.0;
  int total_criteria = 0;

  // Sprawdź czas przygotowania (min i max)
  total_criteria++;
  if (recipe->minutes >= prefs->minutes_min &&
      recipe->minutes <= prefs->minutes_max) {
    score += 1.0;
  }

  // Sprawdź kalorie (min i max)
  total_criteria++;
  if (recipe->cal >= prefs->cal_min && recipe->cal <= prefs->cal_max) {
    score += 1.0;
  }

  // Sprawdź tłuszcz (min i max)
  total_criteria++;
  if (recipe->fat >= prefs->fat_min && recipe->fat <= prefs->fat_max) {
    score += 1.0;
  }

  // Sprawdź białko (min i max)
  total_criteria++;
  if (recipe->prot >= prefs->prot_min && recipe->prot <= prefs->prot_max) {
    score += 1.0;
  }

  // Sprawdź ocenę (min i max)
  total_criteria++;
  if (recipe->avg_rating >= prefs->rating_min &&
      recipe->avg_rating <= prefs->rating_max) {
    score += 1.0;
  }

  // Sprawdź lubiane składniki
  if (prefs->liked_count > 0) {
    total_criteria += prefs->liked_count;
    for (int i = 0; i < prefs->liked_count; i++) {
      if (contains_ingredient(recipe->ingredients, recipe->ingredients_count,
                              prefs->ingredients_liked[i])) {
        score += 1.0;
      }
    }
  }

  // Sprawdź nielubiane składniki (odejmij punkty)
  if (prefs->disliked_count > 0) {
    total_criteria += prefs->disliked_count;
    for (int i = 0; i < prefs->disliked_count; i++) {
      if (!contains_ingredient(recipe->ingredients, recipe->ingredients_count,
                               prefs->ingredients_disliked[i])) {
        score += 1.0;
      }
    }
  }

  return total_criteria > 0 ? score / total_criteria : 0.0;
}

void parse_preferences(const char *filename, Preferences *prefs) {
  FILE *f = fopen(filename, "r");
  if (!f) {
    fprintf(stderr, "Nie można otworzyć pliku preferencji: %s\n", filename);
    perror("Szczegóły błędu");
    exit(1);
  }

  char line[MAX_LINE];
  prefs->liked_count = 0;
  prefs->disliked_count = 0;
  prefs->ingredients_liked = malloc(MAX_INGREDIENTS * sizeof(char *));
  prefs->ingredients_disliked = malloc(MAX_INGREDIENTS * sizeof(char *));

  // Ustaw domyślne wartości
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
    char *val_start = NULL;
    char *colon = strchr(line, ':');

    if (colon) {
      val_start = colon + 1;
      while (*val_start && isspace((unsigned char)*val_start))
        val_start++;
      if (*val_start == '"')
        val_start++;
    }

    // Parsuj wartości liczbowe
    if (strstr(line, "\"cal_max\"") && val_start) {
      prefs->cal_max = atof(val_start);
    } else if (strstr(line, "\"cal_min\"") && val_start) {
      prefs->cal_min = atof(val_start);
    } else if (strstr(line, "\"fat_max\"") && val_start) {
      prefs->fat_max = atof(val_start);
    } else if (strstr(line, "\"fat_min\"") && val_start) {
      prefs->fat_min = atof(val_start);
    } else if (strstr(line, "\"prot_max\"") && val_start) {
      prefs->prot_max = atof(val_start);
    } else if (strstr(line, "\"prot_min\"") && val_start) {
      prefs->prot_min = atof(val_start);
    } else if (strstr(line, "\"minutes_max\"") && val_start) {
      prefs->minutes_max = atoi(val_start);
    } else if (strstr(line, "\"minutes_min\"") && val_start) {
      prefs->minutes_min = atoi(val_start);
    } else if (strstr(line, "\"rating_max\"") && val_start) {
      prefs->rating_max = atof(val_start);
    } else if (strstr(line, "\"rating_min\"") && val_start) {
      prefs->rating_min = atof(val_start);
    } else if (strstr(line, "\"recipe_name\"")) {
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

  printf("✓ Wczytano preferencje:\n");
  printf("  Kalorie: %.0f - %.0f\n", prefs->cal_min, prefs->cal_max);
  printf("  Tłuszcz: %.0f - %.0f\n", prefs->fat_min, prefs->fat_max);
  printf("  Białko: %.0f - %.0f\n", prefs->prot_min, prefs->prot_max);
  printf("  Czas: %d - %d min\n", prefs->minutes_min, prefs->minutes_max);
  printf("  Ocena: %.1f - %.1f\n", prefs->rating_min, prefs->rating_max);
  printf("  Lubiane składniki: %d\n", prefs->liked_count);
  printf("  Nielubiane składniki: %d\n", prefs->disliked_count);
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
  if (argc != 4) {
    printf("Użycie: %s <plik_preferencji.json> <plik_przepisow.csv> "
           "<plik_wynikowy.json>\n",
           argv[0]);
    return 1;
  }

  Preferences prefs;
  parse_preferences(argv[1], &prefs);

  FILE *csv = fopen(argv[2], "r");
  if (!csv) {
    fprintf(stderr, "Nie można otworzyć pliku CSV: %s\n", argv[2]);
    perror("Szczegóły błędu");
    return 1;
  }
  printf("✓ Pomyślnie otwarto plik CSV: %s\n", argv[2]);

  int recipe_capacity = 1000;
  Recipe *recipes = malloc(recipe_capacity * sizeof(Recipe));
  int recipe_count = 0;

  char line[MAX_LINE];
  fgets(line, sizeof(line), csv); // Pomiń nagłówek

  while (fgets(line, sizeof(line), csv)) {
    // Zwiększ pojemność tablicy jeśli potrzeba
    if (recipe_count >= recipe_capacity) {
      recipe_capacity *= 2;
      recipes = realloc(recipes, recipe_capacity * sizeof(Recipe));
      if (!recipes) {
        fprintf(stderr, "Błąd alokacji pamięci\n");
        fclose(csv);
        return 1;
      }
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
    r->accuracy = calculate_accuracy(r, &prefs);

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

  // Cleanup
  for (int i = 0; i < recipe_count; i++) {
    free_string_array(recipes[i].ingredients, recipes[i].ingredients_count);
    free_string_array(recipes[i].tags, recipes[i].tags_count);
  }
  free(recipes);
  free_string_array(prefs.ingredients_liked, prefs.liked_count);
  free_string_array(prefs.ingredients_disliked, prefs.disliked_count);

  return 0;
}
