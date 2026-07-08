"""
Local dashboard server for Vader.

Serves the dashboard UI and exposes an endpoint that triggers the real
briefing pipeline (briefing.py). Auto-opens the browser on launch.

Run with: python dashboard_server.py
"""

import threading
import queue
import webbrowser
import io
import contextlib
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import os

import config
from integrations import calendar_api, tasks_api, gmail_api, weather_api
import summarizer
import speak
import scheduler
import memory

DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "dashboard")
PORT = 8420

# Holds the most recent briefing result so the frontend can poll/fetch it
latest_state = {
    "status": "idle",
    "briefing_text": None,
    "log": [],
}


def run_real_briefing():
    """Runs the actual pipeline (same as briefing.py) and updates latest_state.
    Speaks the greeting instantly (no API wait) WHILE data pulls and the
    Claude call happen in parallel on a background thread — so the real
    pipeline isn't delayed by waiting for the greeting audio to finish."""
    latest_state["status"] = "working"
    latest_state["log"].append("Briefing run started")

    greeting = summarizer.build_instant_greeting()
    latest_state["briefing_text"] = greeting

    # Pick today's song (no-repeat logic handled by scheduler) and
    # start it playing now, right as the briefing begins.
    todays_song = scheduler.pick_todays_song()
    speak.start_background_music(
        song_path=todays_song["path"],
        volume=todays_song["volume"],
    )

    # Kick off the real data pull in the background so it runs WHILE
    # the greeting is being spoken, not after.
    data_holder = {}

    def gather_and_generate():
        data_holder["weather"] = weather_api.get_todays_weather()
        latest_state["log"].append("Weather pulled")

        data_holder["events"] = calendar_api.get_todays_events()
        latest_state["log"].append("Calendar pulled")

        data_holder["tasks"] = tasks_api.get_open_tasks()
        latest_state["log"].append("Tasks pulled")

        data_holder["emails"] = gmail_api.get_important_emails()
        latest_state["log"].append("Email pulled")

    gather_thread = threading.Thread(target=gather_and_generate, daemon=True)
    gather_thread.start()

    # Speak the greeting now — this plays WHILE gather_and_generate runs above.
    latest_state["status"] = "speaking"
    speak.speak(greeting)
    latest_state["log"].append("Greeting spoken")

    # By now the background data-pull has likely finished (or nearly has);
    # wait for it if it hasn't, so we have weather/events/tasks/emails
    # ready before we start streaming the Claude response.
    latest_state["status"] = "working"
    gather_thread.join()

    weather, events, tasks, emails = data_holder["weather"], data_holder["events"], \
        data_holder["tasks"], data_holder["emails"]

    # Start the Claude stream + sentence queue in the background RIGHT NOW,
    # before speaking the filler — so generation is already underway while
    # the filler phrase plays, instead of starting only after it finishes.
    latest_state["status"] = "speaking"
    full_text_parts = []
    sentence_queue = queue.Queue()
    STREAM_DONE = object()

    def stream_producer():
        try:
            for sentence in summarizer.stream_briefing_sentences(weather, events, tasks, emails):
                full_text_parts.append(sentence)
                latest_state["briefing_text"] = f"{greeting} " + " ".join(full_text_parts)
                sentence_queue.put(sentence)
        finally:
            sentence_queue.put(STREAM_DONE)

    stream_thread = threading.Thread(target=stream_producer, daemon=True)
    stream_thread.start()

    # Speak the short filler now — this plays WHILE stream_producer above
    # is already working on getting the first real sentence + its audio
    # ready, closing most of the gap that used to be dead silence.
    filler = summarizer.build_filler_phrase()
    speak.speak(filler)
    latest_state["log"].append("Filler spoken")

    def queued_sentences():
        """Pulls sentences off the queue as stream_producer fills it,
        blocking only if generation is genuinely behind playback."""
        while True:
            item = sentence_queue.get()
            if item is STREAM_DONE:
                break
            yield item

    speak.speak_stream(queued_sentences())
    latest_state["log"].append("Briefing script generated and spoken")

    speak.stop_background_music(fade_seconds=3, extend_seconds=3)

    scheduler.mark_ran_today()
    latest_state["status"] = "idle"
    latest_state["log"].append("Briefing complete")

    # Daily memory maintenance piggybacks on this once-a-day run rather than
    # its own scheduled job. Backgrounded so a slow/failed consolidation can
    # never delay or break the briefing itself.
    threading.Thread(target=memory.consolidate, daemon=True).start()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)

    def do_GET(self):
        if self.path == "/api/state":
            self._send_json(latest_state)
            return
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/run":
            threading.Thread(target=run_real_briefing, daemon=True).start()
            self._send_json({"started": True})
            return
        self.send_error(404)

    def _send_json(self, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # quiet the default request logging


def main():
    """Standalone launch — opens the dashboard, waits for manual trigger."""
    server = HTTPServer(("localhost", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"{config.ASSISTANT_NAME} dashboard running at {url}")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    server.serve_forever()


def start_and_run_briefing():
    """
    Scheduled-run mode — starts the server, opens the dashboard, and
    immediately kicks off the real briefing pipeline so the UI shows
    it happening live (rather than requiring a manual button click).

    Used by briefing.py when the OS scheduler triggers it.
    """
    server = HTTPServer(("localhost", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"{config.ASSISTANT_NAME} dashboard running at {url}")

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # Give the server a moment to be ready, then open browser + start briefing
    def launch():
        try:
            webbrowser.open(url)
            run_real_briefing()
        except Exception as e:
            import traceback
            print(f"[briefing] Error in briefing thread: {e}")
            traceback.print_exc()

    briefing_thread = threading.Thread(target=launch, daemon=True)
    briefing_thread.start()

    # Wait for the briefing to fully complete (up to 3 minutes)
    briefing_thread.join(timeout=180)
    server_thread.join(timeout=5)


if __name__ == "__main__":
    main()
