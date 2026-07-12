"""
tests/test_catalog_initialization_sync.py

Test suite for BOT-BACKEND-HOTFIX-CATALOG-INITIALIZATION-SYNC-169.

Verifies the fail-fast behavior of CatalogService when ConfigLoader is
injected but fails to hydrate category_aliases correctly, preventing
zombie container deployment with broken alias resolution.
"""
import logging
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ["TEST_MODE"] = "true"

from app.services.catalog_service import CatalogService


class TestCatalogInitializationSync(unittest.TestCase):
    """
    Characterization test suite for the CatalogService initialization
    dependency injection refactor (ticket 169).
    """

    def _make_mock_db(self, items=None):
        """Build a mock Firestore client that streams a list of mock docs."""
        mock_db = MagicMock()
        docs = items or []
        mock_db.collection.return_value.document.return_value.collection.return_value.stream.return_value = iter(docs)
        return mock_db

    def _make_mock_doc(self, doc_id="moto_1", price=3500000, categoria="urban"):
        """Build a minimal mock Firestore document."""
        doc = MagicMock()
        doc.id = doc_id
        doc.to_dict.return_value = {
            "brand": "TVS",
            "referencia": "Sport 100",
            "price": price,
            "categoria": categoria,
            "imagen_url": "https://example.com/sport.jpg",
            "active": True,
            "isVisible": True,
            "onStock": True,
        }
        return doc

    # --------------------------------------------------------------------------
    # TEST 1: Fail-Fast — RuntimeError when ConfigLoader injected but aliases empty
    # --------------------------------------------------------------------------
    def test_catalog_initialization_failure_raises_runtime_error_when_aliases_empty(self):
        """
        [BOT-BACKEND-HOTFIX-CATALOG-INITIALIZATION-SYNC-169]
        REQUIRED TEST AUTOPSY: Verifies that CatalogService raises RuntimeError
        (fail-fast guardrail) when a ConfigLoader is explicitly injected via
        initialize() but resolves to empty category_aliases, preventing deployment
        of zombie containers with broken alias resolution (ticket 163 regression).
        """
        service = CatalogService()

        # Build a ConfigLoader mock that returns an empty category_aliases dict
        # (simulates a missing or corrupted Firestore 'configuracion/catalog_config' doc)
        mock_config_loader = MagicMock()
        mock_config_loader.get_catalog_config.return_value = {
            "category_aliases": {}  # <- Empty: triggers the fail-fast guardrail
        }

        mock_db = self._make_mock_db(items=[self._make_mock_doc()])

        # The RuntimeError MUST propagate up from load_catalog()
        with self.assertRaises(RuntimeError) as ctx:
            service.initialize(mock_db, config_loader=mock_config_loader)

        error_message = str(ctx.exception)
        self.assertIn("[CATALOG-INIT-FAILURE]", error_message, (
            "RuntimeError must contain the structured error tag [CATALOG-INIT-FAILURE] "
            "for forensic log tracing."
        ))
        self.assertIn("category_aliases", error_message, (
            "RuntimeError message must mention 'category_aliases' to identify the failing field."
        ))

    # --------------------------------------------------------------------------
    # TEST 2: Happy Path — Aliases hydrated correctly via injected ConfigLoader
    # --------------------------------------------------------------------------
    def test_catalog_initializes_correctly_with_injected_config_loader(self):
        """
        Verifies that when a properly hydrated ConfigLoader is injected,
        CatalogService successfully resolves category_aliases and loads items.
        """
        service = CatalogService()

        mock_config_loader = MagicMock()
        mock_config_loader.get_catalog_config.return_value = {
            "category_aliases": {
                "deportiva": ["pistera", "sport", "deportiva"],
                "urbana": ["urban", "ciudad"],
            }
        }

        mock_db = self._make_mock_db(items=[self._make_mock_doc()])

        # Should NOT raise
        service.initialize(mock_db, config_loader=mock_config_loader)

        # Aliases must be hydrated
        aliases = CatalogService.get_catalog_aliases()
        self.assertIn("deportiva", aliases, "Category 'deportiva' alias must be loaded.")
        self.assertIn("pistera", aliases.get("deportiva", []), (
            "'pistera' must be in the alias list for 'deportiva'."
        ))

    # --------------------------------------------------------------------------
    # TEST 3: Degraded Path — No config_loader injected (singleton fallback)
    # --------------------------------------------------------------------------
    def test_catalog_initializes_without_config_loader_using_empty_aliases(self):
        """
        Verifies the degraded path: when no config_loader is injected and no
        singleton is available, CatalogService proceeds with empty aliases and
        logs a warning instead of crashing.
        """
        service = CatalogService()
        mock_db = self._make_mock_db(items=[self._make_mock_doc()])

        # Ensure no singleton is set
        with patch("app.core.config_loader.ConfigLoader._instance", None):
            # Should NOT raise — degraded path tolerates empty aliases
            try:
                service.initialize(mock_db, config_loader=None)
            except RuntimeError as e:
                self.fail(
                    f"initialize() without config_loader should NOT raise RuntimeError, "
                    f"but got: {e}"
                )

    # --------------------------------------------------------------------------
    # TEST 4: Verify _config_loader is stored correctly in __init__
    # --------------------------------------------------------------------------
    def test_config_loader_attribute_initialized_to_none(self):
        """
        Verifies the structural invariant: _config_loader is initialized to None
        in __init__ before any call to initialize().
        """
        service = CatalogService()
        self.assertIsNone(
            service._config_loader,
            "_config_loader must be None before initialize() is called."
        )

    # --------------------------------------------------------------------------
    # TEST 5: Verify initialize() stores the injected config_loader
    # --------------------------------------------------------------------------
    def test_initialize_stores_injected_config_loader(self):
        """
        Verifies that after calling initialize(db, config_loader), the service
        stores the config_loader reference in self._config_loader.
        """
        service = CatalogService()

        mock_config_loader = MagicMock()
        mock_config_loader.get_catalog_config.return_value = {
            "category_aliases": {"deportiva": ["pistera"]}
        }
        mock_db = self._make_mock_db(items=[])

        # Patch the stream to return empty (no items to load) to simplify test
        service.initialize(mock_db, config_loader=mock_config_loader)

        self.assertIs(
            service._config_loader,
            mock_config_loader,
            "initialize() must store the injected config_loader in self._config_loader."
        )


if __name__ == "__main__":
    unittest.main()
