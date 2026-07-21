"""
[BOT-BUILD-REFACTOR-03-05-RESIDUAL] WS-3 — Autopsia de atomicidad del refresh de configuración.

Demuestra físicamente, con un Firestore falso determinista (latencia + barreras +
inyección de fallos), el invariante exigido por el ticket:

    INV-1 (Consistencia):   ningún lector concurrente observa jamás un estado
                            RASGADO (mezcla de versiones entre los 3 documentos).
    INV-2 (Sin defaults transitorios): ningún lector observa defaults de emergencia
                            mientras coexiste un snapshot válido previo.
    INV-3 (Ponytail/fallo): ante fallo parcial de Firestore, el estado FINAL
                            committed conserva la semántica de fallback por documento
                            (idéntica al comportamiento legacy).
    INV-4 (Vía rápida):     los getters NO adquieren el RLock de escritura.

Ejecutar PRE-fix: los tests 1, 2, 3, 5 y 6 FALLAN (autopsia de la vulnerabilidad).
Ejecutar POST-fix: toda la suite pasa (demostración del invariante).
"""

import threading
import time

import pytest

from app.core.config_loader import ConfigLoader
from app.services.config_loader import FinanceConfigLoader

# ============================================================================
# Fake Firestore determinista (latencia, hooks de barrera, inyección de fallos)
# ============================================================================

PERSONALITY_PATH = "configuracion/juan_pablo_personality"
ROUTING_PATH = "configuracion/routing_rules"
CATALOG_PATH = "configuracion/catalog_config"
FINANCIAL_PATH = "financial_config/general/global_params/global_params"
PARTNERS_PATH = "configuracion/aliados"


class _FakeDoc:
    def __init__(self, payload):
        self._payload = payload
        self.exists = payload is not None

    def to_dict(self):
        return dict(self._payload)


class _FakeDocRef:
    def __init__(self, db, path):
        self._db = db
        self._path = path

    def collection(self, name):
        return _FakeCollection(self._db, f"{self._path}/{name}")

    def get(self):
        return self._db._get(self._path)


class _FakeCollection:
    def __init__(self, db, path):
        self._db = db
        self._path = path

    def document(self, name):
        return _FakeDocRef(self._db, f"{self._path}/{name}")


class _FakeDB:
    """Firestore falso: payloads versionados + latencia + hooks + fallos por path."""

    def __init__(self):
        self._docs = {}
        self._latency = {}
        self._hooks = {}
        self._fail = set()

    def collection(self, name):
        return _FakeCollection(self, name)

    def set_doc(self, path, payload):
        self._docs[path] = payload

    def set_docs(self, docs):
        for path, payload in docs.items():
            self._docs[path] = payload

    def set_latency(self, path, seconds):
        self._latency[path] = seconds

    def set_hook(self, path, fn):
        self._hooks[path] = fn

    def set_failure(self, path, on=True):
        (self._fail.add if on else self._fail.discard)(path)

    def _get(self, path):
        if path in self._hooks:
            self._hooks[path]()
        if self._latency.get(path):
            time.sleep(self._latency[path])
        if path in self._fail:
            raise RuntimeError(f"simulated Firestore failure at {path}")
        return _FakeDoc(self._docs.get(path))


# ============================================================================
# Payloads versionados (la clave 'version' ausente == default transitorio)
# ============================================================================

def _core_docs(v):
    return {
        PERSONALITY_PATH: {
            "name": "Juan Pablo",
            "model_version": f"gemini-test-v{v}",
            "system_instruction": f"instr-{v}",
            "version": v,
        },
        ROUTING_PATH: {
            "financial_keywords": [f"kw-{v}"],
            "sales_keywords": [],
            "default_handler": "cerebro_ia",
            "version": v,
        },
        CATALOG_PATH: {
            "items": [f"item-{v}"],
            "category_aliases": {},
            "version": v,
        },
    }


