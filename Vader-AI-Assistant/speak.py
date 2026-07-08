"""
The one OS-aware module in the whole system.
Handles converting briefing text to speech and playing it back,
with platform-specific fallbacks for Mac vs Windows.
"""

import platform
import subprocess
import tempfile
import os
import time
import threading
import queue
import config


_music_process = None  # tracks the currently playing background music process
_music_start_time = None  # wall-clock time when music playback began
_music_active_path = None  # path of the song actually playing (for the fade-out clip)
_music_active_volume = None  # volume the song actually started at


def start_background_music(song_path: str = None, volume: float = None):
    """
    Starts playing a song softly in the background as a separate,
    non-blocking process. Uses song_path if provided, otherwise falls
    back to config.BACKGROUND_MUSIC_PATH. Volume uses the per-song
    override if provided, otherwise falls back to
    config.BACKGROUND_MUSIC_VOLUME. No-op if no path is set or the
    file doesn't exist.
    """
    global _music_process, _music_start_time, _music_active_path, _music_active_volume

    path = song_path or getattr(config, "BACKGROUND_MUSIC_PATH", "")
    if not path or not os.path.exists(path):
        return

    vol = volume if volume is not None else config.BACKGROUND_MUSIC_VOLUME

    system = platform.system()
    if system == "Darwin":
        # afplay's -v flag sets volume from 0.0 (silent) to 1.0 (full)
        _music_process = subprocess.Popen(
            ["afplay", "-v", str(vol), path]
        )
        _music_start_time = time.time()
        _music_active_path = path
        _music_active_volume = vol
    elif system == "Windows":
        ps_command = (
            "Add-Type -AssemblyName presentationCore; "
            "$global:jarvisMusicPlayer = New-Object system.windows.media.mediaplayer; "
            f"$jarvisMusicPlayer.open([uri]'{path}'); "
            f"$jarvisMusicPlayer.Volume = {vol}; "
            "$jarvisMusicPlayer.Play(); "
            "Start-Sleep -Seconds 300"  # keep the process alive while music plays
        )
        _music_process = subprocess.Popen(["powershell", "-Command", ps_command])
        _music_start_time = time.time()
    else:
        print(f"[speak] No background music playback handler for {system}.")


def stop_background_music(fade_seconds: float = 0, extend_seconds: float = 0):
    """
    Stops background music. If fade_seconds > 0 (and ffmpeg is
    available, Mac only for now), instead of cutting the music off
    abruptly, this:
      1. Lets the music continue playing for `extend_seconds` more
         (e.g. 3 seconds past when speech ends)
      2. Extracts a short clip from wherever the song currently is,
         with a smooth fade-out applied via ffmpeg
      3. Plays that fade-out clip to close things out gracefully

    Falls back to an immediate cut if ffmpeg isn't available or
    anything about the fade fails — never lets a fade error break the
    briefing.
    """
    global _music_process, _music_start_time, _music_active_path, _music_active_volume

    if _music_process is None:
        return

    if fade_seconds <= 0 or platform.system() != "Darwin" or not _music_active_path:
        _music_process.terminate()
        _music_process = None
        return

    try:
        elapsed = time.time() - _music_start_time if _music_start_time else 0

        # Let the music play on for the extend window before we cut to the fade
        if extend_seconds > 0:
            time.sleep(extend_seconds)
            elapsed += extend_seconds

        # Where to start the fade-out clip from in the source file
        fade_start = max(elapsed, 0)

        fade_clip_path = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name

        vol = _music_active_volume if _music_active_volume is not None else config.BACKGROUND_MUSIC_VOLUME

        FFMPEG = "/opt/homebrew/Cellar/ffmpeg/8.1.2/bin/ffmpeg"
        ffmpeg_result = subprocess.run(
            [
                FFMPEG, "-y",
                "-ss", str(fade_start),
                "-i", _music_active_path,
                "-t", str(fade_seconds),
                "-af", f"afade=t=out:st=0:d={fade_seconds},volume={vol}",
                fade_clip_path,
            ],
            capture_output=True,
            timeout=10,
        )

        # Stop the raw looping playback now that we have the fade clip ready
        _music_process.terminate()
        _music_process = None

        if ffmpeg_result.returncode == 0 and os.path.exists(fade_clip_path):
            subprocess.run(["afplay", fade_clip_path])
            os.remove(fade_clip_path)
        # If ffmpeg failed for any reason, we've already stopped the music
        # above — no fade, but no crash either.

    except Exception as e:
        print(f"[speak] Fade-out failed, stopping music immediately instead: {e}")
        if _music_process is not None:
            _music_process.terminate()
            _music_process = None
    finally:
        _music_active_path = None
        _music_active_volume = None


