#!/usr/bin/env python3
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from seeds.seed_all import seed_all

if __name__ == "__main__":
    asyncio.run(seed_all())
