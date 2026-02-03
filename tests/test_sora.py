#!/usr/bin/env python3
"""
Sora Video Generation Test Script

This script demonstrates video generation using OpenAI's Sora API.
It sends a request to generate a video, polls for completion, and downloads the result.

Usage:
    export OPENAI_API_KEY="your-api-key"
    python test_sora.py
"""

from __future__ import annotations

import os
import sys
import time

import requests

# OpenAI API Base URL
BASE_URL = "http://localhost:8084/v1"

# Default polling interval in seconds
POLL_INTERVAL = 10

os.environ["OPENAI_API_KEY"] = "sk-PCr5oXZNKb9HcyzYqTIMvr8zXsIBK3WS"


def generate_video(
    api_key: str,
    prompt: str,
    model: str = "sora-2",
    size: str = "1920x1080",
    duration: int = 10,
    n: int = 1,
) -> str:
    """
    Send a request to generate a video and return the video job ID.

    Args:
        api_key: OpenAI API key
        prompt: Text prompt for video generation
        model: Model name to use (default: sora-2)
        size: Video resolution (default: 1920x1080)
        duration: Video duration in seconds (default: 10)
        n: Number of videos to generate (default: 1)

    Returns:
        Video job ID for polling status
    """
    url = f"{BASE_URL}/videos"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "duration": str(duration),
        "n": n,
    }

    print(f"Sending video generation request to {model}...")
    print(f"  Size: {size}, Duration: {duration}s")
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()

    data = response.json()
    video_id = data.get("id")

    if not video_id:
        raise ValueError(f"No video ID in response: {data}")

    print(f"Video job started: {video_id}")
    print(f"  Status: {data.get('status')}")
    return video_id


def poll_video(api_key: str, video_id: str, poll_interval: int = POLL_INTERVAL) -> dict:
    """
    Poll the video job status until the video is ready.

    Args:
        api_key: OpenAI API key
        video_id: Video job ID from generate_video
        poll_interval: Seconds between polls (default: 10)

    Returns:
        Final response dict containing the video metadata
    """
    url = f"{BASE_URL}/videos/{video_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    print(f"Polling video job status (every {poll_interval}s)...")

    while True:
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()

        data = response.json()
        status = data.get("status", "unknown")
        progress = data.get("progress", 0)

        print(f"  Status: {status}, Progress: {progress}%")

        if status == "completed":
            print("Video generation completed!")
            print(f"  Duration: {data.get('seconds')}s")
            print(f"  Size: {data.get('size')}")
            print(f"  Expires at: {data.get('expires_at')}")
            return data

        if status == "failed":
            error = data.get("error", {})
            raise RuntimeError(f"Video generation failed: {error.get('message', error)}")

        if status == "cancelled":
            raise RuntimeError("Video generation was cancelled")

        time.sleep(poll_interval)


def download_video(api_key: str, video_id: str, output_path: str = "sora_output.mp4", variant: str | None = None) -> str:
    """
    Download the generated video content.

    Args:
        api_key: OpenAI API key
        video_id: Video job ID
        output_path: Path to save the video (default: sora_output.mp4)
        variant: Optional variant to download (defaults to MP4 video)

    Returns:
        Path to the downloaded video
    """
    url = f"{BASE_URL}/videos/{video_id}/content"
    if variant:
        url = f"{url}?variant={variant}"

    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    print(f"Downloading video content...")
    response = requests.get(url, headers=headers, allow_redirects=True, timeout=300, stream=True)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    file_size = os.path.getsize(output_path)
    print(f"Video saved to: {output_path} ({file_size / 1024 / 1024:.2f} MB)")
    return output_path


def main() -> None:
    """Main entry point."""
    # Get API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set", file=sys.stderr)
        print("Usage: export OPENAI_API_KEY='your-api-key' && python test_sora.py", file=sys.stderr)
        sys.exit(1)

    # Default prompt
    prompt = "A calico cat playing a piano on stage"

    # Allow custom prompt via command line argument
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        print(f"Using custom prompt: {prompt}")

    try:
        # Step 1: Start video generation
        video_id = generate_video(api_key, prompt)

        # Step 2: Poll until complete
        final_response = poll_video(api_key, video_id)

        # Step 3: Download video content
        download_video(api_key, video_id)

        print("\nVideo generation complete!")
        print(f"Video ID: {video_id}")
        print(f"Model: {final_response.get('model')}")

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
