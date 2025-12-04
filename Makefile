# --- Configuration Variables ---
# Directories for raw and processed data
RAW_DIR = data/raw
PROCESSED_DIR = data/processed

# Sentinel files to mark completion of download and processing steps
RAW_DATA_SENTINEL = $(RAW_DIR)/.download_complete
PROCESSED_DATA_SENTINEL = $(PROCESSED_DIR)/.processed_complete

# --- Phony Targets ---
# .PHONY targets are not actual files; always execute the rule.
.PHONY: all setup data run test clean

# --- Default Target ---
# Runs 'setup' when 'make' is executed without arguments.
all: setup

# --- Setup Environment ---
# Creates a Python virtual environment and installs dependencies.
# The .venv target ensures this is only done once or if dependencies change.
setup: .venv
	@echo ">>> Environment is set up. Activate with: source .venv/bin/activate"

# Rule to create and sync the virtual environment using 'uv'.
# 'make' automatically manages re-running this if pyproject.toml or uv.lock change.
.venv: pyproject.toml uv.lock
	@echo ">>> Creating virtual environment and installing dependencies..."
	uv venv
	uv sync
	@touch .venv # Marks the .venv directory as up-to-date for 'make'

# --- Data Pipeline ---
# Main target to ensure all data (raw and processed) is ready.
data: $(PROCESSED_DATA_SENTINEL)
	@echo ">>> All data (raw and processed) is ready in the data/ directory."

# Rule to download and extract raw data.
# Depends on 'scripts/download_data.sh'. Creates a sentinel file upon success.
$(RAW_DATA_SENTINEL): scripts/download_data.sh
	@echo ">>> Ensuring raw data is downloaded and extracted..."
	@mkdir -p "$(RAW_DIR)"
	@bash scripts/download_data.sh
	@touch "$(RAW_DATA_SENTINEL)"

# Rule to process raw data.
# Depends on the raw data being available and the processing script.
# Creates a sentinel file upon success.
$(PROCESSED_DATA_SENTINEL): $(RAW_DATA_SENTINEL) scripts/process_data.py
	@echo ">>> Processing raw data into final databases..."
	@mkdir -p "$(PROCESSED_DIR)"
	uv run python scripts/process_data.py
	@touch "$(PROCESSED_DATA_SENTINEL)"

# --- Run Application ---
# Executes the main Python application.
run:
	@echo ">>> Running the application..."
	uv run python -m src

# --- Run Tests ---
# Executes the test suite.
test:
	@echo ">>> Running tests..."
	uv run pytest

# --- Cleanup ---
# Removes all generated files and directories.
clean:
	@echo ">>> Cleaning up project..."
	@rm -rf .venv __pycache__ */__pycache__ tests/__pycache__
	@rm -rf "$(RAW_DIR)" "$(PROCESSED_DIR)"
	@echo ">>> Cleanup complete."
