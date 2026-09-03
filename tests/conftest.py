import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# LangChain validates credentials when the project graphs are imported. Tests
# replace all model calls, so this value is never sent anywhere.
os.environ.setdefault("OPENAI_API_KEY", "test-key")
