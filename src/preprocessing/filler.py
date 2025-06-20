from fastapi.responses import JSONResponse
from fastapi import HTTPException

from pydub import AudioSegment
from pathlib import Path
from moviepy import VideoFileClip, concatenate_videoclips

from src.preprocessing.service import transcribe_audio, find_video_file


def get_filler_word_timestamps(words: list) -> list:
    FILLER_WORDS = {"um", "uh", "like", "so", "actually", "basically", "yeah"}

    return [
        {"start": word["start"], "end": word["end"]}
        for word in words
        if word["word"].lower() in FILLER_WORDS
    ]


def remove_filler_words_from_audio(audio_path: str, filler_timestamps: list, output_path: str = None) -> str:
    """
    Removes filler word segments from audio based on their start and end times.
    """
    audio = AudioSegment.from_file(audio_path)
    cleaned_audio = AudioSegment.empty()

    prev_end = 0
    for filler in filler_timestamps:
        cleaned_audio += audio[prev_end * 1000:filler["start"] * 1000]
        prev_end = filler["end"]

    cleaned_audio += audio[prev_end * 1000:]

    output_path = output_path or Path(audio_path).with_name(Path(audio_path).stem + "_cleaned.wav")
    cleaned_audio.export(output_path, format="wav")
    return str(output_path)


def remove_filler_words_from_video(video_path: str, filler_timestamps: list, output_path: str = None) -> str:
    """
    Removes filler word segments from video based on timestamps.
    """
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
    output_path = output_path or Path(video_path).with_name(Path(video_path).stem + "_cleaned.mp4")
    final.write_videofile(str(output_path), codec="libx264", audio_codec="aac")
    return str(output_path)


from moviepy import VideoFileClip, concatenate_videoclips, CompositeVideoClip
from moviepy.video.fx  import CrossFadeIn
from moviepy.audio.fx import AudioFadeIn
from pathlib import Path
from typing import List


def remove_filler_words_smooth(video_path: str,
                            filler_timestamps: List[dict],
                            output_path: str = None,
                            transition_duration: float = 0.3) -> str:
    """
    Professional-grade filler word removal with proper CrossFadeIn transitions.

    Args:
        video_path: Input video path
        filler_timestamps: List of {'start':, 'end':} dicts
        output_path: Optional output path
        transition_duration: Crossfade duration (0.1-1.0 seconds)

    Returns:
        Path to processed video
    """
    # Load video
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

    # Concatenate with composition
    final = concatenate_videoclips(
        clips,
        method="compose",
        padding=-transition_duration if len(clips) > 1 else 0
    )

    # Configure output
    output_path = output_path or Path(video_path).with_name(
        f"{Path(video_path).stem}_pro_clean.mp4"
    )

    # Optimized render settings
    final.write_videofile(
        str(output_path),
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="fast",
        ffmpeg_params=["-crf", "22", "-movflags", "+faststart"]
    )

    return str(output_path)

# def align_transcripts(base_words, medium_words, time_tolerance=0.5):
#     """
#     Aligns word timestamps from base and medium Whisper model outputs.
#
#     - base_words: list of {'word', 'start', 'end'} with fillers, less accurate timestamps
#     - medium_words: list of {'word', 'start', 'end'} with precise timestamps, no fillers
#     - time_tolerance: max time difference in seconds allowed when matching words
#
#     Returns:
#         list of {'word', 'start', 'end'} — using base words and medium timestamps where possible
#     """
#     aligned = []
#     j = 0  # index for medium_words
#
#     for bw in base_words:
#         word = bw["word"].lower()
#
#         # Try to match with medium_words
#         while j < len(medium_words):
#             mw = medium_words[j]
#             j += 1
#
#             if mw["word"].lower() == word:
#                 # Match found → take timestamps from medium
#                 aligned.append({
#                     "word": word,
#                     "start": mw["start"],
#                     "end": mw["end"]
#                 })
#                 break
#         else:
#             # No match → use base model timestamps (likely a filler word)
#             aligned.append({
#                 "word": word,
#                 "start": bw["start"],
#                 "end": bw["end"]
#             })
#
#     return aligned
def align_transcripts(base_words, medium_words, time_tolerance=0.6):
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

UPLOAD_DIR = Path("video")
UPLOAD_DIR.mkdir(exist_ok=True)
AUDIO_DIR = Path("audio")
AUDIO_DIR.mkdir(exist_ok=True)

def remove_filler_words(media_id: str):
    try:
        audio_path = AUDIO_DIR / f"{media_id}.wav"
        video_path = find_video_file(media_id, UPLOAD_DIR)

        if not audio_path.exists():
            raise HTTPException(status_code=404, detail="Audio file not found")

        filler_times = get_filler_timestamps_from_audio(str(audio_path))

        cleaned_audio_path = remove_filler_words_from_audio(str(audio_path), filler_times)

        response = {
            "message": "Filler words removed successfully",
            "cleaned_audio": cleaned_audio_path,
            "filler_timestamps": filler_times,
        }

        # Optionally remove filler words from video
        if video_path.exists():
            cleaned_video_path = remove_filler_words_from_video(str(video_path), filler_times)
            response["cleaned_video"] = cleaned_video_path

        return JSONResponse(content=response)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})



