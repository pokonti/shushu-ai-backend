from pydub import AudioSegment
from pathlib import Path
from moviepy import VideoFileClip, concatenate_videoclips


def get_filler_word_timestamps(words: list) -> list:
    FILLER_WORDS = {"um", "uh", "like", "you know", "so", "actually", "basically", "yeah"}

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



def align_transcripts(base_words, medium_words, time_tolerance=0.5):
    """
    Aligns word timestamps from base and medium Whisper model outputs.

    - base_words: list of {'word', 'start', 'end'} with fillers, less accurate timestamps
    - medium_words: list of {'word', 'start', 'end'} with precise timestamps, no fillers
    - time_tolerance: max time difference in seconds allowed when matching words

    Returns:
        list of {'word', 'start', 'end'} — using base words and medium timestamps where possible
    """
    aligned = []
    j = 0  # index for medium_words

    for bw in base_words:
        word = bw["word"].lower()

        # Try to match with medium_words
        while j < len(medium_words):
            mw = medium_words[j]
            j += 1

            if mw["word"].lower() == word:
                # Match found → take timestamps from medium
                aligned.append({
                    "word": word,
                    "start": mw["start"],
                    "end": mw["end"]
                })
                break
        else:
            # No match → use base model timestamps (likely a filler word)
            aligned.append({
                "word": word,
                "start": bw["start"],
                "end": bw["end"]
            })

    return aligned
