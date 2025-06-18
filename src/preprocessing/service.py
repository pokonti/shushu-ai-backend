from faster_whisper import WhisperModel
import subprocess
from pathlib import Path
# from voicefixer import VoiceFixer

# def denoise_audio(audio_path: str) -> str:
#     audio_path = Path(audio_path)
#     output_path = Path("separated/htdemucs") / audio_path.stem / "vocals.wav"
#
#     subprocess.run([
#         "python3", "-m", "demucs",
#         "--two-stems", "vocals",
#         "-o", "separated",
#         str(audio_path)
#     ], check=True)
#
#     return str(output_path)
# def denoise_audio(audio_path: str, output_dir: str = "separated") -> str:
#     audio_path = Path(audio_path)
#
#     if not audio_path.exists():
#         raise FileNotFoundError(f"Audio file not found: {audio_path}")
#
#     try:
#         subprocess.run([
#             "python3",
#             "-m", "demucs",
#             "--two-stems", "vocals",
#             "-o", output_dir,
#             str(audio_path)
#         ], check=True)
#     except subprocess.CalledProcessError as e:
#         print(f"Demucs failed: {e}")
#
#     model_name = "htdemucs"  # default model
#     output_path = Path(output_dir) / model_name / audio_path.stem / "vocals.wav"
#
#     if not output_path.exists():
#         raise FileNotFoundError(f"Expected output not found: {output_path}")
#
#     print(f"Denoised audio saved at: {output_path}")
#     return str(output_path)


# def denoise_audio(audio_path: str) -> str:
#     audio_path = Path(audio_path)
#     output_dir = Path("denoised")
#     output_dir.mkdir(parents=True, exist_ok=True)
#
#     output_path = output_dir / audio_path.name.replace(".wav", "_denoised.wav")
#
#     fixer = VoiceFixer()
#     fixer.restore(input=str(audio_path), output=str(output_path))
#
#     return str(output_path)

# import noisereduce as nr
# import scipy.io.wavfile as wav
# import numpy as np
#
# def denoise_audio(input_path: str) -> str:
#     input_path = Path(input_path)
#     output_dir = Path("denoised")
#     output_dir.mkdir(parents=True, exist_ok=True)
#     output_path = output_dir / f"{input_path.stem}_denoised.wav"
#
#     # Load audio
#     rate, data = wav.read(input_path)
#
#     # Optional: take first 0.5 sec as noise profile
#     noise_sample = data[0:int(rate * 0.5)]
#
#     # Apply noise reduction
#     reduced_noise = nr.reduce_noise(y=data, sr=rate, y_noise=noise_sample)
#
#     # Save the result
#     wav.write(output_path, rate, reduced_noise.astype(data.dtype))
#
#     return str(output_path)

def transcribe_audio(
    file_path: str,
    model_size: str,
    compute_type: str = "float32",
) -> dict:
    try:
        # Load model
        model = WhisperModel(model_size, compute_type=compute_type)

        # Transcribe with word timestamps
        segments, info = model.transcribe(file_path,
                                          initial_prompt="Transcribe everything exactly as spoken, including ums and uhs, all filler words",
                                          vad_filter=False,  # VAD can cut fillers
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
        print(words_print)
        return {
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


