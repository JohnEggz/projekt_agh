set -e
DATASET_URL="https://www.kaggle.com/api/v1/datasets/download/shuyangli94/food-com-recipes-and-user-interactions"
RAW_DIR="data/raw"
ZIP_FILENAME="food-com-recipes-and-user-interactions.zip"
ZIP_FILE_PATH="$RAW_DIR/$ZIP_FILENAME"
EXTRACTED_SUBDIR="food-com-recipes-and-user-interactions"
INTERMEDIATE_DIR="$RAW_DIR/$EXTRACTED_SUBDIR"

echo "--- Data Download & Extraction ---"
mkdir -p "$RAW_DIR"
echo "Ensured data directory '$RAW_DIR' exists."
if [ ! -f "$ZIP_FILE_PATH" ]; then
    echo "Downloading dataset from Kaggle to '$ZIP_FILE_PATH'..."
    echo "NOTE: Kaggle downloads often require authentication."
    echo "If 'curl' fails, ensure you are logged into Kaggle in your browser"
    echo "or consider using the Kaggle API client (pip install kaggle) and"
    echo "setting up credentials (~/.kaggle/kaggle.json)."
    curl -L "$DATASET_URL" -o "$ZIP_FILE_PATH"
else
    echo "Zip file '$ZIP_FILENAME' already exists at '$ZIP_FILE_PATH'. Skipping download."
fi
if [ -f "$ZIP_FILE_PATH" ]; then
    echo "Extracting '$ZIP_FILENAME' to '$RAW_DIR'..."
    unzip -o "$ZIP_FILE_PATH" -d "$RAW_DIR"
    if [ -d "$INTERMEDIATE_DIR" ] && [ "$(ls -A "$INTERMEDIATE_DIR")" ]; then
        echo "Intermediate directory '$INTERMEDIATE_DIR' found."
        echo "Moving contents to '$RAW_DIR'..."
        mv "$INTERMEDIATE_DIR"/* "$RAW_DIR"/
        rmdir "$INTERMEDIATE_DIR"
        echo "Cleaned up intermediate directory."
    else
        echo "No intermediate directory '$INTERMEDIATE_DIR' found or it was empty."
        echo "Assuming dataset files were extracted directly into '$RAW_DIR'."
    fi
    echo "Removing '$ZIP_FILE_PATH'..."
    rm "$ZIP_FILE_PATH"
else
    echo "Zip file '$ZIP_FILE_PATH' not found, skipping extraction and cleanup."
fi

echo "--- Data Download & Extraction Complete ---"
