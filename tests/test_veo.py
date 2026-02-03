#!/usr/bin/env python3
"""
Veo Video Generation Test Script

This script demonstrates video generation using Google's Veo API.
It sends a request to generate a video, polls for completion, and downloads the result.

Usage:
    export GEMINI_API_KEY="your-api-key"
    python test_veo.py
"""

from __future__ import annotations

import os
import sys
import time

import requests

# Gemini API Base URL
BASE_URL = "http://localhost:8084/v1beta"

# Default polling interval in seconds
POLL_INTERVAL = 10

os.environ["GEMINI_API_KEY"] = "sk-PCr5oXZNKb9HcyzYqTIMvr8zXsIBK3WS"


def generate_video(api_key: str, prompt: str, model: str = "veo-3.1-fast-generate-preview") -> str:
    """
    Send a request to generate a video and return the operation name.

    Args:
        api_key: Gemini API key
        prompt: Text prompt for video generation
        model: Model name to use (default: veo-3.1-generate-preview)

    Returns:
        Operation name for polling status
    """
    url = f"{BASE_URL}/models/{model}:predictLongRunning"
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "instances": [
            {
                "prompt": prompt,
            }
        ]
    }

    print(f"Sending video generation request to {model}...")
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()

    data = response.json()
    operation_name = data.get("name")

    if not operation_name:
        raise ValueError(f"No operation name in response: {data}")

    print(f"Operation started: {operation_name}")
    return operation_name


def poll_operation(api_key: str, operation_name: str, poll_interval: int = POLL_INTERVAL) -> dict:
    """
    Poll the operation status until the video is ready.

    Args:
        api_key: Gemini API key
        operation_name: Operation name from generate_video
        poll_interval: Seconds between polls (default: 10)

    Returns:
        Final response dict containing the video URI
    """
    url = f"{BASE_URL}/{operation_name}"
    headers = {
        "x-goog-api-key": api_key,
    }

    print(f"Polling operation status (every {poll_interval}s)...")

    while True:
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()

        data = response.json()
        is_done = data.get("done", False)

        if is_done:
            print("Operation completed!")

            # Check for errors
            if "error" in data:
                error = data["error"]
                raise RuntimeError(f"Operation failed: {error.get('message', error)}")

            return data

        # Show progress if available
        metadata = data.get("metadata", {})
        if metadata:
            progress = metadata.get("progress", "unknown")
            print(f"  Progress: {progress}%")

        time.sleep(poll_interval)


def download_video(api_key: str, video_uri: str, output_path: str = "dialogue_example.mp4") -> str:
    """
    Download the generated video.

    Args:
        api_key: Gemini API key
        video_uri: URI of the generated video
        output_path: Path to save the video (default: dialogue_example.mp4)

    Returns:
        Path to the downloaded video
    """
    headers = {
        "x-goog-api-key": api_key,
    }

    print(f"Downloading video from: {video_uri}")
    response = requests.get(video_uri, headers=headers, allow_redirects=True, timeout=300, stream=True)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    file_size = os.path.getsize(output_path)
    print(f"Video saved to: {output_path} ({file_size / 1024 / 1024:.2f} MB)")
    return output_path


def extract_video_uri(response: dict) -> str:
    """
    Extract the video URI from the operation response.

    Args:
        response: Final operation response dict

    Returns:
        Video download URI
    """
    try:
        video_response = response["response"]["generateVideoResponse"]
        samples = video_response["generatedSamples"]
        video_uri = samples[0]["video"]["uri"]
        return video_uri
    except (KeyError, IndexError) as e:
        raise ValueError(f"Could not extract video URI from response: {response}") from e


def main() -> None:
    """Main entry point."""
    # Get API key from environment
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set", file=sys.stderr)
        print("Usage: export GEMINI_API_KEY='your-api-key' && python test_veo.py", file=sys.stderr)
        sys.exit(1)

    # Default prompt (same as the bash script)
    prompt = (
        "A close up of two people staring at a cryptic drawing on a wall, "
        "torchlight flickering. A man murmurs, \"This must be it. That's the secret code.\" "
        "The woman looks at him and whispering excitedly, \"What did you find?\""
    )

    # Allow custom prompt via command line argument
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        print(f"Using custom prompt: {prompt}")

    try:
        # Step 1: Start video generation
        operation_name = generate_video(api_key, prompt)

        # Step 2: Poll until complete
        final_response = poll_operation(api_key, operation_name)

        # Step 3: Extract video URI and download
        video_uri = extract_video_uri(final_response)
        download_video(api_key, video_uri)

        print("\nVideo generation complete!")

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}", file=sys.stderr)
        if e.response is not None:
            print(f"Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
