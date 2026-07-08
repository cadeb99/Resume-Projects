"""The human-like response delay should always fall within the configured range."""

from app.config import get_settings


def test_delay_within_configured_bounds():
    settings = get_settings()
    lo = settings.response_delay_min_minutes * 60.0
    hi = settings.response_delay_max_minutes * 60.0
    # Sample many times since it's random.
    for _ in range(200):
        delay = settings.random_response_delay_seconds()
        assert lo <= delay <= hi


def test_delay_is_randomized():
    settings = get_settings()
    values = {settings.random_response_delay_seconds() for _ in range(50)}
    # Extremely unlikely to all be identical if it's truly random.
    assert len(values) > 1
