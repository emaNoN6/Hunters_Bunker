# ==========================================================
# Hunter's Command Console - Master Acquisition Script
# Target: Unexplained Podcast (via Pocket Casts JSON Feed)
# v6.0 - Definitive version using innerHTML for robust parsing
# ==========================================================

# ----------------------------------------------------------
# STAGE 1: ENVIRONMENT SETUP
# ----------------------------------------------------------
import sys
import os
import requests
import re
import json


# ----------------------------------------------------------
# STAGE 2: MISSION CONFIGURATION
# ----------------------------------------------------------
JSON_FEED_URL = "https://podcasts.pocketcasts.com/f96fb8d0-a70d-0133-2dfa-6dc413d6d41d/episodes_full_1751585827.json"
TRANSCRIPT_DIR = 'g:/My Drive/Unexplained_Transcripts'
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
TEMP_AUDIO_DIR = '/content/temp_audio'
os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)

print("\n--- BEGINNING ACQUISITION: UNEXPLAINED (SELENIUM PROTOCOL) ---")

print(f"Deploying Selenium agent to fetch master episode list...")
driver = None # Initialize driver to None
episodes = [] # Initialize episodes list

response = requests.get(JSON_FEED_URL)
if response.status_code != 200:
    sys.exit(f"FATAL: Failed to fetch JSON feed. Status code: {response.status_code}")

json_response = response.json()
if not json_response:
    sys.exit("FATAL: Received empty JSON feed. Aborting mission.")

json_text = json.dumps(json_response, indent=2)
if not json_text:
    sys.exit("FATAL: Failed to convert JSON response to text. Aborting mission.")

print("Selenium agent successfully fetched the raw JSON feed.")
print(f"Raw data length: {len(json_text)} characters.")
    
# Parse the text we extracted
podcast_data = json.loads(json_text)
print(f"JSON feed parsed successfully. Type: {type(podcast_data)}")
podcast = podcast_data.get('podcast', {})
episodes = podcast.get('episodes', [])
print(f"Successfully parsed JSON.\r\nExpected {podcast_data.get("episode_count")}, found {len(episodes)} episodes.")

if not episodes:
        print("WARNING: Parsed episode list is empty. The JSON structure may have changed.")
        sys.exit("Aborting mission: No targets found.")

existing_count = 0
existing_transcripts = set()
new_count = 0
error_count = 0
missing_count = 0

# --- The rest of the script (downloading/transcribing) remains the same ---
# Process each episode in the feed.
for i, episode in enumerate(episodes):
    temp_audio_path = None
    try:
        episode_title = episode.get('title', 'Unknown_Episode')
        episode_url = episode.get('url')
        
        safe_title = re.sub(r'[^\w\s-]', '', episode_title).replace(' ', '_')
        transcript_filename = f"{safe_title}.txt"
        transcript_filepath = os.path.join(TRANSCRIPT_DIR, transcript_filename)
        
        if os.path.exists(transcript_filepath):
            existing_count += 1
            episode = episode.get('title', 'Unknown_Episode')
            season_string = r"Season\s+(\d+)\s+Episode\s+(\d+)"
            match = re.search(season_string, episode)
            if match:
                season_number = match.group(1)
                episode_number = match.group(2)
                existing_transcripts.add(f"S{season_number}E{episode_number}")
            continue

        if not episode_url:
            print("  -> WARNING: No MP3 URL found for this episode. Skipping.")
            missing_count += 1
            continue
        new_count += 1
            
    except Exception as e:
        print(f"  -> ERROR processing this episode: {e}. Moving to next target.")
        error_count += 1
        continue
         
print("\n--- ACQUISITION CAMPAIGN COMPLETE ---")
print(f"Existing transcripts: {existing_count}, New transcripts: {new_count}")
print(f"Errors encountered: {error_count}, Missing URLs: {missing_count}")
print(f"Total episodes processed: {i + 1}/{len(episodes)} out of {json_response.get('episode_count', 0)}")
existing_transcripts = sorted(existing_transcripts)
print(f"Existing episodes: {existing_transcripts}")
