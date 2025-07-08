from pathlib import Path
from src.preprocessing.filler import transcribe_audio
from openai import AzureOpenAI
from dotenv import load_dotenv
import os

load_dotenv()

AZURE_OAI_ENDPOINT = os.getenv("AZURE_OAI_ENDPOINT")
AZURE_OAI_KEY = os.getenv("AZURE_OAI_KEY")
AZURE_GPT_DEPLOYMENT = os.getenv("AZURE_GPT4_DEPLOYMENT")

client = AzureOpenAI(
    api_version="2024-05-01-preview",
    azure_endpoint=AZURE_OAI_ENDPOINT,
    api_key=AZURE_OAI_KEY,
)


async def get_summary(audio_path):
    try:
        transcription = transcribe_audio(Path(audio_path), model_size="base")
        prompt = f"""
            You are an AI assistant specialized in summarizing spoken audio content.
            Summarize the following transcript clearly and concisely. Include the main ideas, key points, and any important statements.
            Keep the summary informative, engaging, and structured in natural language.

            Transcription:
            ---
            {transcription}
            ---
            """

        response = client.chat.completions.create(
            model=AZURE_GPT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that excels at summarization."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=250,  # Limit the summary length
            temperature=0.5,  # Make the summary more focused and less random
        )
        print("Summarization successful.")
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Summarization failed: {str(e)}"


# if __name__ == "__main__":
#
#     async def main_test():
#         """A simple async function to test the full transcription and summarization pipeline."""
#
#         print("--- Starting Azure AI Audio Summary Test ---")
#         test_file = "../test/3bbcc845c3ba478caa864536bea26814_clean.wav"  # Make sure this file exists in your project root
#
#         if not os.path.exists(test_file):
#             print(f"\nERROR: Test file not found at '{test_file}'.")
#             return
#
#         # Call the main orchestrator function
#         final_summary = await get_summary(test_file)
#
#         print("\n--- ✅ Test Complete ---")
#         print("\n📝 Final Summary:")
#         print(final_summary)
#
#
#     # Run the async main function
#     asyncio.run(main_test())
