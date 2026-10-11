import base64
import json
import os
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("SARVAM_API_KEY")

print(f"[1/3] Checking API Key: {'Present (Length: ' + str(len(api_key)) + ')' if api_key else 'Missing'}")

# Test 1: Grounded LLM (sarvam-105b)
print("\n[2/3] Testing sarvam-105b Chat Completion...")
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}
payload = {
    "model": "sarvam-105b",
    "messages": [
        {
            "role": "system",
            "content": (
                "You are BhoomiVoice. Answer ONLY based on the document fields provided. "
                "If not found, say 'दस्तावेज़ में यह जानकारी उपलब्ध नहीं है।' "
                "Never say legal owner, only say दर्ज खातेदार. Keep it under 2 sentences in spoken Hindi."
            ),
        },
        {
            "role": "user",
            "content": (
                "दस्तावेज़ विवरण:\nखातेदार: रामेश्वर प्रसाद सुपुत्र हरिनारायण\n"
                "खसरा संख्या: 342/2 ख\nक्षेत्रफल: 0.4520 हेक्टेयर\n\n"
                "प्रश्न: खातेदार का क्या नाम है और उनका रकबा कितना है?"
            ),
        },
    ],
    "temperature": 0.1,
    "max_tokens": 150,
}

resp = requests.post("https://api.sarvam.ai/v1/chat/completions", headers=headers, json=payload, timeout=20)
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    llm_reply = resp.json()["choices"][0]["message"]["content"]
    print(f"Reply: {llm_reply}")
else:
    print(f"Error: {resp.text}")
    llm_reply = "दर्ज खातेदार का नाम रामेश्वर प्रसाद है और उनका रकबा 0.4520 हेक्टेयर है।"

# Test 2: TTS (bulbul:v3)
print("\n[3/3] Testing Bulbul v3 TTS...")
tts_headers = {
    "api-subscription-key": api_key,
    "Content-Type": "application/json",
}
tts_payload = {
    "inputs": [llm_reply],
    "target_language_code": "hi-IN",
    "speaker": "shubh",
    "pitch": 0,
    "pace": 1.0,
    "loudness": 1.5,
    "speech_sample_rate": 8000,
    "enable_preprocessing": True,
    "model": "bulbul:v3",
}

tts_resp = requests.post("https://api.sarvam.ai/text-to-speech", headers=tts_headers, json=tts_payload, timeout=20)
print(f"TTS Status: {tts_resp.status_code}")
if tts_resp.status_code == 200:
    audios = tts_resp.json().get("audios", [])
    if audios:
        audio_bytes = base64.b64decode(audios[0])
        Path("test_audio.wav").write_bytes(audio_bytes)
        print(f"Audio saved to test_audio.wav ({len(audio_bytes)} bytes)")
else:
    print(f"TTS Error: {tts_resp.text}")

print("\nEndpoint test script completed.")
