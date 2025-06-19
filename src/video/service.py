import uuid
import subprocess
from pathlib import Path
from fastapi import UploadFile


UPLOAD_DIR = Path("video")
UPLOAD_DIR.mkdir(exist_ok=True)
AUDIO_DIR = Path("audio")
AUDIO_DIR.mkdir(exist_ok=True)

def save_uploaded_file(file: UploadFile) -> dict:
    file_ext = Path(file.filename).suffix
    file_id = str(uuid.uuid4())
    saved_path = UPLOAD_DIR / f"{file_id}{file_ext}"

    with open(saved_path, "wb") as f:
        content = file.file.read()
        f.write(content)

    return {
        "file_id": file_id,
        "filename": saved_path.name,
        "path": str(saved_path)
    }

def extract_audio_from_video(video_path: str, audio_filename: str = None) -> str:
    video_path = Path(video_path)
    audio_filename = audio_filename or video_path.stem + ".wav"
    output_path = AUDIO_DIR / audio_filename

    cmd = [
        "ffmpeg",
        "-y",                    # Overwrite existing
        "-i", str(video_path),   # Input video
        "-vn",                   # Disable video output
        "-acodec", "pcm_s16le",  # WAV codec
        "-ar", "16000",          # 16 kHz (Whisper-friendly)
        "-ac", "1",              # Mono
        str(output_path)
    ]

    subprocess.run(cmd, check=True)

    return str(output_path)


def replace_audio_in_video(video_path: str, new_audio_path: str, output_path: str = None) -> str:
    video_path = Path(video_path)
    new_audio_path = Path(new_audio_path)
    output_path = output_path or str(video_path.parent / f"{video_path.stem}_with_audio.mp4")

    cmd = [
        "ffmpeg",
        "-y",  # overwrite
        "-i", str(video_path),
        "-i", str(new_audio_path),
        "-c:v", "copy",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        str(output_path)
    ]

    subprocess.run(cmd, check=True)
    return output_path
