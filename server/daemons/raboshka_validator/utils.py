import os
import sys
import logging

logger = logging.getLogger(__name__)

def get_env_or_die(name: str) -> str:
    """Get environment variable or exit with error if not set."""
    value = os.getenv(name)
    if value is None:
        logger.critical(f"Environment variable '{name}' is required but not set.")
        sys.exit(1)
    return value
