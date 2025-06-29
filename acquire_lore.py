import feedparser
import requests
import os
import whisper
import re
import time

# --- Configuration ---
# The RSS feed for the Lore podcast
RSS_URL = "https://feeds.libsyn.com/65267/rss"

# Where to save the downloaded files
AUDIO_DIR = "podcast_audio"
TRANSCRIPT_DIR = "lore_transcripts"  # This will be our high-quality 'case' data

# --- Setup ---
# Let's make sure our output directories exist
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)

whisper.models.download_model("medium")  # Ensure the Whisper model is downloaded
whisper.load_model("medium")  # Load the model into memory

def sanitize_filename(name):
    """
    Takes a string and returns a safe version for a filename.
    Removes illegal characters and limits length.
    """
    # Remove any character that isn't a letter, number, space, hyphen, or underscore
    clean_name = re.sub(r"[^\w\s-]", "", name)
    # Replace spaces with underscores
    clean_name = clean_name.replace(" ", "_")
    # Truncate to a reasonable length
    return clean_name[:150]


def download_episode(episode):
    """
    Downloads the MP3 for a single podcast episode if it doesn't already exist.
    """
    episode_title = episode.get("title", "Unknown_Episode")
    safe_title = sanitize_filename(episode_title)
    audio_filename = f"{safe_title}.mp3"
    audio_filepath = os.path.join(AUDIO_DIR, audio_filename)

    # 1. Check if we already have this audio file
    if os.path.exists(audio_filepath):
        print(f"  - Audio for '{episode_title}' already exists. Skipping download.")
        return audio_filepath  # Return the path so the transcriber can use it

    # 2. Find the audio URL in the RSS feed entry
    audio_url = None
    for link in episode.get("links", []):
        if link.get("type") == "audio/mpeg":
            audio_url = link.get("href")
            break

    if not audio_url:
        print(f"  - Could not find audio URL for '{episode_title}'. Skipping.")
        return None

    # 3. Download the file
    print(f"  - Downloading '{episode_title}'...")
    try:
        response = requests.get(audio_url, stream=True)
        response.raise_for_status()

        with open(audio_filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"  - Download complete.")
        return audio_filepath

    except requests.exceptions.RequestException as e:
        print(f"  - FAILED to download {episode_title}: {e}")
        return None


def transcribe_audio(audio_path, whisper_model):
    """
    Transcribes a single audio file using Whisper if the transcript doesn't exist.
    """
    if not audio_path:
        return

    # Create the name for the output text file
    base_filename = os.path.splitext(os.path.basename(audio_path))[0]
    transcript_filename = f"{base_filename}.txt"
    transcript_filepath = os.path.join(TRANSCRIPT_DIR, transcript_filename)

    # 1. Check if we already have the transcript
    if os.path.exists(transcript_filepath):
        print(
            f"  - Transcript for '{base_filename}' already exists. Skipping transcription."
        )
        return

    # 2. Transcribe the audio (this is the time-consuming part)
    print(f"  - Transcribing '{base_filename}'... (This will take a while)")
    try:
        result = whisper_model.transcribe(audio_path)
        transcript_text = result["text"]

        # 3. Save the transcript
        with open(transcript_filepath, "w", encoding="utf-8") as f:
            f.write(transcript_text)
        print(f"  - Transcription successful. Saved to '{transcript_filepath}'")

    except Exception as e:
        print(f"  - FAILED to transcribe {base_filename}: {e}")


def run_acquisition():
    """
    Main function to orchestrate the entire download and transcribe process.
    """
    print("--- Starting Lore Acquisition Protocol ---")

    # Load the Whisper model once at the beginning.
    # 'base' is a good balance. Use 'tiny' for speed, 'medium' for more accuracy.
    print("Loading Whisper model into memory... (This may take a moment)")
    try:
        model = whisper.load_model("base")
        print("Whisper model loaded.")
    except Exception as e:
        print(f"FATAL: Could not load Whisper model. Error: {e}")
        print(
            "Please ensure Whisper is installed correctly (`pip install openai-whisper`)."
        )
        return

    # Parse the RSS feed
    print(f"Parsing RSS feed from {RSS_URL}...")
    feed = feedparser.parse(RSS_URL)

    if not feed.entries:
        print("FATAL: Could not parse RSS feed or feed is empty.")
        return

    total_episodes = len(feed.entries)
    print(f"Found {total_episodes} episodes in the feed.")

    # Process each episode
    for i, entry in enumerate(feed.entries):
        print(f"\n--- Processing Episode {i+1} of {total_episodes} ---")

        # Step 1: Download the audio file
        audio_file_path = download_episode(entry)

        # Step 2: Transcribe the audio file
        transcribe_audio(audio_file_path, model)

        # It's good practice to pause briefly between big operations
        time.sleep(1)

    print("\n--- Lore Acquisition Protocol Complete ---")


if __name__ == "__main__":
    run_acquisition()
