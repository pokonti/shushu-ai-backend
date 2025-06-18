from pedalboard.io import AudioFile
from pedalboard import Pedalboard, NoiseGate, Compressor, LowShelfFilter, Gain, HighpassFilter
import noisereduce as nr
from pathlib import Path

def denoise_audio(audio_file: str, sample_rate: int = 44100) -> str:
    audio_path = Path(audio_file)
    output_path = audio_path.parent / f"{audio_path.stem}_enhanced.wav"

    # Read and resample audio
    with AudioFile(str(audio_path)).resampled_to(sample_rate) as f:
        audio = f.read(f.frames)

    # Reduce noise using noisereduce
    reduced_noise = nr.reduce_noise(
        y=audio,
        sr=sample_rate,
        stationary=False,
        prop_decrease=0.6
    )

    # Apply pedalboard effects
    board = Pedalboard([
        NoiseGate(threshold_db=-30, ratio=1.5, release_ms=250),
        Compressor(threshold_db=-16, ratio=4),
        LowShelfFilter(cutoff_frequency_hz=400, gain_db=10, q=1),
        Gain(gain_db=2)
    ])
    # board = Pedalboard([
    #     HighpassFilter(cutoff_frequency_hz=100),  # Cut rumble
    #     NoiseGate(threshold_db=-38, ratio=2.0, release_ms=300),  # Silence empty regions
    #     Compressor(threshold_db=-18, ratio=2.0, attack_ms=10, release_ms=200),  # Gentle compression
    #     LowShelfFilter(cutoff_frequency_hz=200, gain_db=2, q=0.8),  # Gentle boost to voice body
    #     Gain(gain_db=2)  # Final lift
    # ])
#
    # board = Pedalboard([
    #     HighpassFilter(cutoff_frequency_hz=120),
    #     NoiseGate(threshold_db=-40, ratio=3.0, release_ms=300),
    #     Compressor(threshold_db=-20, ratio=2.5, attack_ms=5, release_ms=200),
    #     Gain(gain_db=4)
#         # NoiseGate(threshold_db=-35, ratio=1.5, release_ms=200),
#         # Compressor(threshold_db=-16, ratio=2.0),
#         # LowShelfFilter(cutoff_frequency_hz=200, gain_db=10, q=1),
#         # Gain(gain_db=5)
#     ])

    effected = board(reduced_noise, sample_rate)
#
# #     # Write enhanced audio
    with AudioFile(str(output_path), 'w', sample_rate, effected.shape[0]) as f:
        f.write(effected)

    return str(output_path)


# from df import enhance, init_df
# import soundfile as sf
# from pathlib import Path
#
#
# def denoise_audio(filepath: str) -> str:
#     input_path = Path(filepath)
#     output_path = input_path.parent / f"{input_path.stem}_df.wav"
#
#     # Load audio file
#     audio, sr = sf.read(str(input_path))
#
#     if sr != 48000:
#         raise ValueError(f"DeepFilterNet expects 48kHz audio, but got {sr}Hz. Please resample first.")
#
#     # Initialize model (only once per session)
#     model, df_state, _ = init_df()
#
#     # Enhance
#     enhanced = enhance(model, df_state, audio)
#
#     # Save output
#     sf.write(str(output_path), enhanced, sr)
#
#     return str(output_path)

# import torch
# from df import enhance, init_df
# import soundfile as sf
# from pathlib import Path

# def denoise_audio(filepath: str) -> str:
#     audio_path = Path(filepath)
#     output_path = audio_path.parent / f"{audio_path.stem}_cleaned_deepfilternet.wav"
#
#     # Load audio as float32
#     audio, sr = sf.read(audio_path, dtype="float32")
#
#     # Convert to mono if stereo
#     if audio.ndim > 1:
#         audio = audio.mean(axis=1)
#
#     # Convert to 2D tensor [samples, 1]
#     audio_tensor = torch.from_numpy(audio).unsqueeze(1)
#
#     # Initialize model
#     model, state, _ = init_df()
#
#     # Enhance
#     enhanced_tensor = enhance(model, state, audio_tensor)
#
#     # Convert back to numpy and flatten to 1D
#     enhanced_audio = enhanced_tensor.squeeze(1).cpu().numpy()
#
#     # Save
#     sf.write(output_path, enhanced_audio, sr)
#
#     return str(output_path)
