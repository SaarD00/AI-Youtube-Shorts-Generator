# 🎬 AutoShorts AI: The Automated Faceless Video Generator

![Views](https://komarev.com/ghpvc/?username=SaarD00-AI-Youtube-Shorts-Generator&style=for-the-badge&color=blue)


**AutoShorts AI** is a Python pipeline that creates viral-style "Faceless" YouTube Shorts and TikToks from a topic. It handles the production chain: AI topic/script generation, voiceover generation, stock footage sourcing, and FFmpeg editing with transitions and avatar injection.

---

## ✨ Key Features

- **🧠 Intelligent Scriptwriting:** Uses **Google Gemini 2.0 Flash** to write engaging, "Edutainment" style scripts (Vox/Kurzgesagt style) with strict storytelling structures (Hook → Context → Mechanism → Twist).
- **🗣️ Voiceovers:** Generates narration with `edge-tts`.
- **🎞️ Dual-Visual System:** Automatically searches and downloads **two distinct stock videos** per scene from **Pexels**, creating a dynamic "A/B Split" visual style to maximize viewer retention.
- **✂️ Advanced FFmpeg Editing:**
- **Smart Trimming:** Syncs video perfectly to audio duration.
- **A/B Splitting:** Cuts every scene in half, switching visuals mid-sentence.
- **Pro Transitions:** Randomly applies `xfade` (fade, slide, wipes) between scenes.
- **Silence Removal:** Automatically trims dead air from AI voice generation.

- **🤖 Random Avatar Injection:** Automatically inserts a custom "Avatar/Mascot" video into a random middle scene to build channel brand identity.
- **🪟 Windows Ready:** Includes specific FFmpeg flags (`yuv420p`, `faststart`) to prevent corruption errors (`0x80004005`) on Windows Media Player.

---

## 📂 Project Structure

```text
Automated-YT-Shorts-AI/
│
├── assets/                  # Stores all media files
│   ├── audio_clips/         # Generated voiceovers (.wav)
│   ├── video_clips/         # Downloaded stock footage (.mp4)
│   ├── temp/                # Intermediate processing files
│   ├── final/               # 🏆 The Final Output Video lives here
│   └── avatar/              # ⚠️ PUT YOUR AVATAR VIDEO HERE
│       └── avatars.mp4
│
├── modules/                 # Core Logic Modules
│   ├── brain.py             # AI Scriptwriter (Gemini)
│   ├── audio.py             # Voice generator (edge-tts)
│   ├── asset_manager.py     # Pexels Downloader (Dual-Visual logic)
│   └── composer.py          # FFmpeg Video Editor (Stitching & Transitions)
│
├── main.py                  # Entry point (Orchestrator)
└── requirements.txt         # Python dependencies

```

---

## 🛠️ Prerequisites

1. **Python 3.10+** installed.
2. **FFmpeg** installed and added to your system PATH.

- _Windows:_ `winget install ffmpeg` (or download from [ffmpeg.org](https://ffmpeg.org/download.html)).
- _Verify:_ Type `ffmpeg -version` in your terminal.

3. **API Keys:**

- **Google Gemini API Key** (Free tier available).
- **Pexels API Key** (Free).
- No Ngrok token is required for the default voiceover path. The current pipeline uses `edge-tts`.

---

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/AutoShorts-AI.git
cd AutoShorts-AI

```

### 2. Install Dependencies

```bash
pip install -r requirements.txt

```

### 3. Environment Setup

Create the required folders and add your avatar:

1. Create folder: `assets/avatar`
2. Place your avatar video inside and name it: `avatars.mp4`

### 4. Configure API Keys

Copy `.env.example` to `.env` and fill in your key:

```bash
cp .env.example .env
```

Required:

- `GEMINI_API_KEY` for script generation
- `PEXELS_API_KEY` for stock video search/download

Optional:

- `GEMINI_MODEL` to override the default `gemini-3.5-flash` model

---

## 🎮 How to Run

### Generate Video

Run the main script:

```bash
python main.py

```

1. The AI picks a trending topic, writes the script, generates the audio, downloads stock footage, and edits the video.
2. The final video is saved to `assets/final/` with a timestamped name (e.g. `short_20260812_1930.mp4`).

### Automated / Unattended Runs

`main.py` is fully non-interactive and returns a non-zero exit code when a run
fails, so it drops straight into cron, systemd timers, or CI.

```bash
# Verify keys, ffmpeg and assets without generating anything
python main.py --check

# Pin the topic instead of letting the AI choose one
python main.py --topic "Why the Sahara was once green"

# Batch: produce 3 videos in one invocation
python main.py --runs 3

# Pick a voice and a fixed output name
python main.py --voice en-GB-SoniaNeural --output daily_short.mp4
```

| Flag | Purpose |
| --- | --- |
| `--topic` | Skip the AI topic picker and use your own topic. |
| `--runs N` | Generate N videos in one invocation (default `1`). |
| `--voice` | Any `edge-tts` voice (default `en-US-AvaNeural`). |
| `--output` | Output filename for a single run (default: timestamped). |
| `--keep-cache` | Keep intermediate audio/video files instead of cleaning them. |
| `--fail-fast` | Stop a batch at the first failed run. |
| `--check` | Run preflight checks (ffmpeg, API keys, avatar) and exit. |

Schedule a daily short with cron:

```cron
0 9 * * * cd /path/to/AutoShorts-AI && /usr/bin/python3 main.py >> run.log 2>&1
```

---

## 🧩 Module Breakdown

### `brain.py` ( The Writer)

- **Input:** Topic string.
- **Logic:** Prompts Gemini to create an 8-9 scene JSON script. It asks for **two** visual keywords per scene (`visual_1`, `visual_2`) to enable the A/B split effect.

### `audio.py` (The Voice)

- **Input:** Text script.
- **Logic:** Generates MP3 voice clips with `edge-tts`.
- **Post-Processing:** Reads durations with `mutagen` so scenes can be synced to audio length.

### `asset_manager.py` (The Librarian)

- **Input:** Visual keywords.
- **Logic:** Searches Pexels for **Portrait (9:16)** videos. Downloads pairs of videos for every scene. Handles fallbacks (if Video B is missing, reuse Video A).

### `composer.py` (The Editor)

- **Input:** Audio files + Video files.
- **Logic:**
- **Scene Processing:** Cuts the scene duration in half. Plays Video A for the first half, Video B for the second half.
- **Avatar Injection:** Identifies a random "middle" scene (not hook/outro) and replaces the stock footage with your Avatar loop.
- **Stitching:** Merges all scenes using `xfade` transitions (wipes, slides).
- **Rendering:** Exports as `yuv420p` H.264 MP4 with `faststart` flags for maximum compatibility.

---

## ⚠️ Troubleshooting

**Q: The video is black or corrupt (0x80004005 error).**

- **Fix:** This is usually a Windows codec issue. The updated `composer.py` forces `pix_fmt='yuv420p'`. Try opening the file with VLC Media Player.

**Q: "Avatar file missing" error.**

- **Fix:** Ensure your folder structure is exactly `assets/avatar/avatars.mp4`.

**Q: The audio is silent or fails.**

- **Fix:** Check your internet connection and that `edge-tts` is installed from `requirements.txt`.

**Q: FFmpeg error "Exec format error" or "not found".**

- **Fix:** Ensure FFmpeg is installed and accessible from your command line.

---

## 📜 License

This project is open-source. Feel free to modify and build your own automation empire!
