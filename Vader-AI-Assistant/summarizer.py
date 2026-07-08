"""
Takes raw data from all integrations and asks Claude to turn it into a
natural, spoken-style morning briefing script.
"""

from datetime import datetime
import config


def build_instant_greeting():
    """
    Returns the opening line instantly — no API call, no wait.
    Meant to be spoken immediately while the rest of the briefing is
    still being generated in the background, so there's zero perceived
    delay before Vader starts talking.

    Includes a time-aware quip when the briefing runs at an unusual hour
    (very early or very late), for personality.
    """
    import random

    now = datetime.now()
    time_str = _current_time_spoken()
    hour = now.hour

    hour = now.hour
    greeting_word = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
    base = f"{greeting_word}, {config.USER_NAME}. It's currently {time_str}."

    # Time-of-day flavor — only kicks in outside normal "ran right at 8am" hours.
    if 0 <= hour < 5:
        quips = [
            f" You're either up late or up early, sir — not sure which one to congratulate you on.",
            f" That's an unusual hour to be awake. Burning the midnight oil, or starting obscenely early?",
            f" Either an early start or a late night. I won't pry.",
        ]
        base += random.choice(quips)
    elif 5 <= hour < 7:
        quips = [
            f" An early start today.",
            f" Up before the sun, I see.",
            "",
        ]
        base += random.choice(quips)
    elif 11 <= hour < 17:
        quips = [
            f" A bit later than your usual briefing time, but better late than never.",
            f" Running behind schedule today, are we?",
            "",
        ]
        base += random.choice(quips)

    return base


def build_filler_phrase():
    """
    Returns a short, varied transitional phrase — instant, no API call.
    Spoken right after the greeting and before the real briefing starts,
    buying a second or two of extra time for Claude + ElevenLabs to get
    the first real sentence ready, so there's no dead silence while
    that's happening.
    """
    import random

    fillers = [
        "Let's see what we've got.",
        "Pulling up your day now.",
        "One moment, sir.",
        "Here's where things stand.",
        "Let me walk you through it.",
    ]
    return random.choice(fillers)


