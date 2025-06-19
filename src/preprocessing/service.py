from faster_whisper import WhisperModel
import glob
from pathlib import Path


def transcribe_audio(
    file_path: Path,
    model_size: str,
    compute_type: str = "float32",
) -> dict:
    try:
        model = WhisperModel(model_size, compute_type=compute_type)

        segments, info = model.transcribe(file_path,
                                          initial_prompt="Transcribe everything exactly as spoken,"
                                                         "including ums and uhs, and all filler words",
                                          vad_filter=False,
                                          suppress_tokens=[],
                                          beam_size=5,
                                          word_timestamps=True,
                                          condition_on_previous_text=False)

        words = []
        words_print = []
        for segment in segments:
            if segment.words:
                for word in segment.words:
                    words.append({
                        "word": word.word.strip(),
                        "start": round(word.start, 4),
                        "end": round(word.end, 4),
                    })
                    words_print.append(word.word.strip())
        return {
            "only_words": words_print,
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "words": words
        }

    except Exception as e:
        print("Transcription failed:", e)
        return {
            "error": str(e),
            "words": []
        }




def find_video_file(media_id: str, upload_dir: Path) -> Path | None:
    pattern = str(upload_dir / f"{media_id}.*")
    matches = glob.glob(pattern)

    for path in matches:
        if Path(path).suffix.lower() in [".mp4", ".mov", ".mkv"]:
            return Path(path)

    return None



