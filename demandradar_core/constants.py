"""Shared constants for DemandRadar."""

VERSION = "0.5.0"
USER_AGENT = f"DemandRadar/{VERSION} (+https://github.com/099popovB2c/DemandRadar)"

SOFTWARE_REQUEST_TEMPLATES = [
    '"looking for" app',
    '"is there an app"',
    '"alternative to"',
    '"wish there was"',
    '"need a tool"',
    '"looking for software"',
]

RETRYABLE_HTTP_STATUS = {408, 429, 500, 502, 503, 504}
