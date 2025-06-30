from pathlib import Path
from src.preprocessing.filler import transcribe_audio
from google import genai
from dotenv import load_dotenv
import os

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

def get_summary(audio_path):
    try:
        transcription = transcribe_audio(Path(audio_path), model_size="medium")
        prompt = f"""You are an AI assistant specialized in summarizing spoken audio content. 
        Summarize the following transcript clearly and concisely. Include the main ideas, key points, and any important statements. 
        Keep the summary informative, engaging, and structured in natural language.
        Transcription:
        {transcription["full_text"]}"""
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt)
        return response.text.strip()
    except Exception as e:
        return f"Summarization failed: {str(e)}"

