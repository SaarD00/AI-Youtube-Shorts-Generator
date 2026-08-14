import os
import json
import re
import time
from google import genai
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "gemini-3.5-flash"

# Gemini returns these when it is overloaded or rate-limiting rather than when
# the request itself is wrong, so they are worth waiting out.
RETRYABLE_STATUSES = (429, 500, 502, 503, 504)

# Longest a single retry will sleep. A daily-quota 429 reports delays far past
# anything worth blocking a run on.
MAX_RETRY_WAIT = 90

def _get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Create a .env file or set the environment variable before running.")
    return genai.Client(api_key=api_key)

def _get_model():
    # An unset CI variable arrives as an empty string, not as None.
    return os.getenv("GEMINI_MODEL") or DEFAULT_MODEL

def _is_retryable(error):
    status = getattr(error, "code", None) or getattr(error, "status_code", None)
    if status in RETRYABLE_STATUSES:
        return True
    # Not every client error exposes a numeric code, so fall back to the text.
    text = str(error)
    return any(str(code) in text for code in RETRYABLE_STATUSES)

def _retry_delay(error):
    """
    Reads the retryDelay Gemini attaches to a 429. Plain backoff is often
    shorter than what the server actually wants, which just burns the retries.
    """
    match = re.search(r"'retryDelay':\s*'(\d+(?:\.\d+)?)s'", str(error))
    if not match:
        return None
    # Cap it: a daily quota reports delays no run should sit and wait out.
    return min(float(match.group(1)) + 1, MAX_RETRY_WAIT)

def _generate(prompt, retries=4):
    """
    Calls Gemini, waiting out the overload and rate-limit responses that a
    scheduled run hits regularly. Raises once the model is genuinely unreachable.
    """
    client = _get_client()
    model = _get_model()

    for attempt in range(retries):
        try:
            return client.models.generate_content(model=model, contents=prompt)
        except Exception as e:
            if attempt == retries - 1 or not _is_retryable(e):
                raise
            wait = _retry_delay(e) or 2 ** (attempt + 1)
            print(f"   ⚠️ Gemini unavailable (attempt {attempt+1}/{retries}). Retrying in {wait:.0f}s...")
            time.sleep(wait)

