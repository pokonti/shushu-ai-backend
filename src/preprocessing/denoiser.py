from dotenv import load_dotenv
from pydub import AudioSegment
import noisereduce as nr
import numpy as np
from pathlib import Path
import os
import httpx
import asyncio


load_dotenv()

CLEANVOICE_BASE_URL = "https://api.cleanvoice.ai"
CLEANVOICE_API_KEY = os.getenv("CLEANVOICE_API_KEY")
CLEANVOICE_HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": CLEANVOICE_API_KEY
}

async def process_audio_from_url(public_audio_url: str, options: dict) -> str:
    """
    Submits a job to Cleanvoice using a public URL, polls for completion,
    and returns the URL of the processed audio file.
    """
    if not CLEANVOICE_API_KEY:
        raise ValueError("CLEANVOICE_API_KEY is not set. Please check your .env file.")

    edit_api_url = f"{CLEANVOICE_BASE_URL}/v2/edits"

    payload = {
        "input": {
            "files": [public_audio_url],
            "config": {
                "remove_noise": options.get("denoise", False),
                "remove_fillers": options.get("remove_fillers", False)
            }
        }
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        # --- Step 1: Submit the editing job ---
        print("Submitting job to Cleanvoice...")
        try:
            submit_response = await client.post(edit_api_url, headers=CLEANVOICE_HEADERS, json=payload)
            if submit_response.status_code == 401: raise Exception("Cleanvoice Error: Invalid API Key.")
            if submit_response.status_code == 422:
                error_details = submit_response.json()
                raise Exception(
                    f"Cleanvoice Error [422 - Unprocessable Entity]: {error_details.get('detail', 'Invalid payload data')}")
            submit_response.raise_for_status()
        except httpx.RequestError as e:
            raise Exception(f"A network error occurred while submitting the job to Cleanvoice: {e}")

        job_data = submit_response.json()
        edit_id = job_data.get("id")
        if not edit_id: raise Exception("Failed to get a valid job ID from Cleanvoice.")
        print(f"Cleanvoice job submitted with ID: {edit_id}")

        # --- Step 2: Poll for the result ---
        status_url = f"{CLEANVOICE_BASE_URL}/v2/edits/{edit_id}"
        max_polls = 30
        for attempt in range(max_polls):
            print(f"Checking status for job {edit_id} (Attempt {attempt + 1}/{max_polls})...")
            try:
                status_response = await client.get(status_url, headers=CLEANVOICE_HEADERS)
                status_response.raise_for_status()
            except httpx.RequestError as e:
                print(f"Network error while polling status: {e}. Retrying...")
                await asyncio.sleep(10)
                continue

            status_data = status_response.json()
            status = status_data.get("status")

            # --- MODIFICATION START ---
            if status in ["done", "SUCCESS"]:
                print(f"Cleanvoice processing finished with status: {status}.")

                # Correctly extract the URL from the 'download_url' field
                result_object = status_data.get("result", {})
                processed_url = result_object.get("download_url")

                if not processed_url:
                    raise Exception("Job finished, but 'download_url' was not found in the result.")

                print(f"Successfully retrieved processed file URL.")
                return processed_url

            elif status == "failed":
                error_message = status_data.get("error", "An unknown error occurred.")
                raise Exception(f"Cleanvoice processing failed: {error_message}")

            # Recognize all known "in-progress" statuses
            elif status in ["pending", "processing", "PREPROCESSING", "EXPORT"]:
                print(f"Current status is '{status}'. Waiting...")

            else:
                print(f"Received an unknown status: '{status}'. Continuing to poll.")
            # --- MODIFICATION END ---

            await asyncio.sleep(10)

        raise Exception(f"Cleanvoice job timed out after {max_polls * 10 / 60} minutes.")


# def denoise_audio_local(audio_file: str) -> str:
#     audio_path = Path(audio_file)
#     output_path = audio_path.with_name(f"{audio_path.stem}_denoised.wav")
#     print(f"Performing local denoising on {audio_file}...")
#     audio = AudioSegment.from_file(audio_file)
#     samples = np.array(audio.get_array_of_samples()).astype(np.float32)
#     if audio.channels == 2:
#         samples = samples.reshape((-1, 2)).mean(axis=1)
#     reduced_noise = nr.reduce_noise(y=samples, sr=audio.frame_rate)
#     denoised_audio = AudioSegment(reduced_noise.astype(np.int16).tobytes(), frame_rate=audio.frame_rate,
#                                   sample_width=audio.sample_width, channels=1)
#     denoised_audio.export(output_path, format="wav")
#     print(f"Local denoising successful. File saved to: {output_path}")
#     return str(output_path)


# def denoise_audio(audio_file: str) -> str:
#     audio_path = Path(audio_file)
#     output_path = audio_path.with_name(audio_path.stem + "_denoised.wav")
#
#     # Load audio
#     audio = AudioSegment.from_file(audio_file)
#
#     # Convert audio to numpy array
#     samples = np.array(audio.get_array_of_samples()).astype(np.float32)
#
#     # If stereo, convert to mono by averaging channels
#     if audio.channels == 2:
#         samples = samples.reshape((-1, 2))
#         samples = samples.mean(axis=1)
#
#     # Apply noise reduction
#     reduced_noise = nr.reduce_noise(y=samples, sr=audio.frame_rate)
#
#     # Convert back to AudioSegment
#     reduced_audio = AudioSegment(
#         reduced_noise.astype(np.int16).tobytes(),
#         frame_rate = audio.frame_rate,
#         sample_width = audio.sample_width,
#         channels = audio.channels
#     )
#
#     try:
#         reduced_audio.export(output_path, format="wav")
#         print("Export successful:", output_path)
#     except Exception as e:
#         print("Export failed:", e)
#         raise e
#
#     return str(output_path)


# async def main():
#     audio_url = "https://shushu-space.fra1.digitaloceanspaces.com/users/1/originals/20250627102852_4be188a6-0448-494d-b3fb-87a9d13cd74e.wav"
#     options = {"denoise": True, "remove_fillers": False}
#     try:
#         processed_url = await process_audio_from_url(audio_url, options)
#         print(f"\nSuccessfully processed audio. You can download it from: {processed_url}")
#     except Exception as e:
#         print(f"\nAn error occurred: {e}")
#

# if __name__ == "__main__":
#     asyncio.run(main())
#