def _finance_docs(v):
    return {
        FINANCIAL_PATH: {"tasa_nmv_banco": 1.0 + v / 1000.0, "version": v},
        PARTNERS_PATH: {"link_banco_bogota": f"https://example.test/v{v}", "version": v},
    }


def _sample_core(loader):
    p = loader.get_juan_pablo_personality()
    r = loader.get_routing_rules()
    c = loader.get_catalog_config()
    return (p.get("version"), r.get("version"), c.get("version"))


def _sample_finance(loader):
    f = loader.get_financial_config()
    p = loader.get_partners_config()
    return (f.get("version"), p.get("version"))


def _is_consistent(trio):
    return trio[0] is not None and len(set(trio)) == 1


def _is_torn_or_transient(seq):
    """
    Invariante exacto demostrable de assign-at-end para muestreos multi-getter:

    - Cualquier None == default transitorio expuesto (INV-2 violado).
    - Secuencia DECRECIENTE (seq[i] > seq[i+1]) == el lector se ADELANTÓ al
      commit: observó un store parcial en vuelo (INV-1 violado). Es la firma
      del bug original, p.ej. (2,1,1) con personalidad nueva y routing viejo.
    - Secuencias NO-decrecientes (k,k) o (k,k+1) son straddles legítimos: el
      lector quedó ENTRE dos snapshots committed completos e íntegros (cada
      getter leyó un valor committed; es físicamente inevitable sin cambiar la
      API pública a un get_all() único y no constituye estado rasgado).
    """
    if any(v is None for v in seq):
        return True
    return any(seq[i] > seq[i + 1] for i in range(len(seq) - 1))


# ============================================================================
# Fixture: higiene de singletons (ambos loaders son Singleton de clase)
# ============================================================================

@pytest.fixture(autouse=True)
def _reset_singletons():
    ConfigLoader._instance = None
    ConfigLoader._initialized = False
    FinanceConfigLoader._instance = None
    FinanceConfigLoader._initialized = False
    yield
    ConfigLoader._instance = None
    ConfigLoader._initialized = False
    FinanceConfigLoader._instance = None
    FinanceConfigLoader._initialized = False


def _run_tracked(target, errors):
    """Ejecuta target registrando excepciones para fallar ruidosamente."""
    try:
        target()
    except Exception as exc:  # pragma: no cover - forensic guard
        errors.append(exc)


# ============================================================================
# TEST 1 — Estrés concurrente (core): lectores continuos vs 25 refreshes
# ============================================================================

def test_core_stress_no_torn_reads_under_concurrent_refresh():
    db = _FakeDB()
    db.set_docs(_core_docs(1))
    for path in (PERSONALITY_PATH, ROUTING_PATH, CATALOG_PATH):
        db.set_latency(path, 0.0015)  # 1.5ms por documento → ventana de rasgado

    loader = ConfigLoader(db)
    loader.load_all()
    assert _sample_core(loader) == (1, 1, 1)

    stop = threading.Event()
    violations = []
    samples = [0]
    errors = []

    def reader():
        while not stop.is_set():
            trio = _sample_core(loader)
            samples[0] += 1
            if _is_torn_or_transient(trio):
                violations.append(trio)

    readers = [threading.Thread(target=reader, daemon=True) for _ in range(3)]
    for r in readers:
        r.start()

    def writer():
        for v in range(2, 27):
            db.set_docs(_core_docs(v))
            loader.refresh()

    errors.clear()
    _run_tracked(writer, errors)
    stop.set()
    for r in readers:
        r.join(timeout=5)

    assert not errors, f"writer falló: {errors}"
    assert not violations, (
        f"INV-1/INV-2 VIOLADO: {len(violations)} lecturas rasgadas o con default "
        f"transitorio de {samples[0]} muestras. Ejemplos: {violations[:5]}"
    )


# ============================================================================
# TEST 2 — Barrera determinista (core): ningún estado intermedio visible
#           mientras el refresh está a mitad de la fase de fetch.
# ============================================================================

