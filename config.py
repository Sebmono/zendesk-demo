"""
Configuration for the Zendesk demo-data scripts.

Every credential is read from the environment. Nothing secret is stored in this
file. Copy .env.example to .env and fill it in, or export the variables in your
shell, before running any script.
"""

import os
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is optional; plain env vars work too
    pass


def _require(name: str) -> str:
    """Read a required environment variable or exit with a clear message."""
    value = os.environ.get(name)
    if not value:
        sys.exit(
            f"Missing required environment variable: {name}\n"
            "Copy .env.example to .env and fill it in, or export the variable "
            "in your shell. See the Configuration section of README.md."
        )
    return value


# Zendesk API configuration
API_TOKEN = _require("ZENDESK_API_TOKEN")
ADMIN_EMAIL = _require("ZENDESK_EMAIL")
SUBDOMAIN = _require("ZENDESK_SUBDOMAIN")

# Base URL for API calls
BASE_URL = f"https://{SUBDOMAIN}.zendesk.com/api/v2"

# Anthropic API configuration
ANTHROPIC_API_KEY = _require("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
