import asyncio
from pathlib import Path
import subprocess
import httpx
from dotenv import load_dotenv
import requests
import os


load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"

def search_broll_videos(keywords: list, orientation="portrait", max_results=1) -> list:
    """
    Searches Pexels for videos and returns a list of dictionaries containing
    the direct link to the highest quality video file.
    """
    headers = {"Authorization": PEXELS_API_KEY}
    results = []

    for keyword in keywords:
        params = {
            "query": keyword,
            "orientation": orientation,
            "per_page": max_results
        }
        try:
            res = requests.get("https://api.pexels.com/videos/search", params=params, headers=headers)
            res.raise_for_status()  # Check for HTTP errors

            data = res.json()
            for video in data.get("videos", []):
                # --- THIS IS THE KEY CHANGE ---
                # Find the video file with the highest resolution.
                if not video.get("video_files"):
                    continue

                # best_file = max(video["video_files"], key=lambda f: f.get("height", 0))
                best_file = min(
                    [f for f in video["video_files"] if f["width"] <= 720],
                    key=lambda f: f.get("height", 0),
                    default=None
                )

                # We store the direct download link, not the webpage url.
                results.append({
                    "keyword": keyword,
                    "download_url": best_file["link"],  # Use the 'link' from 'video_files'
                    "duration": video.get("duration"),
                    "width": best_file.get("width"),
                    "height": best_file.get("height")
                })
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch for '{keyword}': {e}")

    return results

async def download_video(client: httpx.AsyncClient, url: str, save_path: Path) -> Path | None:
    try:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            with open(save_path, "wb") as f:
                async for chunk in response.aiter_bytes():
                    f.write(chunk)
        print(f"✅ Downloaded: {save_path}")
        return save_path
    except httpx.RequestError as e:
        print(f"❌ Request error for {url}: {e}")
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP error for {url}: {e}")
    except Exception as e:
        print(f"❌ Unexpected error for {url}: {e}")
    return None

# async def download_broll_videos(video_data: list, save_directory: str) -> list:
#     """
#     Downloads one B-roll video per keyword group concurrently.
#     """
#     Path(save_directory).mkdir(exist_ok=True)
#     download_tasks = []
#
#     async with httpx.AsyncClient(timeout=300.0) as client:
#         for group_index, group in enumerate(video_data):
#             videos = group.get("videos", [])
#             if not videos:
#                 continue
#
#             # Take only the first video in the group
#             video_info = videos[0]
#             download_url = video_info.get("download_url")
#             keyword = video_info.get("keyword", "clip").replace(" ", "_")
#
#             if not download_url:
#                 print(f"⚠️ Missing download_url in video: {video_info}")
#                 continue
#
#             ext = Path(download_url).suffix or ".mp4"
#             filename = f"group{group_index}_{keyword}{ext}"
#             local_path = Path(save_directory) / filename
#
#             task = download_video(client, download_url, local_path)
#             download_tasks.append(task)
#
#         local_file_paths = await asyncio.gather(*download_tasks)
#         return [path for path in local_file_paths if path is not None]


# async def _download_video_with_limit(client: httpx.AsyncClient, url: str, save_path: Path):
#     """A wrapper for the download function that uses the semaphore."""
#     async with download_semaphore:
#         print(f"Acquired semaphore for downloading {Path(url).name}")
#         return await download_video(client, url, save_path)

async def download_broll_videos(video_data: list, save_directory: str, max_concurrent=2) -> list:
    Path(save_directory).mkdir(exist_ok=True)
    download_tasks = []

    download_semaphore = asyncio.Semaphore(max_concurrent)

    async with httpx.AsyncClient(timeout=300.0) as client:
        async def _download_video_with_limit(url, save_path):
            async with download_semaphore:
                print(f"Acquired semaphore for downloading {Path(url).name}")
                return await download_video(client, url, save_path)

        for group_index, group in enumerate(video_data):
            videos = group.get("videos", [])
            if not videos:
                continue

            video_info = videos[0]
            download_url = video_info.get("download_url")
            keyword = video_info.get("keyword", "clip").replace(" ", "_")

            if not download_url:
                print(f"⚠️ Missing download_url in video: {video_info}")
                continue

            ext = Path(download_url).suffix or ".mp4"
            filename = f"group{group_index}_{keyword}{ext}"
            local_path = Path(save_directory) / filename

            task = _download_video_with_limit(download_url, local_path)
            download_tasks.append(task)

        local_file_paths = await asyncio.gather(*download_tasks)
        return [path for path in local_file_paths if path is not None]

