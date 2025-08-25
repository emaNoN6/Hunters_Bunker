# ==========================================================
# Hunter's Command Console - LLM Helper (Corrected v2)
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import requests
import json


def generate_text(prompt, api_key):
	"""
	Sends a prompt to the Google Gemini API and returns the text response.
	"""
	if not api_key:
		print("[LLM_HELPER ERROR]: Gemini API key not provided.")
		return None

	# --- THIS IS THE CORRECTED URL ---
	# Using the endpoint from the official REST API documentation.
	url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
	# --- END CORRECTION ---

	headers = {
		'Content-Type': 'application/json',
	}

	data = {
		"contents": [{
			"parts": [{
				"text": prompt
			}]
		}]
	}

	try:
		response = requests.post(url, headers=headers, data=json.dumps(data))
		response.raise_for_status()

		response_json = response.json()

		content = response_json['candidates'][0]['content']
		text = content['parts'][0]['text']

		return text.strip()

	except requests.exceptions.RequestException as e:
		print(f"[LLM_HELPER ERROR]: API request failed: {e}")
		return None
	except (KeyError, IndexError) as e:
		print(f"[LLM_HELPER ERROR]: Could not parse API response: {e}")
		print(f"Raw Response: {response.text}")
		return None
