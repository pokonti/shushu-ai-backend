from pydub import AudioSegment
from moviepy import VideoFileClip, concatenate_videoclips, CompositeVideoClip
from moviepy.video.fx  import CrossFadeIn
from moviepy.audio.fx import AudioFadeIn
from pathlib import Path
from faster_whisper import WhisperModel

def transcribe_audio(
    file_path: Path,
    model_size: str,
    compute_type: str = "float32",
) -> dict:
    try:
        model = WhisperModel(model_size, compute_type=compute_type)

        segments, info = model.transcribe(file_path,
                                          initial_prompt="Transcribe everything exactly as spoken,"
                                                         "including ums and uhs, and absolutely all filler words",
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
        full_text = " ".join(words_print)

        return {
            "full_text": [full_text],
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

def get_filler_timestamps_from_audio(audio_path: str) -> list[dict]:
    """
    Transcribes the audio using base and medium models, aligns timestamps,
    and returns filler word timestamps.
    """
    audio_path = Path(audio_path)
    # Step 1: Transcribe with base and medium models
    base = transcribe_audio(audio_path, model_size="base")
    medium = transcribe_audio(audio_path, model_size="medium")

    # Step 2: Align timestamps
    aligned = align_transcripts(base["words"], medium["words"])

    # Step 3: Extract filler word timestamps
    filler_times = get_filler_word_timestamps(aligned)

    return filler_times


def get_filler_word_timestamps(words: list) -> list:
    FILLER_WORDS = {"um", "uh", "like", "yeah", "er", "ah", "basically", "mm", "aa"}

    return [
        {"start": word["start"], "end": word["end"]}
        for word in words
        if word["word"].lower() in FILLER_WORDS
    ]

def align_transcripts(base_words, medium_words, time_tolerance=0.5):
    """
    Aligns word timestamps from base and medium Whisper model outputs.

    For matching words (case-insensitive), replaces base timestamps with medium’s if within time tolerance.
    Keeps fillers from base even if unmatched.

    Returns:
        List of {'word', 'start', 'end'} with best available timestamps.
    """
    aligned = []
    used_indices = set()

    for bw in base_words:
        word = bw["word"].lower()
        best_match = None
        best_diff = float("inf")

        for idx, mw in enumerate(medium_words):
            if idx in used_indices:
                continue
            if mw["word"].lower() != word:
                continue

            # Match found — check time proximity
            time_diff = abs(bw["start"] - mw["start"])
            if time_diff < best_diff and time_diff <= time_tolerance:
                best_diff = time_diff
                best_match = (idx, mw)

        if best_match:
            idx, mw = best_match
            used_indices.add(idx)
            aligned.append({
                "word": word,
                "start": mw["start"],
                "end": mw["end"]
            })
        else:
            # No match or out of sync — keep original
            aligned.append(bw)

    return aligned



def remove_filler_words_from_audio(audio_path: str, filler_timestamps: list = None,  output_path: str = None) -> str:
    """
    Removes filler word segments from audio based on their start and end times.
    """
    if filler_timestamps is None:
        filler_timestamps = get_filler_timestamps_from_audio(audio_path)

    audio = AudioSegment.from_file(audio_path)
    cleaned_audio = AudioSegment.empty()

    prev_end = 0
    for filler in filler_timestamps:
        cleaned_audio += audio[prev_end * 1000:filler["start"] * 1000]
        prev_end = filler["end"]

    cleaned_audio += audio[prev_end * 1000:]

    output_path = output_path or Path(audio_path).with_name(Path(audio_path).stem + "_no_filler.wav")
    cleaned_audio.export(output_path, format="wav")
    return str(output_path)


def remove_filler_words_from_video(video_path: str, filler_timestamps: list, output_path: str = None) -> str:
    """
    Removes filler word segments from media based on timestamps.
    """
    video = None
    final_clip = None
    try:
        # Load the main video file
        video = VideoFileClip(video_path)
        segments = []

        # Create the list of subclips to keep
        prev_end = 0
        for filler in filler_timestamps:
            if filler["start"] > prev_end:
                segments.append(video.subclipped(prev_end, filler["start"]))
            prev_end = filler["end"]

        # Add the final segment after the last filler word
        if prev_end < video.duration:
            segments.append(video.subclipped(prev_end, video.duration))

        # If there are segments to concatenate, do so
        if segments:
            final_clip = concatenate_videoclips(segments)

            # Determine the output path
            if not output_path:
                output_path = Path(video_path).with_name(Path(video_path).stem + "_no_filler.mp4")

            # Write the final video to a file
            final_clip.write_videofile(str(output_path), codec="libx264", audio_codec="aac")

            return str(output_path)
        else:
            # If no segments were created (e.g., the whole video was a filler),
            # return the original path as there is nothing to process.
            print("Warning: No segments were left after removing fillers. Returning original path.")
            return video_path

    finally:
        # --- THIS IS THE CRITICAL CLEANUP BLOCK ---
        # This 'finally' block ensures that the .close() methods are called
        # no matter what happens, even if an error occurs.
        print("Cleaning up video resources...")
        if video:
            video.close()
        if final_clip:
            final_clip.close()

    video = VideoFileClip(video_path)
    segments = []

    prev_end = 0
    for filler in filler_timestamps:
        if filler["start"] > prev_end:
            segments.append(video.subclipped(prev_end, filler["start"]))
        prev_end = filler["end"]

    if prev_end < video.duration:
        segments.append(video.subclipped(prev_end, video.duration))

    final = concatenate_videoclips(segments)
    output_path = output_path or Path(video_path).with_name(Path(video_path).stem + "_no_filler.mp4")
    final.write_videofile(str(output_path), codec="libx264", audio_codec="aac")
    video.close()

    return str(output_path)

def remove_filler_words_smooth(video_path: str,
                            filler_timestamps: list,
                            output_path: str = None,
                            transition_duration: float = 0.15) -> str:
    """
    Professional-grade filler word removal with proper CrossFadeIn transitions.

    Args:
        video_path: Input media path
        filler_timestamps: List of {'start':, 'end':} dicts
        output_path: Optional output path
        transition_duration: Crossfade duration (0.1-1.0 seconds)

    Returns:
        Path to processed media
    """
    # Load media
    video = VideoFileClip(video_path)
    clips = []

    # Sort timestamps chronologically
    filler_timestamps = sorted(filler_timestamps, key=lambda x: x['start'])

    # Build clips with transitions
    prev_end = 0
    for i, filler in enumerate(filler_timestamps):
        if filler["start"] > prev_end:
            clip = video.subclipped(prev_end, filler["start"])

            # Apply crossfade to all clips except first
            if i > 0:
                clip = CompositeVideoClip([
                    clip.with_effects([
                        CrossFadeIn(transition_duration),
                        AudioFadeIn(transition_duration)
                    ])
                ])

            clips.append(clip)

        prev_end = filler["end"]

    # Add final clip
    if prev_end < video.duration:
        final_clip = video.subclipped(prev_end, video.duration)
        if clips:  # Apply fade if not first clip
            final_clip = CompositeVideoClip([
                final_clip.with_effects([
                    CrossFadeIn(transition_duration),
                    AudioFadeIn(transition_duration)
                ])
            ])
        clips.append(final_clip)

    final = concatenate_videoclips(
        clips,
        method="compose",
        padding=-transition_duration if len(clips) > 1 else 0
    )

    output_path = output_path or Path(video_path).with_name(
        f"{Path(video_path).stem}_pro_filler.mp4"
    )

    final.write_videofile(
        str(output_path),
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="ultrafast",
        ffmpeg_params=["-crf", "24", "-movflags", "+faststart"]
    )

    return str(output_path)
