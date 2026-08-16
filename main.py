import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp

app = FastAPI(title="KromaAudio Engine", version="1.0.0")

# Разрешаем все CORS запросы
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("KromaBackend")


class TrackResponse(BaseModel):
    id: str
    title: str
    artist: str
    duration_sec: int
    artwork_url: Optional[str] = None
    stream_url: str


class VersionResponse(BaseModel):
    version_code: int
    version_name: str
    apk_url: str
    force_update: bool
    changelog: str


# Разрешаем и GET, и HEAD на корневой адрес, чтобы не было ошибки 405 Method Not Allowed
@app.api_route("/", methods=["GET", "HEAD"])
def read_root():
    return {"status": "ok", "service": "KromaAudio Engine Running"}


@app.get("/api/version", response_model=VersionResponse)
def get_version():
    return VersionResponse(
        version_code=1,
        version_name="0.6.0",
        apk_url="https://drive.google.com/file/d/1mGm17EtTJvQkcWrLWP0rmbBOb502eujT/view?usp=sharing",  # или ссылка на GitHub Release
        force_update=False,
        changelog="Стабильный релиз KromaAudio, интеграция поиска и оффлайн библиотеки."
    )


@app.get("/api/search", response_model=List[TrackResponse])
def search_tracks(q: str = Query(..., min_length=1, description="Search query")):
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch5',
        'extract_flat': False,
        'source_address': '0.0.0.0',
        'socket_timeout': 10,
        'ignoreerrors': True,
    }

    results = []

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{q}", download=False)

            if not info or 'entries' not in info:
                return []

            for entry in info['entries']:
                if not entry:
                    continue

                stream_url = entry.get('url')
                if not stream_url:
                    continue

                thumbnails = entry.get('thumbnails', [])
                artwork_url = thumbnails[-1].get('url') if thumbnails else None

                title = entry.get('title', 'Unknown Track')
                uploader = entry.get('uploader') or entry.get('channel') or 'Unknown Artist'

                if ' - ' in title:
                    parts = title.split(' - ', 1)
                    artist_name = parts[0].strip()
                    track_title = parts[1].strip()
                else:
                    artist_name = uploader
                    track_title = title

                results.append(
                    TrackResponse(
                        id=str(entry.get('id', '')),
                        title=track_title,
                        artist=artist_name,
                        duration_sec=int(entry.get('duration') or 0),
                        artwork_url=artwork_url,
                        stream_url=stream_url
                    )
                )

        return results

    except Exception as e:
        logger.error(f"Error extracting stream for query '{q}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search tracks: {str(e)}")