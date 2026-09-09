"""Report the primary metric: python analyse.py [--min-ticks N]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from vsa.report import main

if __name__ == "__main__":
    main()
