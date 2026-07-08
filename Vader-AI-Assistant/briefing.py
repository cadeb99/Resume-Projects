"""
Morning briefing — main entry point.

This is what the OS scheduler (Task Scheduler / launchd) actually calls.
When it's time for the briefing to run, this launches the dashboard
server, auto-opens it in the browser, and runs the real briefing
pipeline — so you see the UI light up live as it gathers data and
speaks, rather than just hearing audio with nothing on screen.

If it's not yet time (or already ran today), it exits quietly without
opening anything — important since this gets triggered frequently
(every login, every 15 min) by the OS trigger.

Run with: python briefing.py
Run with: python briefing.py --force   (bypass the time/already-ran gate, AND force-open the dashboard, for testing)
"""

import sys
import config
import scheduler
import dashboard_server
import memory


def run_briefing(force: bool = False):
    if not force and not scheduler.should_run_now():
        # Quiet exit — this is expected most times the scheduler fires
        # (every login, every 15 min) since it only actually runs once,
        # at the first trigger inside the BRIEFING_WINDOW each day.
        return

    print(f"=== {config.ASSISTANT_NAME} morning briefing for {config.USER_NAME} ===")
    print(f"(DEMO_MODE = {config.DEMO_MODE})\n")

    memory.init_db()

    # Launch the dashboard server (opens browser) and run the real
    # pipeline through it, so the UI reflects what's actually happening.
    dashboard_server.start_and_run_briefing()


if __name__ == "__main__":
    force_flag = "--force" in sys.argv
    run_briefing(force=force_flag)