def stream_briefing_sentences(weather, events, tasks, emails):
    """
    Streams the briefing from Claude and yields complete sentences as
    soon as each one is ready — rather than waiting for the full
    response. Used to start speaking earlier instead of waiting ~3s
    for the entire briefing to generate first.

    In DEMO_MODE, just yields the demo text as a single "sentence"
    since there's no real streaming API call to speed up.
    """
    if config.DEMO_MODE:
        yield _demo_briefing_text(weather, events, tasks, emails)
        return

    import anthropic
    import re

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    raw_data = f"""
Weather: {weather.get('condition', 'unknown conditions')}, high {weather['high']}°F, low {weather['low']}°F, {weather['precip_chance']}% chance of precipitation, wind {weather.get('wind_speed_mph', 'unknown')} mph from the {weather.get('wind_direction', 'unknown direction')}{f", gusting up to {weather['wind_gust_mph']} mph" if weather.get('wind_gust_mph') else ""}.
Detailed forecast notes: {weather.get('detailed_forecast', 'none available')}

Calendar events today:
{_format_events(events)}

Open tasks:
{_format_tasks(tasks)}

Important unread emails:
{_format_emails(emails)}
"""

    seasonal_activity = _seasonal_activity()

    prompt = f"""You are {config.ASSISTANT_NAME}, an AI assistant with a personality in the vein \
of Tony Stark's JARVIS — dry wit, understated confidence, genuinely helpful, never robotic or stiff. You're \
speaking a morning briefing aloud to {config.USER_NAME}. The greeting (time-appropriate greeting and the \
current time) has ALREADY been spoken separately — do NOT repeat it or restate the time. Start \
directly with the rest of the briefing content.

Write the way {config.ASSISTANT_NAME} actually talks: warm but composed, occasionally dryly funny, never reading \
like a list. Vary your phrasing and structure every time — don't fall into the same template \
sentence-for-sentence each day (avoid always saying "you've got X things on the calendar" or \
"you have X open tasks" verbatim; mix up how you introduce each section). React naturally to \
what's actually in the data — if the schedule is packed, note it; if it's light, mention that \
too; if there's nothing important in email, say so briefly instead of a flat "no important \
emails." Treat this like a sharp assistant who knows {config.USER_NAME} well, not a script \
reading off a database.

End the briefing with exactly this sign-off line, word for word: \
"Grab a Red Bull, go {seasonal_activity}, and have a good day, sir." \
Keep it to about 20-30 seconds of spoken audio (roughly 55-85 words) excluding the sign-off. \
Give weather a proper, fuller treatment — don't reduce it to one quick line. Using the detailed \
forecast notes, cover: the actual conditions and how they'll feel (not just a number), wind \
including gusts if mentioned, any notable shift through the day (temperature dropping, clearing \
up, smoke moving in, etc.), and precipitation chance if it's meaningful. Don't read the notes \
verbatim — translate the genuinely useful parts into natural spoken language, as if describing \
what {config.USER_NAME} will actually experience stepping outside today. After weather, cover \
the day's schedule, top priorities, and any important emails worth knowing about. Don't use \
markdown formatting, bullet points, or headers — this is going to be converted directly to speech.

Raw data:
{raw_data}
"""

    buffer = ""
    sentence_end_pattern = re.compile(r'(?<=[.!?])\s+')

    with client.messages.stream(
        model=config.CLAUDE_MODEL,
        max_tokens=320,
        temperature=1.0,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text_chunk in stream.text_stream:
            buffer += text_chunk
            # Split off any complete sentences from the buffer, keep the
            # trailing incomplete fragment for the next chunk.
            parts = sentence_end_pattern.split(buffer)
            if len(parts) > 1:
                # All but the last part are complete sentences ready to speak
                for sentence in parts[:-1]:
                    if sentence.strip():
                        yield sentence.strip()
                buffer = parts[-1]

    # Whatever's left in the buffer after streaming ends is the final sentence
    if buffer.strip():
        yield buffer.strip()


def build_briefing_text(weather, events, tasks, emails):
    """
    Returns the REST of the briefing (after the instant greeting) as a
    plain-text script meant to be spoken aloud. In DEMO_MODE, builds a
    simple template instead of calling the API, so the scaffold runs
    with zero API keys.
    """
    if config.DEMO_MODE:
        return _demo_briefing_text(weather, events, tasks, emails)

    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    raw_data = f"""
Weather: {weather.get('condition', 'unknown conditions')}, high {weather['high']}°F, low {weather['low']}°F, {weather['precip_chance']}% chance of precipitation, wind {weather.get('wind_speed_mph', 'unknown')} mph from the {weather.get('wind_direction', 'unknown direction')}{f", gusting up to {weather['wind_gust_mph']} mph" if weather.get('wind_gust_mph') else ""}.
Detailed forecast notes: {weather.get('detailed_forecast', 'none available')}

Calendar events today:
{_format_events(events)}

Open tasks:
{_format_tasks(tasks)}

Important unread emails:
{_format_emails(emails)}
"""

    seasonal_activity = _seasonal_activity()

    prompt = f"""You are {config.ASSISTANT_NAME}, an AI assistant with a personality in the vein \
of Tony Stark's JARVIS — dry wit, understated confidence, genuinely helpful, never robotic or stiff. You're \
speaking a morning briefing aloud to {config.USER_NAME}. The greeting (time-appropriate greeting and the \
current time) has ALREADY been spoken separately — do NOT repeat it or restate the time. Start \
directly with the rest of the briefing content.

Write the way {config.ASSISTANT_NAME} actually talks: warm but composed, occasionally dryly funny, never reading \
like a list. Vary your phrasing and structure every time — don't fall into the same template \
sentence-for-sentence each day (avoid always saying "you've got X things on the calendar" or \
"you have X open tasks" verbatim; mix up how you introduce each section). React naturally to \
what's actually in the data — if the schedule is packed, note it; if it's light, mention that \
too; if there's nothing important in email, say so briefly instead of a flat "no important \
emails." Treat this like a sharp assistant who knows {config.USER_NAME} well, not a script \
reading off a database.

End the briefing with exactly this sign-off line, word for word: \
"Grab a Red Bull, go {seasonal_activity}, and have a good day, sir." \
Keep it to about 25-35 seconds of spoken audio (roughly 70-110 words) excluding the sign-off. \
Mention weather, the day's schedule, top priorities, and any important emails worth knowing \
about. Don't use markdown formatting, bullet points, or headers — this is going to be converted \
directly to speech.

Raw data:
{raw_data}
"""

    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=350,
        temperature=1.0,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def _demo_briefing_text(weather, events, tasks, emails):
    """Simple template-based version so the scaffold works with no API key.
    Does NOT include the greeting — that's spoken separately via
    build_instant_greeting()."""
    lines = []
    lines.append(
        f"Here's your briefing for today. "
        f"Expect {weather.get('condition', 'mixed conditions')}, with a high of "
        f"{weather['high']} degrees and a low of {weather['low']}, "
        f"with about a {weather['precip_chance']} percent chance of precipitation, "
        f"and wind around {weather.get('wind_speed_mph', 0)} miles per hour out of the "
        f"{weather.get('wind_direction', 'northwest')}"
        + (f", gusting up to {weather['wind_gust_mph']} miles per hour" if weather.get('wind_gust_mph') else "")
        + "."
    )

    if events:
        lines.append(f"You've got {len(events)} things on the calendar today.")
        for e in events:
            lines.append(f"At {e['start']}, {e['title']}.")
    else:
        lines.append("Your calendar is clear today.")

    if tasks:
        lines.append(f"You have {len(tasks)} open tasks, including: " +
                      ", ".join(t["title"] for t in tasks[:3]) + ".")

    if emails:
        lines.append(f"You've got {len(emails)} important emails waiting, including one from "
                      f"{emails[0]['from']} about {emails[0]['subject']}.")
    else:
        lines.append("No important emails flagged right now.")

    lines.append(f"That's your briefing. Grab a Red Bull, go {_seasonal_activity()}, "
                 f"and have a good day, sir.")
    return " ".join(lines)


def _current_time_spoken():
    """Returns the current time formatted naturally for speech, e.g. '8:00 AM'."""
    now = datetime.now()
    # Strip leading zero from hour (e.g. "08:00 AM" -> "8:00 AM")
    return now.strftime("%I:%M %p").lstrip("0")


def _seasonal_activity():
    """
    Returns 'ski' or 'mountain bike' based on the current month.
    Rough Colorado mountain season split: Nov-Apr is ski season,
    May-Oct is mountain bike season. Easy to fine-tune later.
    """
    month = datetime.now().month
    if month in (11, 12, 1, 2, 3, 4):
        return "ski"
    return "mountain bike"


def _format_events(events):
    if not events:
        return "None"
    return "\n".join(f"- {e['start']}-{e['end']}: {e['title']}" for e in events)


def _format_tasks(tasks):
    if not tasks:
        return "None"
    return "\n".join(f"- {t['title']} (due: {t['due']})" for t in tasks)


def _format_emails(emails):
    if not emails:
        return "None"
    return "\n".join(f"- From {e['from']}: {e['subject']} — {e['snippet']}" for e in emails)