def test_core_deterministic_no_intermediate_state_during_fetch():
    db = _FakeDB()
    db.set_docs(_core_docs(1))
    loader = ConfigLoader(db)
    loader.load_all()
    assert _sample_core(loader) == (1, 1, 1)

    db.set_docs(_core_docs(2))
    entered_routing = threading.Event()
    release_routing = threading.Event()

    def _barrier():
        entered_routing.set()
        release_routing.wait(10)

    db.set_hook(ROUTING_PATH, _barrier)

    errors = []
    writer = threading.Thread(target=lambda: _run_tracked(loader.refresh, errors), daemon=True)
    writer.start()

    assert entered_routing.wait(10), "el writer nunca alcanzó la barrera de routing"
    # En este instante el fetch de personalidad (v2) YA ocurrió; catalog (v1) aún no.
    mid_trio = _sample_core(loader)
    release_routing.set()
    writer.join(timeout=10)

    assert not errors, f"writer falló: {errors}"
    assert _is_consistent(mid_trio), (
        f"INV-1 VIOLADO (determinista): estado intermedio visible durante el "
        f"fetch del refresh → {mid_trio}. Se exige snapshot completo previo (1,1,1)."
    )
    assert mid_trio == (1, 1, 1), (
        f"Se esperaba el snapshot previo íntegro (1,1,1) durante el fetch, "
        f"observado: {mid_trio}"
    )
    assert _sample_core(loader) == (2, 2, 2), "el commit final no publicó v2 íntegra"


# ============================================================================
# TEST 3 — Inyección de fallo (core): sin defaults transitorios; el fallback
#           final por documento se preserva (semántica legacy / ponytail).
# ============================================================================

def test_core_failure_injection_no_transient_defaults_and_final_fallback_preserved():
    db = _FakeDB()
    db.set_docs(_core_docs(1))
    loader = ConfigLoader(db)
    loader.load_all()
    assert _sample_core(loader) == (1, 1, 1)

    db.set_docs(_core_docs(2))
    db.set_failure(ROUTING_PATH, True)  # routing_rules falla a mitad del refresh

    entered_catalog = threading.Event()
    release_catalog = threading.Event()

    def _barrier():
        entered_catalog.set()
        release_catalog.wait(10)

    db.set_hook(CATALOG_PATH, _barrier)

    errors = []
    writer = threading.Thread(target=lambda: _run_tracked(loader.refresh, errors), daemon=True)
    writer.start()

    assert entered_catalog.wait(10), "el writer nunca alcanzó la barrera de catalog"
    # En este instante: personality v2 ya leída; routing FALLÓ (→ default); catalog aún no.
    mid_trio = _sample_core(loader)
    release_catalog.set()
    writer.join(timeout=10)

    assert not errors, f"writer falló: {errors}"
    assert mid_trio == (1, 1, 1), (
        f"INV-2 VIOLADO: durante un refresh con fallo parcial se observó "
        f"{mid_trio} (estado rasgado y/o default transitorio). Se exige el "
        f"snapshot previo íntegro (1,1,1) hasta el commit."
    )

    # INV-3: el estado FINAL committed preserva el fallback por documento:
    # personality y catalog en v2; routing en su default (igual que el legacy).
    final_trio = _sample_core(loader)
    assert final_trio == (2, None, 2), (
        f"Semántica de fallback final alterada (ponytail): {final_trio} != (2, None, 2)"
    )
    assert loader.get_routing_rules() == loader._get_default_routing_rules()


# ============================================================================
# TEST 4 — Estrés concurrente (finance): par financiero/partners consistente
# ============================================================================

