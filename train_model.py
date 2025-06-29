import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib  # This library is for saving our trained model

# --- Configuration ---
TRAINING_DATA_DIR = "training_data"
MODEL_OUTPUT_FILE = "hunter_model.joblib"


def load_data(data_dir):
    """
    Loads text files from the 'case' and 'not_a_case' subdirectories.
    """
    texts = []
    labels = []

    # Walk through the directory structure
    for category in os.listdir(data_dir):
        category_path = os.path.join(data_dir, category)
        if os.path.isdir(category_path):
            print(f"Loading files from category: '{category}'")
            for filename in os.listdir(category_path):
                filepath = os.path.join(category_path, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        texts.append(f.read())
                        labels.append(category)
                except Exception as e:
                    print(f"  Could not read file {filepath}: {e}")

    print(f"\nLoaded a total of {len(texts)} documents.")
    return texts, labels


def train_hunter_model():
    """
    The main function to load data, train the model, and save it.
    """
    # 1. Load our meticulously sorted data
    texts, labels = load_data(TRAINING_DATA_DIR)

    if not texts:
        print("No training data found. Aborting.")
        return

    # 2. Split the data. We'll train on 80% and test on the remaining 20%
    # This lets us see how well our model performs on data it's never seen before.
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )
    print(
        f"Split data into {len(X_train)} training samples and {len(X_test)} testing samples."
    )

    # 3. Create the model pipeline. This is our "rookie hunter."
    # TfidfVectorizer: Converts text into numerical features.
    # MultinomialNB: A classic, fast, and effective text classification algorithm.
    model = make_pipeline(TfidfVectorizer(stop_words="english"), MultinomialNB())
    print("\nTraining the model... (This may take a moment depending on data size)")

    # 4. Train the model on our training data. This is the learning process.
    model.fit(X_train, y_train)
    print("Training complete.")

    # 5. Evaluate the model. Let's see how well it did on the test data.
    print("\n--- Model Performance Report ---")
    predictions = model.predict(X_test)
    print(classification_report(y_test, predictions))
    print("---------------------------------")

    # 6. Save the trained model to a file.
    # This is like bottling the ghost. We can now load this file in our main app.
    joblib.dump(model, MODEL_OUTPUT_FILE)
    print(f"\nModel successfully forged and saved to '{MODEL_OUTPUT_FILE}'")
    print("This file contains the hunter's 'instinct'. Keep it safe.")


if __name__ == "__main__":
    train_hunter_model()
