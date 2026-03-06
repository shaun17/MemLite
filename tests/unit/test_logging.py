import logging

from memlite.common.config import Settings
from memlite.common.logging import configure_logging


def test_configure_logging_sets_root_level():
    settings = Settings(log_level="DEBUG")

    configure_logging(settings)

    assert logging.getLogger().level == logging.DEBUG