# async def download_broll_videos(video_data: list, save_directory: str) -> list:
#     Path(save_directory).mkdir(exist_ok=True)
#     download_tasks = []
#
#     async with httpx.AsyncClient(timeout=300.0) as client:
#         for group_index, group in enumerate(video_data):
#             videos = group.get("videos", [])
#             if not videos:
#                 continue
#
#             video_info = videos[0]
#             download_url = video_info.get("download_url")
#             keyword = video_info.get("keyword", "clip").replace(" ", "_")
#
#             if not download_url:
#                 print(f"⚠️ Missing download_url in video: {video_info}")
#                 continue
#
#             ext = Path(download_url).suffix or ".mp4"
#             filename = f"group{group_index}_{keyword}{ext}"
#             local_path = Path(save_directory) / filename
#
#             # 🔄 Use the semaphore-wrapped version
#             task = _download_video_with_limit(client, download_url, local_path)
#             download_tasks.append(task)
#
#         local_file_paths = await asyncio.gather(*download_tasks)
#         return [path for path in local_file_paths if path is not None]


def prepare_broll_insertions(video_metadata: list, downloaded_folder: str) -> list:
    broll_insertions = []

    for i, segment in enumerate(video_metadata):
        # Parse timestamp range
        try:
            start_str, end_str = segment["timestamp"].split("-")
            start_time = float(start_str)
            end_time = float(end_str)
            duration = end_time - start_time
        except Exception as e:
            print(f"⚠️ Failed to parse timestamp for segment {i}: {segment['timestamp']}")
            continue

        # Use the first available video in the segment
        if not segment["videos"]:
            print(f"⚠️ No videos for segment {i}")
            continue

        chosen_video = segment["videos"][0]  # or apply logic to pick best by resolution/duration
        video_url = chosen_video["download_url"]
        keyword = chosen_video["keywords"].replace(" ", "_")

        # Derive filename from URL (matches how we saved it)
        filename = Path(video_url).name
        broll_path = Path(downloaded_folder) / f"group{i}_{keyword}{Path(filename).suffix}"

        broll_insertions.append({
            "timestamp": start_time,
            "duration": duration,
            "broll_path": str(broll_path)
        })

    return broll_insertions

