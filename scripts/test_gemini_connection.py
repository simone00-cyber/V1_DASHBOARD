from pathlib import Path
import os

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

print("ROOT:", ROOT)

loaded = load_dotenv(ROOT / ".env")

print("DOTENV LOADED:", loaded)
print("KEY EXISTS:", os.getenv("GEMINI_API_KEY") is not None)
print("KEY PREFIX:", str(os.getenv("GEMINI_API_KEY"))[:10])