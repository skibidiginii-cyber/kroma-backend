import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp

app = FastAPI(title="KromaAudio Engine", version="1.1.0")

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
    stream_url: Optional[str] = None


class VersionResponse(BaseModel):
    version_code: int
    version_name: str
    apk_url: str
    force_update: bool
    changelog: str


class StreamResponse(BaseModel):
    id: str
    stream_url: str


def clean_artist_name(uploader: str, title: str) -> tuple[str, str]:
    """Очищает имя исполнителя от суффиксов VEVO, - Topic и парсит title"""
    clean_uploader = uploader.replace(" - Topic", "").replace("VEVO", "").strip()

    if " - " in title:
        parts = title.split(" - ", 1)
        artist = parts[0].strip()
        track_title = parts[1].strip()
    else:
        artist = clean_uploader if clean_uploader else "Unknown Artist"
        track_title = title

    return artist, track_title


@app.api_route("/", methods=["GET", "HEAD"])
def read_root():
    return {"status": "ok", "service": "KromaAudio Engine Running"}


@app.get("/api/version", response_model=VersionResponse)
def get_version():
    return VersionResponse(
        version_code=1,
        version_name="0.6.0",
        apk_url="https://drive.google.com/file/d/1mGm17EtTJvQkcWrLWP0rmbBOb502eujT/view?usp=sharing",
        force_update=False,
        changelog="Оптимизация скорости поиска и фикс получения аудиопотока."
    )


@app.get("/api/search", response_model=List[TrackResponse])
def search_tracks(q: str = Query(..., min_length=1, description="Search query")):
    # Быстрый поиск metadata без извлечения тяжелых stream URL
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'skip_download': True,
        'socket_timeout': 5,
    }

    results = []

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch10:{q}", download=False)

            if not info or 'entries' not in info:
                return []

            for entry in info['entries']:
                if not entry:
                    continue

                video_id = entry.get('id')
                if not video_id:
                    continue

                raw_title = entry.get('title', 'Unknown Track')
                uploader = entry.get('uploader') or entry.get('channel') or ''
                artist_name, track_title = clean_artist_name(uploader, raw_title)

                # Выбираем лучший арт
                artwork_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

                results.append(
                    TrackResponse(
                        id=str(video_id),
                        title=track_title,
                        artist=artist_name,
                        duration_sec=int(entry.get('duration') or 0),
                        artwork_url=artwork_url,
                        stream_url=None
                    )
                )

        return results

    except Exception as e:
        logger.error(f"Search error for '{q}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search tracks: {str(e)}")


@app.get("/api/stream/{track_id}", response_model=StreamResponse)
def get_stream_url(track_id: str):
    """Отдельный эндпоинт для получения свежего stream_url непосредственно перед воспроизведением"""
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 8,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={track_id}", download=False)
            stream_url = info.get('url')

            if not stream_url:
                raise HTTPException(status_code=404, detail="Stream URL not found")

            return StreamResponse(id=track_id, stream_url=stream_url)

    except Exception as e:
        logger.error(f"Stream resolution error for ID '{track_id}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resolve stream: {str(e)}")