def concat_with_broll_ffmpeg(original_path: str, broll_insertions: list, output_path: str = "output.mp4"):
    if not broll_insertions:
        raise ValueError("No B-roll insertions provided.")

    for i, moment in enumerate(broll_insertions):

        # Parse start and end times from the 'timestamp' string (e.g., "10.5-15.2")
        try:
            start_time, end_time = map(float, moment['timestamp'].split('-'))
            duration_now = end_time - start_time
        except (ValueError, AttributeError) as e:
            print(f"Warning: Skipping moment due to invalid timestamp format: {moment.get('timestamp')}. Error: {e}")
            continue


    filter_parts = []
    concat_inputs = []
    input_args = ["-i", original_path]
    prev_time = 0

    # Add all B-roll video inputs
    for broll in broll_insertions:
        input_args += ["-i", broll["broll_path"]]

    for i, broll in enumerate(broll_insertions):
        start = start_time
        duration = duration_now
        end = start + duration

        # 1. Original video segment before B-roll (add scale)
        filter_parts.append(
            f"[0:v]trim={prev_time}:{start},setpts=PTS-STARTPTS,scale=720:1280[v{i}a]"
        )

        # 2. B-roll: trim, crop center, then scale
        filter_parts.append(
            f"[{i+1}:v]trim=0:{duration},setpts=PTS-STARTPTS,"
            f"crop='min(iw\\,720)':'min(ih\\,1280)',"
            f"scale=720:1280[v{i}b]"
        )

        concat_inputs += [f"[v{i}a]", f"[v{i}b]"]
        prev_time = end

    # Final segment after last B-roll (add scale)
    filter_parts.append(
        f"[0:v]trim={prev_time},setpts=PTS-STARTPTS,scale=720:1280[v_end]"
    )
    concat_inputs.append("[v_end]")

    # Concatenate all video segments
    filter_parts.append(
        f"{''.join(concat_inputs)}concat=n={len(concat_inputs)}:v=1:a=0[outv]"
    )
    # Use original audio as-is
    filter_parts.append("[0:a]anull[aout]")

    command = [
        "ffmpeg",
        *input_args,
        "-filter_complex", "; ".join(filter_parts),
        "-map", "[outv]",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-preset", "ultrafast",
        "-threads", "1",
        "-y",
        output_path
    ]

    print("▶️ Running FFmpeg with uniform scaling and center crop")
    subprocess.run(command, check=True)
    return output_path

from tempfile import TemporaryDirectory

def concat_with_broll_ffmpeg_light(original_path: str, broll_insertions: list, output_path: str = "output.mp4"):
    if not broll_insertions:
        raise ValueError("No B-roll insertions provided.")

    with TemporaryDirectory() as temp_dir:
        segment_paths = []

        # Step 1: Extract original and B-roll segments
        prev_end = 0.0

        for i, moment in enumerate(broll_insertions):
            try:
                start, end = map(float, moment['timestamp'].split("-"))
                duration = end - start
            except Exception as e:
                print(f"⚠️ Skipping invalid timestamp: {moment.get('timestamp')} — {e}")
                continue

            # 1. Extract segment BEFORE B-roll
            if start > prev_end:
                original_segment = Path(temp_dir) / f"original_before_{i}.mp4"
                subprocess.run([
                    "ffmpeg", "-ss", str(prev_end), "-t", str(start - prev_end),
                    "-i", original_path,
                    "-vf", "scale=720:1280",
                    "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac",
                    "-avoid_negative_ts", "make_zero",
                    "-y", str(original_segment)
                ], check=True)
                segment_paths.append(original_segment)

            # 2. Add B-roll segment
            broll_path = moment["broll_path"]
            broll_segment = Path(temp_dir) / f"broll_{i}.mp4"
            subprocess.run([
                "ffmpeg", "-ss", "0", "-t", str(duration),
                "-i", broll_path,
                "-vf", "crop='min(iw\\,720)':'min(ih\\,1280)',scale=720:1280",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "aac",
                "-avoid_negative_ts", "make_zero",
                "-y", str(broll_segment)
            ], check=True)
            segment_paths.append(broll_segment)

            prev_end = end

        # Final segment after last B-roll
        final_segment = Path(temp_dir) / f"original_after.mp4"
        subprocess.run([
            "ffmpeg", "-ss", str(prev_end),
            "-i", original_path,
            "-vf", "scale=720:1280",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            "-avoid_negative_ts", "make_zero",
            "-y", str(final_segment)
        ], check=True)
        segment_paths.append(final_segment)

        # Step 2: Create concat list
        concat_list_path = Path(temp_dir) / "concat_list.txt"
        with open(concat_list_path, "w") as f:
            for segment in segment_paths:
                f.write(f"file '{segment.as_posix()}'\n")

        # Step 3: Concatenate all segments
        subprocess.run([
            "ffmpeg", "-f", "concat", "-safe", "0",
            "-i", str(concat_list_path),
            "-c", "copy",
            "-y", output_path
        ], check=True)

        print(f"✅ Final video created at: {output_path}")
        return output_path

