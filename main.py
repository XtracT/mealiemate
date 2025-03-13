#!/usr/bin/env python3
"""
Module: main
------------
Main entry point for the MealieMate application.

This module initializes and starts the MealieMate application.
"""

import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

from core.app import MealieMateApp

# Load environment variables
load_dotenv()

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
log_level_map = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}
logging.basicConfig(
    level=log_level_map.get(LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info(f"Logging level set to {LOG_LEVEL}")

async def main() -> None:
    """Main entry point for the MealieMate service."""
    try:
        app = MealieMateApp()
        await app.initialize()
        await app.start()
    except Exception as e:
        logger.critical(f"Fatal error in main: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
