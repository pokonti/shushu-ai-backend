from pathlib import Path
import subprocess

def extract_audio_from_video(video_path_str: str, output_dir_str: str) -> str:
    video_path = Path(video_path_str)
    output_dir = Path(output_dir_str)

    # Create a unique, descriptive filename for the extracted audio.
    audio_filename = f"{video_path.stem}_extracted_audio.wav"
    output_audio_path = output_dir / audio_filename

    cmd = [
        "ffmpeg",
        "-y",  # Overwrite existing files
        "-i", str(video_path),  # Input video
        "-vn",  # No video output
        "-acodec", "pcm_s16le",  # Use WAV codec for high quality
        "-ar", "16000",  # Sample rate for speech recognition
        "-ac", "1",  # Mono channel
        str(output_audio_path)
    ]

    subprocess.run(cmd, check=True)

    return str(output_audio_path)


def replace_audio_in_video(video_path_str: str, new_audio_path_str: str, output_dir_str: str) -> str:

    video_path = Path(video_path_str)
    new_audio_path = Path(new_audio_path_str)
    output_dir = Path(output_dir_str)

    # Create a unique, descriptive filename for the final video.
    output_filename = f"{video_path.stem}_audio_replaced.mp4"
    output_video_path = output_dir / output_filename

    # This FFmpeg command is highly efficient.
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite existing files
        "-i", str(video_path),  # Input 0: The video file
        "-i", str(new_audio_path),  # Input 1: The new audio file
        "-c:v", "copy",  # CRITICAL: Stream copy video, no re-encoding, very fast!
        "-map", "0:v:0",  # Map the video stream from the first input
        "-map", "1:a:0",  # Map the audio stream from the second input
        "-shortest",  # Finish when the shorter of the two streams ends
        str(output_video_path)
    ]

    print(f"Executing FFmpeg to replace audio, saving to: {output_video_path}")
    subprocess.run(cmd, check=True)

    return str(output_video_path)
