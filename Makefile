RAW_DIR = data/raw
PROCESSED_DIR = data/processed

C_FILE_OUT = recipe_matcher
C_FILE = scripts/recipe_matcher.c

RAW_DATA_SENTINEL = $(RAW_DIR)/.download_complete
PROCESSED_DATA_SENTINEL = $(PROCESSED_DIR)/.processed_complete

.PHONY: all setup data run test clean

all: setup
setup: .venv
	@echo ">>> Environment is set up. Activate with: source .venv/bin/activate"
.venv: pyproject.toml uv.lock
	@echo ">>> Creating virtual environment and installing dependencies..."
	uv venv
	uv sync
	@touch .venv

data: $(PROCESSED_DATA_SENTINEL)
	@echo ">>> All data (raw and processed) is ready in the data/ directory."
$(RAW_DATA_SENTINEL): scripts/download_data.sh
	@echo ">>> Ensuring raw data is downloaded and extracted..."
	@mkdir -p "$(RAW_DIR)"
	@bash scripts/download_data.sh
	@touch "$(RAW_DATA_SENTINEL)"
$(PROCESSED_DATA_SENTINEL): $(RAW_DATA_SENTINEL) scripts/process_data.py
	@echo ">>> Processing raw data into final databases..."
	@mkdir -p "$(PROCESSED_DIR)"
	uv run python scripts/process_data.py
	@touch "$(PROCESSED_DATA_SENTINEL)"

build: $(C_FILE)
	gcc -Wall -Wextra -O2 scripts/recipe_matcher.c -o $(C_FILE_OUT)

run:
	@echo ">>> Running the application..."
	uv run python -m src

test:
	@echo ">>> Running tests..."
	uv run pytest

clean:
	@echo ">>> Cleaning up project..."
	@rm -rf .venv __pycache__ */__pycache__ tests/__pycache__
	@rm -rf "$(RAW_DIR)" "$(PROCESSED_DIR)"
	@echo ">>> Cleanup complete."