def test_finance_stress_pair_consistency():
    db = _FakeDB()
    db.set_docs(_finance_docs(1))
    db.set_latency(FINANCIAL_PATH, 0.0015)
    db.set_latency(PARTNERS_PATH, 0.0015)

    loader = FinanceConfigLoader(db)
    loader.initialize(db)
    assert _sample_finance(loader) == (1, 1)
    # TTL en el futuro lejano: los getters de los lectores NUNCA disparan refresh.
    loader._last_fetch_time = time.time() + 3600

    stop = threading.Event()
    violations = []
    samples = [0]
    errors = []

    def reader():
        while not stop.is_set():
            pair = _sample_finance(loader)
            samples[0] += 1
            if _is_torn_or_transient(pair):
                violations.append(pair)

    readers = [threading.Thread(target=reader, daemon=True) for _ in range(3)]
    for r in readers:
        r.start()

    def writer():
        for v in range(2, 27):
            db.set_docs(_finance_docs(v))
            loader._refresh_cache()

    _run_tracked(writer, errors)
    stop.set()
    for r in readers:
        r.join(timeout=5)

    assert not errors, f"writer falló: {errors}"
    assert not violations, (
        f"INV-1/INV-2 VIOLADO (finance): {len(violations)} pares rasgados o con "
        f"default transitorio de {samples[0]} muestras. Ejemplos: {violations[:5]}"
    )


# ============================================================================
# TEST 5 — Barrera determinista (finance): ningún estado intermedio visible
#           entre el store financiero y el store de partners.
# ============================================================================

def test_finance_deterministic_no_intermediate_state():
    db = _FakeDB()
    db.set_docs(_finance_docs(1))
    loader = FinanceConfigLoader(db)
    loader.initialize(db)
    assert _sample_finance(loader) == (1, 1)
    loader._last_fetch_time = time.time() + 3600  # lectores nunca disparan refresh

    db.set_docs(_finance_docs(2))
    entered_partners = threading.Event()
    release_partners = threading.Event()

    def _barrier():
        entered_partners.set()
        release_partners.wait(10)

    db.set_hook(PARTNERS_PATH, _barrier)

    errors = []
    writer = threading.Thread(target=lambda: _run_tracked(loader._refresh_cache, errors), daemon=True)
    writer.start()

    assert entered_partners.wait(10), "el writer nunca alcanzó la barrera de partners"
    # En este instante el documento financiero (v2) YA fue leído; partners (v1) aún no.
    mid_pair = _sample_finance(loader)
    release_partners.set()
    writer.join(timeout=10)

    assert not errors, f"writer falló: {errors}"
    assert mid_pair == (1, 1), (
        f"INV-1 VIOLADO (finance, determinista): estado intermedio visible "
        f"durante el refresh → {mid_pair}. Se exige (1, 1) hasta el commit."
    )
    assert _sample_finance(loader) == (2, 2), "el commit final no publicó v2 íntegra"


# ============================================================================
# TEST 6 — Vía rápida: los getters NO adquieren el RLock de escritura.
# ============================================================================

def test_core_getters_never_acquire_write_lock():
    db = _FakeDB()
    db.set_docs(_core_docs(1))
    loader = ConfigLoader(db)
    loader.load_all()

    lock = getattr(loader, "_write_lock", None)
    assert lock is not None, "RLock de escritura inexistente (control de serialización ausente)"

    lock.acquire()
    try:
        done = threading.Event()

        def read():
            loader.get_juan_pablo_personality()
            loader.get_routing_rules()
            loader.get_catalog_config()
            done.set()

        t = threading.Thread(target=read, daemon=True)
        t.start()
        assert done.wait(5), "INV-4 VIOLADO: un getter quedó bloqueado por el RLock"
        t.join(timeout=5)
    finally:
        lock.release()


def test_finance_getters_never_acquire_write_lock():
    db = _FakeDB()
    db.set_docs(_finance_docs(1))
    loader = FinanceConfigLoader(db)
    loader.initialize(db)  # deja _last_fetch_time fresco (TTL 300s)

    lock = getattr(loader, "_write_lock", None)
    assert lock is not None, "RLock de escritura inexistente (control de serialización ausente)"

    lock.acquire()
    try:
        done = threading.Event()

        def read():
            loader.get_financial_config()
            loader.get_partners_config()
            done.set()

        t = threading.Thread(target=read, daemon=True)
        t.start()
        assert done.wait(5), "INV-4 VIOLADO (finance): un getter quedó bloqueado por el RLock"
        t.join(timeout=5)
    finally:
        lock.release()
