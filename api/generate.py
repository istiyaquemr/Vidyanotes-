
import os
import re
import json
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler

from openai import OpenAI
from youtube_transcript_api import YouTubeTranscriptApi


def get_video_id(url):
    parsed = urlparse(url)

    if parsed.hostname not in [
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be"
    ]:
        raise ValueError("Invalid YouTube URL")

    if parsed.hostname == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    else:
        video_id = parse_qs(parsed.query).get("v", [None])[0]

        if not video_id:
            match = re.match(
                r"^/(shorts|embed)/([a-zA-Z0-9_-]{11})",
                parsed.path
            )
            video_id = match.group(2) if match else None

    if not video_id or not re.fullmatch(
        r"[a-zA-Z0-9_-]{11}", video_id
    ):
        raise ValueError("Invalid video ID")

    return video_id


def make_notes(video_id, language, note_format):

    transcript = YouTubeTranscriptApi().fetch(
        video_id,
        languages=["hi", "en"]
    )

    lines = []

    for item in transcript.snippets:
        seconds = int(item.start)
        minutes, sec = divmod(seconds, 60)
        timestamp = f"{minutes:02d}:{sec:02d}"

        lines.append(
            f"[{timestamp}] {item.text}"
        )

    video_text = "\n".join(lines)

    if not video_text.strip():
        raise ValueError("Video captions not available")

    # Limit transcript size
    video_text = video_text[:35000]

    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"]
    )

    prompt = f"""
You are an expert teacher and educational notes creator.

Create high quality study notes from this YouTube transcript.

Language: {language}
Format: {note_format}

Requirements:

1. Write a clear video title/topic.
2. Make automatic chapter-wise notes.
3. Add timestamps from the actual transcript.
4. Explain every important topic simply.
5. Include important definitions.
6. Include examples if available.
7. Include formulas if present.
8. Make important exam questions and answers.
9. Add a quick revision summary.
10. Do not invent facts or timestamps.
11. Do not add information unsupported by the transcript.

For Short notes, keep everything concise.
For Detailed notes, explain concepts properly.
For Exam notes, focus on important questions and definitions.

Use proper headings and numbered chapters.

TRANSCRIPT:
{video_text}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are an expert educational teacher."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3,
        max_tokens=5000
    )

    return response.choices[0].message.content


class handler(BaseHTTPRequestHandler):

    def send_json(self, status, data):
        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        self.wfile.write(
            json.dumps(
                data,
                ensure_ascii=False
            ).encode("utf-8")
        )

    def do_POST(self):

        try:
            length = int(
                self.headers.get("Content-Length", 0)
            )

            if length <= 0 or length > 10000:
                raise ValueError("Invalid request size")

            data = json.loads(
                self.rfile.read(length)
            )

            url = data.get("url", "").strip()
            language = data.get("language", "Hindi")
            note_format = data.get("format", "Detailed")

            if language not in [
                "Hindi", "English", "Hinglish"
            ]:
                raise ValueError("Invalid language")

            if note_format not in [
                "Detailed", "Short", "Exam"
            ]:
                raise ValueError("Invalid notes format")

            video_id = get_video_id(url)

            notes = make_notes(
                video_id,
                language,
                note_format
            )

            self.send_json(200, {
                "success": True,
                "notes": notes
            })

        except Exception as error:

            print("Notes generation error:", error)

            self.send_json(400, {
                "success": False,
                "error": "Notes nahi ban paye. Video captions, link ya API configuration check karein."
            })
          
