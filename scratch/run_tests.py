import sys
import os
from unittest.mock import MagicMock

# Add app to path
sys.path.append(os.path.abspath(os.getcwd()))

# Mock google.cloud.firestore
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.cloud.firestore"] = MagicMock()

import unittest
from tests.test_catalog_scoring import TestCatalogScoring

if __name__ == '__main__':
    unittest.main()
