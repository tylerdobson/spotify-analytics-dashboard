"""Capture public-safe media for the Spotify Analytics dashboard.

The script runs Streamlit in demo mode, captures screenshots and a short WebM
walkthrough, and writes a media manifest. It does not require Spotify
credentials and does not use private listening history.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MEDIA_DIR = PROJECT_ROOT / "assets" / "demo"
PORT = 8510
BASE_URL = f"http://127.0.0.1:{PORT}"
VIEWPORT = {"width": 1600, "height": 900}
VIDEO_SIZE = {"width": 1600, "height": 900}

PAGES = [
    ("hero.png", "Home", "Spotify Analytics"),
    ("dashboard.png", "Home", "At a glance"),
    ("top-content.png", "Top Content", "Top tracks"),
    ("history.png", "Listening History", "Saved plays"),
    ("features.png", "Audio Features", "Average feature profile"),
    ("workflow.png", "Playlists", "Playlist Manager"),
]


def main() -> int:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_playwright()
    process = _start_streamlit()
    try:
        _wait_for_app()
        media = _capture_media()
        _write_manifest(media)
    finally:
        _stop_process(process)
    print(f"Media capture complete: {MEDIA_DIR}")
    return 0


def _ensure_playwright() -> None:
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        raise SystemExit(
            "Playwright is not installed. Run:\n"
            "python -m pip install -r requirements-dev.txt\n"
            "python -m playwright install chromium"
        )


def _start_streamlit() -> subprocess.Popen:
    env = os.environ.copy()
    env["SPOTIFY_DEMO_MODE"] = "true"
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(PROJECT_ROOT / "app.py"),
        "--server.port",
        str(PORT),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
        "--global.developmentMode",
        "false",
    ]
    return subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_for_app(timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        try:
            with urlopen(BASE_URL, timeout=2) as response:
                if response.status == 200:
                    return
        except URLError as exc:
            last_error = str(exc)
        time.sleep(1)
    raise SystemExit(
        f"Streamlit did not respond at {BASE_URL} within {timeout_seconds} seconds. "
        f"Last error: {last_error}"
    )


def _capture_media() -> list[dict[str, str | int]]:
    from playwright.sync_api import Error, sync_playwright

    captured: list[dict[str, str | int]] = []
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Error as exc:
            raise SystemExit(
                "Chromium is not installed for Playwright. Run:\n"
                "python -m playwright install chromium\n"
                f"Original error: {exc}"
            )

        context = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=2,
            record_video_dir=str(MEDIA_DIR),
            record_video_size=VIDEO_SIZE,
        )
        page = context.new_page()
        video = page.video

        _open_page(page, "Home", "Spotify Analytics")
        _click_if_present(page, "Sync last 50 plays to database")

        for filename, label, expected_text in PAGES:
            _open_page(page, label, expected_text)
            path = MEDIA_DIR / filename
            page.screenshot(path=str(path), full_page=False)
            _assert_non_empty(path)
            captured.append({"file": filename, "bytes": path.stat().st_size})

        for _, label, expected_text in PAGES:
            _open_page(page, label, expected_text)
            page.wait_for_timeout(1600)

        context.close()
        browser.close()

        webm_path = MEDIA_DIR / "demo.webm"
        if video:
            recorded_path = Path(video.path())
            if webm_path.exists():
                webm_path.unlink()
            shutil.move(str(recorded_path), webm_path)
            _assert_non_empty(webm_path)
            captured.append({"file": "demo.webm", "bytes": webm_path.stat().st_size})

        poster = MEDIA_DIR / "demo-poster.png"
        shutil.copyfile(MEDIA_DIR / "hero.png", poster)
        captured.append({"file": "demo-poster.png", "bytes": poster.stat().st_size})

        _convert_to_mp4_if_available(webm_path, captured)
        _convert_to_gif_if_available(webm_path, captured)

    return captured


def _open_page(page, label: str, expected_text: str) -> None:
    page.goto(BASE_URL, wait_until="domcontentloaded")
    if label != "Home":
        page.get_by_text(label, exact=True).click()
    page.get_by_text(expected_text).first.wait_for(timeout=45_000)
    page.wait_for_timeout(1200)


def _click_if_present(page, label: str) -> None:
    try:
        page.get_by_role("button", name=label).click(timeout=2_000)
        page.wait_for_timeout(900)
    except Exception:
        return


def _assert_non_empty(path: Path) -> None:
    if not path.exists() or path.stat().st_size < 10_000:
        raise SystemExit(f"Expected media file was missing or too small: {path}")


def _convert_to_mp4_if_available(webm_path: Path, captured: list[dict[str, str | int]]) -> None:
    _run_ffmpeg(webm_path, MEDIA_DIR / "demo.mp4", captured, ["-movflags", "+faststart", "-pix_fmt", "yuv420p"])


def _convert_to_gif_if_available(webm_path: Path, captured: list[dict[str, str | int]]) -> None:
    _run_ffmpeg(
        webm_path,
        MEDIA_DIR / "demo.gif",
        captured,
        ["-vf", "fps=8,scale=960:-1:flags=lanczos", "-loop", "0"],
    )


def _run_ffmpeg(
    source: Path,
    target: Path,
    captured: list[dict[str, str | int]],
    args: list[str],
) -> None:
    if not source.exists():
        return
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return
    command = [ffmpeg, "-y", "-i", str(source), *args, str(target)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg conversion failed for {target.name}; keeping WebM only.")
        print(result.stderr)
        return
    _assert_non_empty(target)
    captured.append({"file": target.name, "bytes": target.stat().st_size})


def _write_manifest(media: list[dict[str, str | int]]) -> None:
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "app_url": BASE_URL,
        "viewport": VIEWPORT,
        "device_scale_factor": 2,
        "mode": "SPOTIFY_DEMO_MODE=true",
        "media": media,
        "notes": "Demo mode uses deterministic sample data. No Spotify credentials, OAuth tokens, or private listening exports are included.",
    }
    (MEDIA_DIR / "media_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
