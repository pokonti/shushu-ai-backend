from pathlib import Path
from typing import List

from openai import AzureOpenAI
from faster_whisper import WhisperModel
from dotenv import load_dotenv
import os
import re
import json

from src.shorts.ai.schemas import Moment, AllMoments

load_dotenv()

AZURE_OAI_ENDPOINT = os.getenv("AZURE_OAI_ENDPOINT")
AZURE_OAI_KEY = os.getenv("AZURE_OAI_KEY")
AZURE_GPT_DEPLOYMENT = os.getenv("AZURE_GPT4_DEPLOYMENT")

client = AzureOpenAI(
    api_version="2024-08-01-preview",
    azure_endpoint=AZURE_OAI_ENDPOINT,
    api_key=AZURE_OAI_KEY,
)

#
def transcribe_audio(file_path: Path, model_size: str, compute_type: str = "float32") -> dict:
    try:
        model = WhisperModel(model_size, compute_type=compute_type)

        segments, info = model.transcribe(
            file_path,
            initial_prompt="Transcribe everything exactly as spoken.",
            vad_filter=False,
            suppress_tokens=[],
            beam_size=5,
            word_timestamps=True,
            condition_on_previous_text=False
        )

        # sentence-level output
        sentences = []
        full_text = []

        for segment in segments:
            if segment.text:
                sentence = segment.text.strip()
                sentences.append({
                    "start": round(segment.start, 2),
                    "end": round(segment.end, 2),
                    "text": sentence
                })
                full_text.append(sentence)

        return {
            "full_text": " ".join(full_text),  # joined string
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "sentences": sentences  # list of sentence chunks with timestamps
        }


    except Exception as e:
        print("Transcription failed:", e)
        return {
            "error": str(e),
            "sentences": [],
            "full_text": ""
        }

# print("Loading Faster Whisper model into memory (this may take a moment)...")
# try:
#     # Use more efficient settings for production on a CPU
#     # "medium" is a good balance, but "base" or "small" use less memory.
#     # "int8" is significantly faster and uses less RAM than "float32".
#     _model = WhisperModel("medium", device="cpu", compute_type="int8")
#     print("✅ Whisper model loaded successfully.")
# except Exception as e:
#     print(f"❌ FATAL ERROR: Could not load Whisper model. Error: {e}")
#     # If the model fails to load, subsequent calls will fail gracefully.
#     _model = None
#
#
# def transcribe_audio(file_path: str) -> dict:
#     """
#     Transcribes an audio file using the pre-loaded Faster Whisper model and
#     returns a dictionary with the full text and sentence-level timestamps.
#
#     Args:
#         file_path (str): The path to the local audio file.
#
#     Returns:
#         A dictionary containing the transcription results or an error.
#     """
#     # Check if the model was loaded successfully when the worker started.
#     if not _model:
#         raise RuntimeError("Whisper model is not loaded. Cannot perform transcription.")
#
#     try:
#         print(f"Transcribing audio file: {Path(file_path).name}...")
#         # The 'model' is now the pre-loaded '_model' instance.
#         # We no longer call WhisperModel() inside the function.
#         segments_generator, info = _model.transcribe(
#             file_path,
#             beam_size=5,
#             word_timestamps=True,  # Set to True to get word-level details for sentence reconstruction
#         )
#
#         # Process the generator to get sentence-level output
#         sentences = []
#         full_text_list = []
#
#         for segment in segments_generator:
#             # The 'segment' object from faster-whisper already represents
#             # a sentence-like chunk with start and end times.
#             sentence_text = segment.text.strip()
#             if sentence_text:
#                 sentences.append({
#                     "start": round(segment.start, 2),
#                     "end": round(segment.end, 2),
#                     "text": sentence_text
#                 })
#                 full_text_list.append(sentence_text)
#
#         full_text = " ".join(full_text_list)
#         print("Transcription successful.")
#
#         return {
#             "full_text": full_text,
#             "language": info.language,
#             "language_probability": round(info.language_probability, 3),
#             "sentences": sentences
#         }
#
#     except Exception as e:
#         print(f"❌ Transcription failed: {e}")
#         return {
#             "error": str(e),
#             "full_text": "",
#             "sentences": []
#

def get_info_for_shorts(audio_path):
    try:
        # Transcribe with sentence-level timestamps
        transcription = transcribe_audio(Path(audio_path), model_size="base")
        segments = transcription.get("sentences", [])

        if not segments:
            return "No transcript segments found."

        formatted_transcript = "\n".join([
            f"[{s['start']} - {s['end']}] {s['text']}" for s in segments
        ])

        prompt = f"""
        You are a professional video editor assistant.

        Analyze the transcript below and extract 3 to 5 memorable, emotional, or insightful moments suitable for TikTok or Reels.

        For **each moment**, return:
        - "timestamp": start and end in seconds
        - "highlight": a sentence taken **directly and exactly** from the transcript
        - "b_roll_suggestion": describe what kind of **visual footage** could represent that sentence (visually representable)
        - "keywords": 3–5 search terms suitable for Pexels video search (based on visual concepts in the sentence)

        ⚠️ Do not rewrite the transcript. Use only exact sentences.
        🎬 Suggest B-roll only for things that can be visually shown (not abstract ideas).
        ⚠️ Avoid abstract or psychological keywords like "transformation", "growth", "change", "mindfulness", etc. Instead, convert them into **visual equivalents**.
        ⚠️ If there is a concrete example, like an artist name, or a certain word, suggest it in keywords
        ✅ GOOD: For "inner transformation" use keywords like "new day", "person walking forward", "road ahead"
        ❌ BAD: Do not use keywords like "transformation", "personal growth", or "mental clarity", instead suggest words like: "sport", "book" and etc which are related with transformation
        Give keywords related with people, nature, there was a case you gave a word "observation" and pexel api gave a video of an eye and that was really scary, i don't know how, but control such situations
        🎬 Suggest B-roll only for things that can be **shown on screen** – avoid things that cannot be filmed directly.

        i have model like this:
        class Moment(BaseModel):
        timestamp: str
        highlight: str
        b_roll_suggestion: str
        keywords: List[str]

        class AllMoments(BaseModel):
            moments: List[Moment]


        so return me with the format of AllMoments, a list of 3-5 moment dictionaries.

        Respond with a valid **JSON list** of 3 to 5 objects, each following this format:
        [
          {{
            "timestamp": "0.0-6.4",
            "highlight": "Sleep is the foundation of all mental health.",
            "b_roll_suggestion": "Footage of someone peacefully sleeping in bed at night.",
            "keywords": ["sleep", "bedroom", "night"]
          }},
          ...
        ]

        Transcript:
        {formatted_transcript}
        """

        response = client.chat.completions.parse(
            model=AZURE_GPT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are a video editor assistant that creates social-ready shorts."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1200,
            temperature=0.6,
            response_format=AllMoments,

        )
        result = response.choices[0].message.parsed
        print(result)
        return result
    except Exception as e:
        return f"Generation failed: {str(e)}"


def extract_json_from_gpt_response(raw: str):
    try:
        # Strip Markdown triple backticks and optional "json"
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)

        # Parse JSON safely
        return json.loads(cleaned)
    except Exception as e:
        return {"error": "Failed to parse GPT output as JSON.", "raw": raw, "exception": str(e)}