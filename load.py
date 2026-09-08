"""Convert recorded snapshots to Parquet: python load.py [--force]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from vsa.load import main

if __name__ == "__main__":
    main()
