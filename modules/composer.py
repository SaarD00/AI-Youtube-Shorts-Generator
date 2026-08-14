import os
import random
import ffmpeg

class Composer:
    def __init__(self):
        self.temp_dir = os.path.join(os.getcwd(), "assets", "temp")
        self.final_dir = os.path.join(os.getcwd(), "assets", "final")
        self.avatar_path = os.path.join(os.getcwd(), "assets", "avatar", "avatars.mp4")
        
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.final_dir, exist_ok=True)
        self.transitions = ['fade', 'diagbr', 'diagtl']

    def get_duration(self, filepath):
        try:
            probe = ffmpeg.probe(filepath)
            return float(probe['format']['duration'])
        except:
            return 0.0

    def process_scene(self, scene, video_pair, is_avatar=False):
        """
        Combines Audio with Visuals.
        - If Avatar: Loop single video + CROP LOGO.
        - If Stock: Split duration 50/50 between Video A and Video B.
        """
        scene_id = scene['id']
        audio_path = scene['audio_path']
        total_duration = scene['duration']
        output_path = os.path.join(self.temp_dir, f"scene_{scene_id}.mp4")

        try:
            input_audio = ffmpeg.input(audio_path)

            if is_avatar:
                # --- AVATAR MODE (Single Loop + CROP) ---
                print(f"   ⚙️ Processing Scene {scene_id}: 🤖 Avatar Mode (Cropped)")
                
                video_stream = (
                    ffmpeg.input(video_pair[0], stream_loop=-1)
                    .trim(duration=total_duration + 0.5)
                    .setpts('PTS-STARTPTS')
                    
                    # ---------------------------------------------------------
                    # ✂️ LOGO REMOVAL CROP
                    # ---------------------------------------------------------
                    # Current setting: Removes 150px from BOTTOM.
                    .filter('crop', 'iw', 'ih-150', 0, 0) 
                    
                    # ---------------------------------------------------------
                    # 📏 RESIZE & CENTER
                    # ---------------------------------------------------------
                    .filter('scale', 1080, 1920, force_original_aspect_ratio='increase')
                    .filter('crop', 1080, 1920)
                    .filter('fps', fps=30, round='up')
                )
            else:
                # --- DUAL VIDEO MODE (50/50 Split) ---
                print(f"   ⚙️ Processing Scene {scene_id}: 🎞️ A/B Split Mode")
                path_a, path_b = video_pair
                
                duration_a = total_duration / 2
                duration_b = (total_duration / 2) + 0.5 

                # force_original_aspect_ratio='increase' fills the 9:16 frame and
                # lets the crop trim the overflow; a bare scale would squash any
                # clip Pexels returns in a different aspect ratio.
                stream_a = (
                    ffmpeg.input(path_a, stream_loop=-1)
                    .trim(duration=duration_a)
                    .setpts('PTS-STARTPTS')
                    .filter('scale', 1080, 1920, force_original_aspect_ratio='increase')
                    .filter('crop', 1080, 1920)
                    .filter('fps', fps=30, round='up')
                )

                stream_b = (
                    ffmpeg.input(path_b, stream_loop=-1)
                    .trim(duration=duration_b)
                    .setpts('PTS-STARTPTS')
                    .filter('scale', 1080, 1920, force_original_aspect_ratio='increase')
                    .filter('crop', 1080, 1920)
                    .filter('fps', fps=30, round='up')
                )

                video_stream = ffmpeg.concat(stream_a, stream_b, v=1, a=0)

            # Combine Video + Audio
            runner = ffmpeg.output(
                video_stream, 
                input_audio, 
                output_path, 
                vcodec='libx264', 
                acodec='aac', 
                pix_fmt='yuv420p',
                shortest=None
            )
            
            runner.run(overwrite_output=True, quiet=True)
            return output_path

        except ffmpeg.Error as e:
            print(f"❌ Render Fail Scene {scene_id}: {e.stderr.decode('utf8') if e.stderr else str(e)}")
            return None

    def render_all_scenes(self, script_data, video_pairs):
        """
        Iterates script, handles Avatar injection logic (TWICE), and renders individual scenes.
        """
        rendered_paths = []
        
        # 1. Randomly pick TWO distinct middle scenes for the Avatar
        # We pick from range [1, len-2] to avoid the Hook (0) and Outro (last)
        avatar_indices = []
        
        # Only inject if we have enough scenes (need at least 4 scenes to safely pick 2 middle ones)
        if len(script_data) >= 4 and os.path.exists(self.avatar_path):
            valid_range = list(range(1, len(script_data) - 1)) # All valid middle indices
            
            # Pick 2 unique indices if possible, otherwise just 1
            count_to_pick = 2 if len(valid_range) >= 2 else 1
            avatar_indices = random.sample(valid_range, count_to_pick)
            
            # Sort them just for cleaner logging
            avatar_indices.sort()
            human_readable_indices = [i + 1 for i in avatar_indices]
            print(f"🎲 Avatar set for Scenes: {human_readable_indices}")

        # 2. Render Loop
        for i, scene in enumerate(script_data):
            current_pair = video_pairs[i] if i < len(video_pairs) else None
            is_avatar = False

            # Injection Logic: Check if current index is in our chosen list
            if i in avatar_indices:
                current_pair = (self.avatar_path, None)
                is_avatar = True
            elif current_pair is None:
                continue 

            output_path = self.process_scene(scene, current_pair, is_avatar)
            if output_path:
                rendered_paths.append(output_path)
        
        return rendered_paths

    def concatenate_with_transitions(self, video_paths, output_filename="final_short.mp4"):
        """
        Stitches rendered scenes together.
        INCLUDES FIXES FOR: Windows 0x80004005 Error & Playback Issues.
        """
        print("🎬 Stitching final video...")
        output_path = os.path.join(self.final_dir, output_filename)
        
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                print("⚠️ Warning: Could not delete old file. It might be open in a player.")

        if not video_paths:
            return None

        input1 = ffmpeg.input(video_paths[0])
        v_stream = input1.video
        a_stream = input1.audio
        
        current_dur = self.get_duration(video_paths[0])

        for i in range(1, len(video_paths)):
            next_clip = ffmpeg.input(video_paths[i])
            next_dur = self.get_duration(video_paths[i])
            
            trans_dur = 0.5
            offset = current_dur - trans_dur
            
            effect = random.choice(self.transitions)
            print(f"   ✨ Transition {i}: '{effect}' at {offset:.2f}s")

            v_stream = ffmpeg.filter(
                [v_stream, next_clip.video], 
                'xfade', 
                transition=effect, 
                duration=trans_dur, 
                offset=offset
            )
            
            a_stream = ffmpeg.filter(
                [a_stream, next_clip.audio], 
                'acrossfade', 
                d=trans_dur
            )
            
            current_dur = (current_dur + next_dur) - trans_dur

        try:
            runner = ffmpeg.output(
                v_stream, 
                a_stream, 
                output_path, 
                vcodec='libx264',   # Standard H.264 video
                acodec='aac',       # Standard AAC audio
                pix_fmt='yuv420p',  # 🔥 FIX 1: Windows compatibility
                movflags='faststart', # 🔥 FIX 2: Corruption fix
                preset='medium' 
            )
            
            runner.run(overwrite_output=True, quiet=False)
            
            print(f"✅ FINAL VIDEO SAVED: {output_path}")
            return output_path

        except ffmpeg.Error as e:
            error_log = e.stderr.decode('utf8') if e.stderr else str(e)
            print(f"❌ Stitching Error: {error_log}")
            return None