# def assemble_video_with_broll_overlay(
#         original_video_path: str,
#         broll_insertions: list,
#         output_path: str
# ) -> str:
#     """
#     Assembles a video by overlaying B-roll clips onto the original video
#     at specified timestamps, keeping the original audio track intact, using a
#     single complex FFmpeg command.
#
#     Args:
#         original_video_path (str): Path to the main video file (A-roll).
#         broll_insertions (list): A list of dictionaries, e.g.,
#                                  [{'timestamp': '10.5-15.2', 'broll_path': '/tmp/.../broll_1.mp4'}, ...]
#         output_path (str): The path for the final output video.
#
#     Returns:
#         The path to the generated output video.
#     """
#     if not broll_insertions:
#         print("Warning: No B-roll insertions provided. Nothing to assemble.")
#         # If there's no b-roll, you might want to just copy the original file or handle it differently.
#         # For now, we'll raise an error.
#         raise ValueError("No B-roll data to process.")
#
#     # --- Step 1: Build the FFmpeg command dynamically ---
#
#     # Start with the main input video
#     command = ['ffmpeg', '-y', '-i', original_video_path]
#
#     # Add each B-roll clip as an additional input
#     for insertion in broll_insertions:
#         command.extend(['-i', insertion['broll_path']])
#
#     # --- Step 2: Construct the complex filter string ---
#     filter_complex_parts = []
#
#     # [0:v] refers to the video stream of the first input (original_video_path)
#     # This variable will track the output of the last overlay operation.
#     last_video_stream = "[0:v]"
#
#     for i, moment in enumerate(broll_insertions):
#         # The input index for the first b-roll is 1, second is 2, etc.
#         broll_input_index = i + 1
#
#         # Parse start and end times from the 'timestamp' string (e.g., "10.5-15.2")
#         try:
#             start_time, end_time = map(float, moment['timestamp'].split('-'))
#             duration = end_time - start_time
#         except (ValueError, AttributeError) as e:
#             print(f"Warning: Skipping moment due to invalid timestamp format: {moment.get('timestamp')}. Error: {e}")
#             continue
#
#         # Part A: Prepare the B-roll clip.
#         # We scale it, ensure it has the same framerate, and trim it to the needed duration.
#         # The output of this filter chain is given a temporary name, e.g., [broll0_prepped]
#         prepped_broll_stream = f"[broll{i}_prepped]"
#         filter_complex_parts.append(
#             f"[{broll_input_index}:v]"
#             f"scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"  # Scale and pad to 1920x1080
#             f"fps=30,"  # Standardize frame rate
#             f"trim=duration={duration},"
#             f"setpts=PTS-STARTPTS"
#             f"{prepped_broll_stream}"
#         )
#
#         # Part B: Overlay the prepared B-roll onto the video stream from the previous step.
#         # The result of this overlay is given a new name for the next iteration, e.g., [v1]
#         output_stream_name = f"[v{i + 1}]"
#         filter_complex_parts.append(
#             f"{last_video_stream}{prepped_broll_stream}"
#             f"overlay=enable='between(t,{start_time},{end_time})'"
#             f"{output_stream_name}"
#         )
#         # The output of this step becomes the input for the next overlay.
#         last_video_stream = output_stream_name
#
#     # Join all the filter parts together with semicolons
#     filter_complex_string = ";".join(filter_complex_parts)
#
#     command.extend(['-filter_complex', filter_complex_string])
#
#     # --- Step 3: Map the final streams and set encoding options ---
#     command.extend([
#         '-map', last_video_stream,  # Map the final, fully processed video stream
#         '-map', '0:a?',  # Map the audio from the FIRST input (the original video)
#         '-c:v', 'libx264',  # Use a standard, high-compatibility video codec
#         '-preset', 'ultrafast',  # Optimize for speed over file size
#         '-c:a', 'aac',  # Use a standard audio codec
#         '-shortest',  # Finish encoding when the shortest input stream (the video) ends
#         output_path
#     ])
#
#     # --- Step 4: Execute the FFmpeg command ---
#     print("▶️ Assembling final video with FFmpeg...")
#     # print("Generated Command:", " ".join(command)) # Uncomment for deep debugging
#
#     try:
#         # Use subprocess.run to execute the command.
#         # check=True will raise an exception if FFmpeg returns a non-zero exit code.
#         # capture_output=True and text=True will capture stderr for debugging.
#         result = subprocess.run(command, check=True, capture_output=True, text=True)
#         print(f"✅ Video assembly successful. Output saved to: {output_path}")
#         return output_path
#     except subprocess.CalledProcessError as e:
#         # If FFmpeg fails, print its detailed error output.
#         print(f"❌ FFmpeg assembly failed with exit code {e.returncode}.")
#         print(f"FFmpeg stderr:\n{e.stderr}")
#         # Re-raise the exception so the Celery task knows that this step failed.
#         raise

