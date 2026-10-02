import mimetypes
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_MEDIA_SECONDS = 300
CHUNK_SECONDS = 60
MAX_MEDIA_CHUNKS = 5

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
AUDIO_TYPES = {
    "audio/aac",
    "audio/flac",
    "audio/mp4",
    "audio/mpeg",
    "audio/ogg",
    "audio/wav",
    "audio/webm",
    "audio/x-wav",
}
VIDEO_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/x-matroska",
}
TEXT_TYPES = {"text/plain"}

MIME_EXTENSIONS = {
    "audio/aac": ".aac",
    "audio/flac": ".flac",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/webm": ".webm",
    "audio/x-wav": ".wav",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "text/plain": ".txt",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "video/x-matroska": ".mkv",
}


@dataclass(frozen=True)
class MediaChunk:
    data: bytes
    mime_type: str


def normalize_mime_type(content_type: str | None, filename: str | None) -> str:
    mime_type = (content_type or "").split(";", maxsplit=1)[0].strip().lower()
    if not mime_type or mime_type == "application/octet-stream":
        mime_type = mimetypes.guess_type(filename or "")[0] or ""
    if mime_type not in IMAGE_TYPES | AUDIO_TYPES | VIDEO_TYPES | TEXT_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload plain text, JPEG/PNG/WebP, or a supported audio/video file.",
        )
    return mime_type


def _probe_duration(path: Path) -> float:
    if not shutil.which("ffprobe"):
        raise HTTPException(
            status_code=503,
            detail="Audio/video processing requires ffprobe to be installed.",
        )

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            check=True,
            text=True,
            timeout=15,
        )
        return float(result.stdout.strip())
    except (subprocess.SubprocessError, ValueError):
        raise HTTPException(
            status_code=422,
            detail="The uploaded audio/video file could not be read.",
        ) from None


def _split_audio_video(data: bytes, mime_type: str) -> list[MediaChunk]:
    if not shutil.which("ffmpeg"):
        raise HTTPException(
            status_code=503,
            detail="Audio/video processing requires ffmpeg to be installed.",
        )

    with tempfile.TemporaryDirectory(prefix="siteshield-media-") as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / f"upload{MIME_EXTENSIONS[mime_type]}"
        input_path.write_bytes(data)

        duration = _probe_duration(input_path)
        if duration <= 0:
            raise HTTPException(status_code=422, detail="The uploaded media has no readable duration.")
        if duration > MAX_MEDIA_SECONDS:
            raise HTTPException(
                status_code=413,
                detail=f"Audio/video uploads are limited to {MAX_MEDIA_SECONDS // 60} minutes.",
            )

        if mime_type.startswith("audio/"):
            output_extension = ".mp3"
            output_mime = "audio/mpeg"
            output_pattern = temp_path / "chunk_%03d.mp3"
            command = [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(input_path),
                "-vn",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "96k",
                "-f",
                "segment",
                "-segment_time",
                str(CHUNK_SECONDS),
                "-reset_timestamps",
                "1",
                str(output_pattern),
            ]
        else:
            output_extension = ".webm" if mime_type == "video/webm" else (
                ".mkv" if mime_type == "video/x-matroska" else ".mp4"
            )
            output_mime = {
                ".webm": "video/webm",
                ".mkv": "video/x-matroska",
                ".mp4": "video/mp4",
            }[output_extension]
            output_pattern = temp_path / f"chunk_%03d{output_extension}"
            command = [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(input_path),
                "-map",
                "0:v:0?",
                "-map",
                "0:a:0?",
                "-c",
                "copy",
                "-f",
                "segment",
                "-segment_time",
                str(CHUNK_SECONDS),
                "-reset_timestamps",
                "1",
                "-segment_format",
                output_extension.lstrip("."),
                str(output_pattern),
            ]

        try:
            subprocess.run(command, capture_output=True, check=True, timeout=90)
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=422, detail="Media processing took too long.") from None
        except subprocess.CalledProcessError:
            raise HTTPException(
                status_code=422,
                detail="The uploaded audio/video format could not be processed.",
            ) from None

        chunk_paths = sorted(temp_path.glob(f"chunk_*{output_extension}"))
        if not chunk_paths:
            raise HTTPException(status_code=422, detail="No audio/video segments could be extracted.")
        if len(chunk_paths) > MAX_MEDIA_CHUNKS:
            raise HTTPException(
                status_code=413,
                detail=f"Audio/video uploads may contain at most {MAX_MEDIA_CHUNKS} segments.",
            )

        return [
            MediaChunk(data=chunk_path.read_bytes(), mime_type=output_mime)
            for chunk_path in chunk_paths
        ]


def prepare_media(data: bytes, mime_type: str) -> list[MediaChunk]:
    if not data:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploads are limited to 8 MiB.")

    if mime_type in IMAGE_TYPES:
        return [MediaChunk(data=data, mime_type=mime_type)]
    if mime_type in AUDIO_TYPES | VIDEO_TYPES:
        return _split_audio_video(data, mime_type)
    raise HTTPException(status_code=415, detail="This file type is not supported for media analysis.")