from pydub import AudioSegment
import noisereduce as nr
import numpy as np
from pathlib import Path


def denoise_audio(audio_file: str) -> str:
    audio_path = Path(audio_file)
    output_path = audio_path.with_name(audio_path.stem + "_denoised.wav")

    # Load audio
    audio = AudioSegment.from_file(audio_file)

    # Convert audio to numpy array
    samples = np.array(audio.get_array_of_samples()).astype(np.float32)

    # If stereo, convert to mono by averaging channels
    if audio.channels == 2:
        samples = samples.reshape((-1, 2))
        samples = samples.mean(axis=1)

    # Apply noise reduction
    reduced_noise = nr.reduce_noise(y=samples, sr=audio.frame_rate)

    # Convert back to AudioSegment
    reduced_audio = AudioSegment(
        reduced_noise.astype(np.int16).tobytes(),
        frame_rate = audio.frame_rate,
        sample_width = audio.sample_width,
        channels = audio.channels
    )

    # Export audio
    try:
        reduced_audio.export(output_path, format="wav")
        print("Export successful:", output_path)
    except Exception as e:
        print("Export failed:", e)
        raise e

    return str(output_path)

