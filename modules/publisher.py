import os
import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# Uploading is the only scope this needs. Keeping it narrow means the consent
# screen cannot hand out read/write access to the rest of the channel.
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

TOKEN_URI = "https://oauth2.googleapis.com/token"


class YouTubeUploader:
    """
    Uploads a finished short to YouTube using a long-lived refresh token, so an
    unattended run never needs a browser. Run authorize_youtube.py once to mint
    that token.
    """

    def __init__(self):
        self.client_id = os.getenv("YOUTUBE_CLIENT_ID")
        self.client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
        self.refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")

        missing = [
            name for name, value in (
                ("YOUTUBE_CLIENT_ID", self.client_id),
                ("YOUTUBE_CLIENT_SECRET", self.client_secret),
                ("YOUTUBE_REFRESH_TOKEN", self.refresh_token),
            ) if not value
        ]
        if missing:
            raise RuntimeError(
                f"{', '.join(missing)} not set. Run authorize_youtube.py once and "
                "copy the values it prints into your .env file."
            )

    def _service(self):
        credentials = Credentials(
            token=None,
            refresh_token=self.refresh_token,
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_uri=TOKEN_URI,
            scopes=SCOPES,
        )
        credentials.refresh(Request())
        return build("youtube", "v3", credentials=credentials, cache_discovery=False)

    def upload(self, video_path, title, description, tags=None, privacy_status="private",
               category_id="27"):
        """
        Uploads video_path and returns the new video's URL, or None on failure.

        privacy_status defaults to 'private' on purpose: an unverified Google
        Cloud project has its uploads forced private anyway, and it gives you a
        chance to review before anything goes live.
        """
        if not os.path.exists(video_path):
            print(f"❌ Upload skipped: {video_path} does not exist.")
            return None

        # YouTube truncates past these limits, so trim deliberately instead.
        title = title[:100]
        description = description[:5000]

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": (tags or [])[:15],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        print(f"📤 Uploading to YouTube as '{privacy_status}': {title}")

        try:
            service = self._service()
        except Exception as e:
            print(f"❌ YouTube auth failed: {e}")
            return None

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        request = service.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        errors = 0
        while response is None:
            try:
                _, response = request.next_chunk()
            except HttpError as e:
                # 5xx is transient; anything else (quota, bad metadata) will not
                # get better by trying again.
                if e.resp.status in (500, 502, 503, 504) and errors < 3:
                    errors += 1
                    wait = 2 ** errors
                    print(f"   ⚠️ Transient upload error ({e.resp.status}). Retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                print(f"❌ Upload failed: {e}")
                return None
            except Exception as e:
                print(f"❌ Upload failed: {e}")
                return None

        video_id = response.get("id")
        if not video_id:
            print(f"❌ Upload returned no video id: {response}")
            return None

        url = f"https://youtube.com/shorts/{video_id}"
        print(f"✅ Uploaded: {url}")
        return url
