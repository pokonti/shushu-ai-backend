from pathlib import Path
import subprocess


def extract_audio_from_video(
        video_path_str: str,
        output_path_str: str = None
) -> str:
    """
    Extracts audio from a video file using FFmpeg and saves it as a WAV file.

    Args:
        video_path_str (str): The path to the input video file.
        output_path_str (str, optional): The full, exact path to save the output audio file.
                                         If None, it saves a .wav file with the same name
                                         in the same directory as the video.

    Returns:
        The path to the extracted audio file.
    """
    video_path = Path(video_path_str)

    # --- THIS IS THE KEY CHANGE ---
    # 1. Determine the output path.
    if output_path_str:
        # If an explicit output path is provided, use it.
        output_audio_path = Path(output_path_str)
    else:
        # If no path is provided, create a default one.
        # e.g., "my_video.mp4" -> "my_video.wav"
        output_audio_path = video_path.with_suffix(".wav")

    # Ensure the parent directory for the output file exists.
    output_audio_path.parent.mkdir(parents=True, exist_ok=True)

    # 2. Construct the FFmpeg command using the final output path.
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output file if it exists
        "-i", str(video_path),  # Input video
        "-vn",  # No video output (discard video stream)
        "-acodec", "pcm_s16le",  # Use WAV codec for uncompressed audio quality
        "-ar", "16000",  # Standard sample rate for speech recognition
        "-ac", "1",  # Convert to mono channel
        str(output_audio_path)
    ]

    print(f"Running FFmpeg to extract audio to: {output_audio_path}")

    try:
        # 3. Execute the command.
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Audio extraction successful.")
        return str(output_audio_path)
    except subprocess.CalledProcessError as e:
        # If FFmpeg fails, print its detailed error output for easier debugging.
        print("❌ FFmpeg audio extraction failed.")
        print(f"FFmpeg stderr:\n{e.stderr}")


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
