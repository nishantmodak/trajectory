#!/usr/bin/env python3
"""Trajectory CLI entry point.

This file allows running trajectory directly:
    python trajectory.py

For installed usage, use:
    trajectory
"""

import sys
from trajectory.cli import main

if __name__ == "__main__":
    sys.exit(main())