def speak(text: str):
    """Converts text to speech and plays it. Routes to ElevenLabs if
    configured, otherwise falls back to free OS-native TTS."""
    if config.DEMO_MODE or not config.ELEVENLABS_API_KEY:
        print("\n[DEMO MODE — no ElevenLabs key set, using OS-native fallback voice]\n")
        _speak_native(text)
        return

    audio_path = _generate_elevenlabs_audio(text)
    _play_audio_file(audio_path)
    os.remove(audio_path)


def speak_stream(sentence_generator):
    """
    Consumes a generator that yields sentences one at a time (e.g. from
    summarizer.stream_briefing_sentences) and speaks them as they
    arrive, overlapping audio GENERATION for the next sentence with
    PLAYBACK of the current one — so total wall-clock time is closer to
    max(generation, playback) rather than generation + playback summed
    for every sentence.

    Falls back to native OS speech for each sentence if ElevenLabs
    isn't configured (no overlap benefit in that case, but still works).
    """
    if config.DEMO_MODE or not config.ELEVENLABS_API_KEY:
        for sentence in sentence_generator:
            print("\n[DEMO MODE — no ElevenLabs key set, using OS-native fallback voice]\n")
            _speak_native(sentence)
        return

    audio_queue = queue.Queue()
    SENTINEL = object()  # signals "no more audio coming"

    def producer():
        """Runs in a background thread: generates audio for each
        sentence as it streams in from Claude, pushes file paths onto
        the queue as soon as each is ready."""
        try:
            for sentence in sentence_generator:
                audio_path = _generate_elevenlabs_audio(sentence)
                audio_queue.put(audio_path)
        finally:
            audio_queue.put(SENTINEL)

    producer_thread = threading.Thread(target=producer, daemon=True)
    producer_thread.start()

    # Consumer: play each audio file in order as it becomes available.
    # If generation is still working on the next sentence while this
    # one plays, that's the overlap — this loop just blocks on the
    # queue until the next one's ready.
    while True:
        item = audio_queue.get()
        if item is SENTINEL:
            break
        _play_audio_file(item)
        os.remove(item)

    producer_thread.join()


def _generate_elevenlabs_audio(text: str) -> str:
    """Calls ElevenLabs and returns a path to a temp mp3 file. Caller
    is responsible for deleting the file after playback."""
    import requests

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",  # low-latency model, ~3x faster than multilingual_v2; speed setting confirmed to still work
        "voice_settings": {
            "stability": config.VOICE_STABILITY,
            "similarity_boost": config.VOICE_SIMILARITY_BOOST,
            "speed": config.VOICE_SPEED,
        },
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(resp.content)
        return f.name


def _speak_native(text: str):
    """Free fallback using each OS's built-in TTS. Robotic, but $0 and
    requires zero setup — useful for testing the pipeline."""
    system = platform.system()

    if system == "Darwin":  # macOS
        subprocess.run(["say", text])
    elif system == "Windows":
        # Uses PowerShell's System.Speech for zero-dependency TTS
        ps_command = (
            "Add-Type -AssemblyName System.Speech; "
            "$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$speak.Speak('{text}')"
        )
        subprocess.run(["powershell", "-Command", ps_command])
    else:
        print(f"[speak] No native TTS handler for {system}. Printing instead:\n{text}")


def _play_audio_file(path: str):
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["afplay", path])
    elif system == "Windows":
        ps_command = (
            "Add-Type -AssemblyName presentationCore; "
            "$player = New-Object system.windows.media.mediaplayer; "
            f"$player.open([uri]'{path}'); $player.Play(); "
            "Start-Sleep -Seconds 30"
        )
        subprocess.run(["powershell", "-Command", ps_command])
    else:
        print(f"[speak] No audio playback handler for {system}.")
