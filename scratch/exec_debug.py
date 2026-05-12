import sys
import os
from unittest.mock import MagicMock

# Add app to path
sys.path.append(os.path.abspath(os.getcwd()))

# Mock firestore before any imports
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.cloud.firestore"] = MagicMock()
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()

import runpy
runpy.run_path("scratch/debug_scoring.py")
