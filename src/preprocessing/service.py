from faster_whisper import WhisperModel

def transcribe_audio(
    file_path: str,
    model_size: str = "base",
    compute_type: str = "int8",
) -> dict:
    try:
        # Load model once (you could cache this globally if needed)
        model = WhisperModel(model_size, compute_type=compute_type)

        # Run transcription
        segments, info = model.transcribe(file_path, word_timestamps=True)

        transcript = [
            {
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip()
            }
            for segment in segments
        ]

        return {
            "language": info.language,
            "language_probability": round(info.language_probability, 2),
            "segments": transcript
        }

    except Exception as e:
        print("Transcription failed:", e)
        return {
            "error": str(e),
            "segments": []
        }
