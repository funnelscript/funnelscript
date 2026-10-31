import sys
from pathlib import Path

# Add src to sys.path
src_path = str(Path(__file__).parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from funnelscript.cli import main

if __name__ == "__main__":
    main()
