"""Configuration loader module."""

import json
import logging
from typing import Any, Dict


class ConfigLoader:
    """Load and validate configuration from JSON file."""

    @staticmethod
    def load(config_path: str = "config.json") -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(config_path, "r") as f:
                config = json.load(f)

            logging.info("Configuration loaded from %s", config_path)

            return config
        except FileNotFoundError:
            logging.error("Configuration file not found: %s", config_path)

            raise
        except json.JSONDecodeError as e:
            logging.error("Invalid JSON in configuration file: %s", e)

            raise
