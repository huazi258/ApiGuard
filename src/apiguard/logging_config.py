"""Safe standard-library logging setup."""

import logging

from apiguard.config import Settings


def configure_logging(settings: Settings) -> None:
    """Configure logging without serializing settings or environment values."""

    logger = logging.getLogger("apiguard")
    logger.setLevel(settings.log_level)
    logger.propagate = False

    if logger.handlers:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logger.addHandler(handler)