class ContentBrain:
    def get_trending_topic(self):
        """
        In a full build, this would scrape Google Trends or Twitter.
        For now, we ask Gemini to pick a viral niche topic.
        """
        prompts = "Give me 1 specific, viral, and engaging topic for a Short Documentary. It should be a 'Engaging Did you know' fact or a 'Fun/intriguing Engaging News'. return ONLY the topic name."
        response = _generate(prompts)
        topic = response.text.strip()
        print(f"🎯 Selected Topic: {topic}")
        return topic

    def generate_script(self, topic, lang="pt-BR"):
        """
        Generates a structured JSON script with visual cues.
        """
        lang_instruction = "Strictly in PORTUGUESE (Brasil)" if lang == "pt-BR" else "Strictly in ENGLISH"
        print(f"📝 Writing script in {lang} for: {topic}...")
        prompt = f"""
    You are the lead scriptwriter for a high-retention "Edutainment" YouTube Shorts channel.
    Topic: {topic}

    ### GOAL:
    Create a script where every sentence has a "Visual Switch". 
    To keep retention high, we need TWO different stock videos for every single scene.

    ### 1. SCRIPT REQUIREMENTS (The Voiceover):
    - **Language:** Write the text strictly in {lang_instruction}.
    - **Perspective:** Strictly **3rd Person** ("Scientists found..." / "Cientistas descobriram...").
    - **Tone:** Engaging, fast-paced, logical. No fluff.
    - **Structure:** 8-9 Scenes total.
    - **Flow:** Hook -> Context -> Mechanism (How it works) -> Twist -> Outro.

    ### 2. VISUAL REQUIREMENTS (Dual Visuals):
    - For EVERY scene, provide TWO distinct search terms in **ENGLISH** (Pexels works best in English):
      - **visual_1:** Matches the *start* of the sentence.
      - **visual_2:** Matches the *end* of the sentence or provides a reaction/context.
    - **Strictly Literal:** If the text is "The economy crashed," do NOT search "sad man". Search "Stock market red chart".

    ### OUTPUT FORMAT (Strict JSON):
    [
        {{
            "id": 1,
            "text": "In 1995, fourteen wolves were released into Yellowstone Park, and they changed the rivers.",
            "visual_1": "wolves running snow aerial",
            "visual_2": "river flowing forest drone",
            "mood": "intriguing" 
        }},
        {{
            "id": 2,
            "text": "It sounds impossible, but the biology is actually simple math.",
            "visual_1": "person shocked looking at camera",
            "visual_2": "blackboard math equations chalk",
            "mood": "educational"
        }}
    ]
    """
    #     prompt = f"""
    # You are a master visual storyteller creating a viral YouTube Short.
    # Topic: {topic}
    
    # ### CRITICAL REQUIREMENTS:
    # 1. **Perspective:** Strictly **3rd Person** (e.g., "Scientists discovered..." or "The world changed..."). No "I" or "You".
    # 2. **Tone:** Cinematic, high-stakes, and slightly exaggerated.
    #    - Use **Power Words**: Instead of "big," use "colossal." Instead of "scary," use "terrifying."
    #    - The vibe should be "Mystery Documentary" (like Vox or National Geographic but faster).
    # 3. **Length:** Exactly **8 to 9 scenes**. Total read time 40-50 seconds.
    # 4. **Visual Strategy:** Keywords must be optimized for Pexels Stock Footage.
    #    - Use simple, broad nouns: "storm clouds", "ancient ruins", "laboratory microscope".
    #    - Avoid complex actions or specific people.
    
    # ### STRUCTURE GUIDE:
    # - **Scene 1 (The Hook):** A mind-blowing statement or paradox. Grab attention immediately.
    # - **Scene 2-3 (The Mystery):** Establish why this is strange, dangerous, or important.
    # - **Scene 4-7 (The Climax):** The "Wait, what?" moment. The biggest twist or fact.
    # - **Scene 8-9 (The Mic Drop):** A final haunting thought or powerful conclusion.
    
    # ### OUTPUT FORMAT (Strict JSON):
    # [
    #     {{
    #         "id": 1,
    #         "text": "Deep beneath the Antarctic ice, something IMPOSSIBLE has just been detected.",
    #         "keywords": "glacier aerial drone cinematic",
    #         "mood": "ominous" 
    #     }},
    #     {{
    #         "id": 2,
    #         "text": "For centuries, maps showed this area as empty... they were wrong.",
    #         "keywords": "old map ancient paper table",
    #         "mood": "mystery"
    #     }}
    # ]
    # """
    

        # Unattended runs cannot recover from a single malformed reply, so retry.
        for attempt in range(3):
            response = _generate(prompt)

            # Clean the response to ensure it's valid JSON (sometimes AI adds markdown)
            clean_text = response.text.replace('```json', '').replace('```', '').strip()

            try:
                script_data = json.loads(clean_text)
            except json.JSONDecodeError:
                print(f"   ⚠️ Invalid JSON (attempt {attempt+1}/3). Raw output:")
                print(clean_text[:500])
                continue

            script_data = self._sanitize(script_data)
            if script_data:
                return script_data
            print(f"   ⚠️ Script had no usable scenes (attempt {attempt+1}/3).")

        print("❌ Script generation failed after 3 attempts.")
        return None

    def generate_metadata(self, topic, script_data):
        """
        Writes the YouTube title, description and tags for a finished short.
        Falls back to the topic itself if the model misbehaves — a weak title is
        better than a failed upload.
        """
        narration = " ".join(scene['text'] for scene in script_data)

        prompt = f"""
    Write YouTube Shorts metadata for this video.

    Topic: {topic}
    Narration: {narration}

    Rules:
    - "title": under 80 characters, curiosity-driven, no clickbait punctuation spam.
    - "description": 2-3 sentences summarizing the video, then a blank line, then "#Shorts".
    - "tags": 8-12 lowercase search keywords, no "#" prefix.

    Return ONLY strict JSON:
    {{"title": "...", "description": "...", "tags": ["...", "..."]}}
    """

        fallback = {
            "title": topic[:80],
            "description": f"{topic}\n\n#Shorts",
            "tags": [],
        }

        try:
            response = _generate(prompt)
            clean_text = response.text.replace('```json', '').replace('```', '').strip()
            metadata = json.loads(clean_text)
        except Exception as e:
            print(f"   ⚠️ Metadata generation failed ({e}). Using the topic as the title.")
            return fallback

        if not isinstance(metadata, dict) or not str(metadata.get('title', '')).strip():
            print("   ⚠️ Metadata had no usable title. Using the topic as the title.")
            return fallback

        tags = metadata.get('tags') or []
        if not isinstance(tags, list):
            tags = []

        description = str(metadata.get('description', '')).strip() or fallback['description']
        if "#Shorts" not in description:
            description = f"{description}\n\n#Shorts"

        return {
            "title": str(metadata['title']).strip(),
            "description": description,
            "tags": [str(tag).strip() for tag in tags if str(tag).strip()],
        }

    @staticmethod
    def _sanitize(script_data):
        """
        Drops malformed scenes and renumbers ids so downstream modules can rely
        on 'id' and 'text' always being present.
        """
        if not isinstance(script_data, list):
            print(f"   ⚠️ Expected a list of scenes, got {type(script_data).__name__}.")
            return None

        scenes = []
        for raw in script_data:
            if not isinstance(raw, dict):
                continue
            text = str(raw.get('text', '')).strip()
            if not text:
                continue
            scene = dict(raw)
            scene['text'] = text
            scene['id'] = len(scenes) + 1
            scenes.append(scene)

        return scenes or None
        
# --- TESTING THE MODULE ---
if __name__ == "__main__":
    brain = ContentBrain()
    topic = brain.get_trending_topic()
    script = brain.generate_script(topic)
    
    # Save to file to verify
    with open("script.json", "w") as f:
        json.dump(script, f, indent=4)
        print("✅ Script saved to script.json")