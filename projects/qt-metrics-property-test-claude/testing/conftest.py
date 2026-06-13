import sys
import os

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hypothesis import settings

# Default: 50 examples, enough for local dev
settings.register_profile("default", max_examples=50)

# CI: fewer examples to stay under 30s total
settings.register_profile("ci", max_examples=30, deadline=5000)

settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "default"))