#
# def assemble_video_with_broll_overlay(
#         original_video_path: str,
#         broll_insertions: list,
#         output_path: str,
#         output_resolution: str = "1080:1920"  # Use colon ':' as a separator
# ) -> str:
#     """
#     Assembles a video by overlaying B-roll clips onto the original video
#     at specified timestamps, keeping the original audio track intact.
#     This version has corrected FFmpeg filter syntax.
#     """
#     if not broll_insertions:
#         # ... (handle no b-roll case) ...
#         raise ValueError("No B-roll data to process.")
#
#     command = ['ffmpeg', '-y', '-i', original_video_path]
#     for insertion in broll_insertions:
#         command.extend(['-i', insertion['broll_path']])
#
#     filter_complex_parts = []
#
#     output_w, output_h = output_resolution.split(':')
#
#     # Scale the main video first.
#     filter_complex_parts.append(
#         f"[0:v]scale={output_w}:{output_h}:force_original_aspect_ratio=decrease,"
#         f"pad=width={output_w}:height={output_h}:x=-1:y=-1:color=black[base_video]"
#     )
#
#     last_video_stream = "[base_video]"
#
#     for i, moment in enumerate(broll_insertions):
#         broll_input_index = i + 1
#
#         try:
#             start_time, end_time = map(float, moment['timestamp'].split('-'))
#             duration = end_time - start_time
#         except (ValueError, AttributeError) as e:
#             print(f"Warning: Skipping moment with invalid timestamp format: {moment.get('timestamp')}. Error: {e}")
#             continue
#
#         # Part A: Prepare the B-roll clip with corrected pad syntax.
#         prepped_broll_stream = f"[broll{i}_prepped]"
#         filter_complex_parts.append(
#             f"[{broll_input_index}:v]"
#             # --- THE FIX IS HERE ---
#             # Correct syntax for pad filter: width=W:height=H:x=X:y=Y
#             f"scale={output_w}:{output_h}:force_original_aspect_ratio=decrease,"
#             f"pad=width={output_w}:height={output_h}:x=-1:y=-1:color=black,"
#             f"fps=30,trim=duration={duration},setpts=PTS-STARTPTS"
#             f"{prepped_broll_stream}"
#         )
#
#         # Part B: Overlay the prepared B-roll.
#         output_stream_name = f"[v{i + 1}]"
#         filter_complex_parts.append(
#             f"{last_video_stream}{prepped_broll_stream}"
#             f"overlay=enable='between(t,{start_time},{end_time})'"
#             f"{output_stream_name}"
#         )
#         last_video_stream = output_stream_name
#
#     filter_complex_string = ";".join(filter_complex_parts)
#
#     command.extend(['-filter_complex', filter_complex_string])
#
#     command.extend([
#         '-map', last_video_stream,
#         '-map', '0:a?',
#         '-c:v', 'libx264',
#         '-preset', 'ultrafast',
#         '-c:a', 'aac',
#         '-shortest',
#         output_path
#     ])
#
#     print("▶️ Assembling final video with FFmpeg overlay method...")
#
#     try:
#         result = subprocess.run(command, check=True, capture_output=True, text=True)
#         print(f"✅ Video assembly successful. Output saved to: {output_path}")
#         return output_path
#     except subprocess.CalledProcessError as e:
#         print(f"❌ FFmpeg assembly failed. Exit code: {e.returncode}")
#         print(f"FFmpeg command: {' '.join(command)}")
#         print(f"FFmpeg stderr:\n{e.stderr}")
#         raise


