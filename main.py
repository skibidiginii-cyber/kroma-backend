import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp

app = FastAPI(title="KromaAudio Aggregator Backend", version="1.0.0")

# Разрешаем запросы от Android-приложения (CORS)
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


@app.get("/")
def read_root():
    return {"status": "ok", "service": "KromaAudio Aggregator Engine"}


@app.get("/api/search", response_model=List[TrackResponse])
def search_tracks(q: str = Query(..., min_length=1, description="Search query")):
    """Ищет треки через yt-dlp на YouTube/SoundCloud и извлекает прямые ссылки на стрим"""
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch5',  # Возвращает топ-5 результатов с YouTube
        'extract_flat': False,
        'source_address': '0.0.0.0',
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

                # Достаем прямую ссылку на аудиопоток без сохранения на диск
                stream_url = entry.get('url')
                if not stream_url:
                    continue

                # Извлекаем обложку наивысшего качества
                thumbnails = entry.get('thumbnails', [])
                artwork_url = thumbnails[-1].get('url') if thumbnails else None

                # Парсим название и исполнителя
                title = entry.get('title', 'Unknown Track')
                uploader = entry.get('uploader') or entry.get('channel') or 'Unknown Artist'

                # Если в названии есть разделитель "Artist - Title", пытаемся разобрать
                if ' - ' in title:
                    parts = title.split(' - ', 1)
                    artist_name = parts[0].strip()
                    track_title = parts[1].strip()
                else:
                    artist_name = uploader
                    track_title = title

                results.append(
                    TrackResponse(
                        id=entry.get('id', ''),
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


if __name__ == "__main__":
    import uvicorn

    # Запуск сервера на локальном порту 8000
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)