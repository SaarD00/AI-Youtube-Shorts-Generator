import argparse
import asyncio
import os
import shutil
import sys
from datetime import datetime

from dotenv import load_dotenv

from modules.brain import ContentBrain
from modules.asset_manager import AssetManager
from modules.audio import AudioEngine
from modules.composer import Composer

load_dotenv()


def clean_cache():
    """
    Safely deletes temporary files.
    Includes a Safety Lock to prevent deleting anything outside the project.
    """
    print("🧹 Cleaning up temporary files...")

    # 1. Define the specific target folders
    folders_to_clean = [
        os.path.join(os.getcwd(), "assets", "audio_clips"),
        os.path.join(os.getcwd(), "assets", "video_clips"),
        os.path.join(os.getcwd(), "assets", "temp")
    ]

    for folder in folders_to_clean:
        # SAFETY CHECK 1: Ensure folder actually exists
        if not os.path.exists(folder):
            continue

        # SAFETY CHECK 2: Double check we are inside our project "assets" folder
        # This prevents the script from ever touching C:\ or System32
        if "assets" not in folder:
            print(f"   🚨 SECURITY ALERT: Skipping {folder} because it looks unsafe!")
            continue

        # Loop through files inside the folder
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)

            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path) # Delete the file
                    print(f"      Deleted: {filename}") # Print so you can see it working
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path) # Delete subfolders if any
            except Exception as e:
                print(f"   ❌ Failed to delete {file_path}. Reason: {e}")

    print("✨ Workspace clean!")


def preflight():
    """
    Verifies everything an unattended run depends on. Returns a list of problems;
    an empty list means the pipeline is safe to start.
    """
    problems = []

    if not shutil.which("ffmpeg"):
        problems.append("ffmpeg not found on PATH — install it (see README Prerequisites).")
    if not shutil.which("ffprobe"):
        problems.append("ffprobe not found on PATH — it ships with ffmpeg.")

    for key in ("GEMINI_API_KEY", "PEXELS_API_KEY"):
        if not os.getenv(key):
            problems.append(f"{key} is not set — add it to your .env file.")

    avatar = os.path.join(os.getcwd(), "assets", "avatar", "avatars.mp4")
    if not os.path.exists(avatar):
        # Not fatal: the composer simply skips avatar injection.
        print(f"⚠️ Avatar clip missing at {avatar} — continuing without avatar injection.")

    return problems


def build_output_name(prefix="short"):
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"


async def generate_one(args):
    """
    Runs the full pipeline once. Returns the final video path, or None on failure.
    """
    # 1. BRAIN: Get Script
    brain = ContentBrain()
    try:
        topic = args.topic or brain.get_trending_topic()
        if args.topic:
            print(f"🎯 Using provided topic: {topic}")
        script = brain.generate_script(topic)
    except Exception as e:
        print(f"❌ Brain Error: {e}")
        return None

    if not script:
        print("❌ Script generation failed.")
        return None

    # 2. AUDIO: Generate Voice
    audio_engine = AudioEngine(voice=args.voice)
    try:
        script = await audio_engine.process_script(script)
    except Exception as e:
        print(f"❌ Audio Error: {e}")
        return None

    if not script:
        print("❌ No scene produced audio.")
        return None

    # 3. ASSETS: Get Stock Video
    asset_manager = AssetManager()
    assets_map = asset_manager.get_videos(script)

    # 4. COMPOSER: Merge Video + Audio
    composer = Composer()

    final_scene_paths = composer.render_all_scenes(script, assets_map)

    # 5. STITCH WITH TRANSITIONS
    if not final_scene_paths:
        print("❌ Failed to generate any scenes.")
        return None

    output_name = args.output if (args.output and args.runs == 1) else build_output_name()
    final_path = composer.concatenate_with_transitions(final_scene_paths, output_name)

    if final_path and not args.keep_cache:
        clean_cache()

    return final_path


async def main_async(args):
    if args.check:
        problems = preflight()
        for problem in problems:
            print(f"❌ {problem}")
        if problems:
            return 1
        print("✅ Preflight passed — ready to run.")
        return 0

    problems = preflight()
    if problems:
        for problem in problems:
            print(f"❌ {problem}")
        return 1

    produced = []
    for run_index in range(args.runs):
        if args.runs > 1:
            print(f"\n===== RUN {run_index + 1}/{args.runs} =====")
        print("🚀 STARTING AUTOMATION...")

        try:
            final_path = await generate_one(args)
        except Exception as e:
            print(f"❌ Unexpected failure: {e}")
            final_path = None

        if final_path:
            produced.append(final_path)
        elif args.fail_fast:
            print("🛑 Stopping: --fail-fast is set.")
            break

    print(f"\n📦 Produced {len(produced)}/{args.runs} video(s).")
    for path in produced:
        print(f"   • {path}")

    # Non-zero exit tells cron/CI the run needs attention.
    return 0 if len(produced) == args.runs else 1


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="AutoShorts AI — generate faceless YouTube Shorts end-to-end."
    )
    parser.add_argument("--topic", help="Skip the AI topic picker and use this topic.")
    parser.add_argument("--runs", type=int, default=1, help="How many videos to generate (default: 1).")
    parser.add_argument("--voice", default="en-US-AvaNeural", help="edge-tts voice (default: en-US-AvaNeural).")
    parser.add_argument("--output", help="Output filename for a single run (default: timestamped).")
    parser.add_argument("--keep-cache", action="store_true", help="Keep intermediate audio/video files.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop the batch on the first failed run.")
    parser.add_argument("--check", action="store_true", help="Run preflight checks and exit.")

    args = parser.parse_args(argv)
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    return args


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async(parse_args())))