def assemble_video_with_broll_overlay(
        original_video_path: str,
        broll_insertions: list,
        output_path: str,
        output_resolution: str = "1080:1920"
) -> str:
    """
    Assembles a video by inserting B-roll clips at specified timestamps,
    keeping the original audio track intact. This version uses a robust
    split-and-concat filtergraph in FFmpeg to prevent frozen frames.
    """
    if not broll_insertions:
        # ... (handle no b-roll case) ...
        raise ValueError("No B-roll data to process.")

    command = ['ffmpeg', '-y', '-i', original_video_path]
    for insertion in broll_insertions:
        command.extend(['-i', insertion['broll_path']])

    filter_complex_parts = []
    concat_streams = []
    last_aroll_end_time = 0.0

    output_w, output_h = output_resolution.split(':')

    # Sort insertions by start time to process them in order
    broll_insertions.sort(key=lambda x: float(x['timestamp'].split('-')[0]))

    for i, moment in enumerate(broll_insertions):
        broll_input_index = i + 1

        try:
            start_time, end_time = map(float, moment['timestamp'].split('-'))
            duration = end_time - start_time
        except (ValueError, AttributeError):
            continue

        # 1. Take the segment of the original A-roll BEFORE this B-roll
        aroll_segment_stream = f"[aroll{i}]"
        filter_complex_parts.append(
            f"[0:v]trim=start={last_aroll_end_time}:end={start_time},"
            f"setpts=PTS-STARTPTS,"
            f"scale={output_w}:{output_h}:force_original_aspect_ratio=decrease,"
            f"pad=width={output_w}:height={output_h}:x=-1:y=-1:color=black"
            f"{aroll_segment_stream}"
        )
        concat_streams.append(aroll_segment_stream)

        # 2. Prepare the B-roll clip for this segment
        broll_segment_stream = f"[broll{i}_prepped]"
        filter_complex_parts.append(
            f"[{broll_input_index}:v]"
            f"scale={output_w}:{output_h}:force_original_aspect_ratio=decrease,"
            f"pad=width={output_w}:height={output_h}:x=-1:y=-1:color=black,"
            f"trim=duration={duration},setpts=PTS-STARTPTS"
            f"{broll_segment_stream}"
        )
        concat_streams.append(broll_segment_stream)

        last_aroll_end_time = end_time

    # 3. Add the final segment of the A-roll after the last B-roll
    final_aroll_stream = "[aroll_final]"
    filter_complex_parts.append(
        f"[0:v]trim=start={last_aroll_end_time},"
        f"setpts=PTS-STARTPTS,"
        f"scale={output_w}:{output_h}:force_original_aspect_ratio=decrease,"
        f"pad=width={output_w}:height={output_h}:x=-1:y=-1:color=black"
        f"{final_aroll_stream}"
    )
    concat_streams.append(final_aroll_stream)

    # 4. Concatenate all the prepared video streams together
    num_streams = len(concat_streams)
    concat_string = "".join(concat_streams)
    filter_complex_parts.append(f"{concat_string}concat=n={num_streams}:v=1:a=0[final_video]")

    filter_complex_string = ";".join(filter_complex_parts)

    command.extend(['-filter_complex', filter_complex_string])

    command.extend([
        '-map', "[final_video]",
        '-map', '0:a?',
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-c:a', 'aac',
        '-shortest',
        output_path
    ])

    print("▶️ Assembling final video with FFmpeg split/concat method...")

    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"✅ Video assembly successful. Output saved to: {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg assembly failed. Exit code: {e.returncode}")
        print(f"FFmpeg command: {' '.join(command)}")
        print(f"FFmpeg stderr:\n{e.stderr}")
        raise