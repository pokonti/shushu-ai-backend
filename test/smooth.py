from pathlib import Path
from moviepy import VideoFileClip, CompositeVideoClip
from moviepy.video.fx  import CrossFadeIn
from moviepy.audio.fx import AudioFadeIn
import os
from pathlib import Path


def remove_fillers_from_video_with_transitions(
        video_path: str,
        filler_timestamps: list,
        transition_duration: float = 0.15
) -> str:
    """
    Removes filler word segments from a video and applies smooth crossfades
    between the remaining clips, keeping audio and video perfectly synchronized.

    Args:
        video_path (str): The path to the input video file.
        filler_timestamps (list): A list of dictionaries, each with "start" and "end" keys.
        transition_duration (float): The duration of the crossfade in seconds.

    Returns:
        str: The path to the processed video file.
    """
    if not filler_timestamps:
        print("No filler timestamps provided. Returning original video path.")
        return video_path

    video = VideoFileClip(video_path)

    # --- Step 1: Isolate the "Good" Parts ---
    # Create a list of subclips that we want to keep.
    clips_to_keep = []
    last_end = 0
    for filler in sorted(filler_timestamps, key=lambda x: x['start']):
        if filler['start'] > last_end:
            clips_to_keep.append(video.subclipped(last_end, filler['start']))
        last_end = filler['end']

    # Add the final segment of the video after the last filler word.
    if last_end < video.duration:
        clips_to_keep.append(video.subclipped(last_end, video.duration))

    if not clips_to_keep:
        print("Processing resulted in an empty video. Returning original path.")
        return video_path

    # --- Step 2: Manually Composite with Crossfades ---
    # This is more robust than concatenate_videoclips for transitions.
    final_clips = []
    current_time = 0
    for i, clip in enumerate(clips_to_keep):
        if i == 0:
            # --- THE CHANGE IS HERE ---
            # The first clip starts at time 0. Use .set_pos() instead of .set_start()
            final_clips.append(clip.pos(0))
            current_time = clip.duration
        else:
            start_time = current_time - transition_duration

            # --- THE CHANGE IS HERE ---
            # Use .set_pos() to position the clip, then apply the crossfade.
            faded_clip = clip.pos(start_time).CrossFadeIn(transition_duration)
            final_clips.append(faded_clip)

            current_time = start_time + clip.duration

    # --- Step 3: Assemble and Render ---
    final_duration = current_time
    final_composition = CompositeVideoClip(final_clips, size=video.size).set_duration(final_duration)

    output_path = Path(video_path).with_name(f"{Path(video_path).stem}_smooth_cut.mp4")

    final_composition.write_videofile(
        str(output_path),
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="fast",
        ffmpeg_params=["-crf", "22", "-movflags", "+faststart"]
    )

    # Close the clips to release memory
    video.close()
    for clip in clips_to_keep:
        clip.close()
    final_composition.close()

    return str(output_path)


if __name__ == "__main__":

    print("--- Starting Test for remove_fillers_from_video_with_transitions ---")

    # --- 1. Define Test Inputs ---

    VIDEO_FILENAME = "1.mov"

    # This is a mock list of timestamps. In the real app, this would come from
    # the get_filler_timestamps_from_audio() function.
    MOCK_TIMESTAMPS = [
        {"start": 2.5, "end": 3.1, "word": "um"},  # Cut out from 2.5s to 3.1s
        {"start": 7.8, "end": 8.5, "word": "like"},  # Cut out from 7.8s to 8.5s
        {"start": 11.2, "end": 11.5, "word": "uh"},  # Cut out from 11.2s to 11.5s
        {"start": 15.0, "end": 16.2, "word": "so"},  # Cut out from 15.0s to 16.2s
    ]

    # --- 2. Locate the Video File ---

    # Assumes you run this script from the project's root directory.
    # It constructs the full path to the video file.
    try:
        project_root = Path.cwd()
        video_full_path = project_root / VIDEO_FILENAME

        if not video_full_path.exists():
            raise FileNotFoundError(
                f"Test video not found at '{video_full_path}'. "
            )

        print(f"Found test video at: {video_full_path}")
        print(f"Using mock timestamps: {MOCK_TIMESTAMPS}")

        # --- 3. Execute the Function ---

        print("\nCalling the function...")
        processed_video_path = remove_fillers_from_video_with_transitions(
            video_path=str(video_full_path),
            filler_timestamps=MOCK_TIMESTAMPS,
            transition_duration=0.15  # You can test different durations here
        )

        # --- 4. Report the Result ---

        print("\n--- TEST COMPLETE ---")
        if Path(processed_video_path).exists():
            print("✅ Success! The function executed without errors.")
            print(f"🎥 Processed video saved to: {processed_video_path}")
        else:
            print("❌ Error! The function ran but the output file was not created.")

    except Exception as e:
        print(f"\n--- TEST FAILED ---")
        print(f"❌ An error occurred during the test: {e}")