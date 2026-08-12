import os
import asyncio
import edge_tts
from mutagen.mp3 import MP3

class AudioEngine:
    def __init__(self, voice="en-US-AvaNeural"):
        self.voice = voice
        self.output_dir = os.path.join(os.getcwd(), "assets", "audio_clips")
        os.makedirs(self.output_dir, exist_ok=True)

    async def generate_audio(self, text, output_filename, retries=3):
        """
        Generates MP3 with retry logic to handle connection drops.
        """
        output_path = os.path.join(self.output_dir, output_filename)
        
        for attempt in range(retries):
            try:
                # Rate +10% for engagement
                communicate = edge_tts.Communicate(text, self.voice, rate="+10%")
                await communicate.save(output_path)
                return output_path
            
            except Exception as e:
                print(f"      ⚠️ Audio Error (Attempt {attempt+1}/{retries}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2) # Wait 2 seconds before retrying
                else:
                    print("      ❌ Failed to generate audio after max retries.")
                    raise e # Re-raise error if all retries fail

    def get_audio_duration(self, file_path):
        try:
            audio = MP3(file_path)
            return audio.info.length
        except Exception as e:
            print(f"❌ Error reading audio length: {e}")
            return 0.0

    async def process_script(self, script_data):
        print(f"🎙️ Starting Audio Generation for {len(script_data)} scenes...")

        # Only scenes that actually got audio are kept: the composer reads
        # 'audio_path'/'duration' unconditionally and would crash on a scene
        # that was skipped here.
        narrated = []

        for scene in script_data:
            scene_id = scene['id']
            text = scene['text']
            filename = f"voice_{scene_id}.mp3"
            
            try:
                # Generate Audio
                file_path = await self.generate_audio(text, filename)
                
                # Get Duration
                duration = self.get_audio_duration(file_path)
                if duration <= 0:
                    print(f"   ❌ Skipping Scene {scene_id}: unreadable audio duration.")
                    continue

                # Update Scene Data
                scene['audio_path'] = file_path
                scene['duration'] = duration
                narrated.append(scene)

                print(f"   ✅ Scene {scene_id}: {duration:.2f}s generated.")

                # CRITICAL: Sleep for 1 second to be polite to the API
                # This prevents the "Connection Timeout" error
                await asyncio.sleep(1) 
                
            except Exception as e:
                print(f"   ❌ Skipping Scene {scene_id} due to audio error.")
                continue

        if len(narrated) < len(script_data):
            print(f"   ⚠️ {len(script_data) - len(narrated)} scene(s) dropped without audio.")

        return narrated