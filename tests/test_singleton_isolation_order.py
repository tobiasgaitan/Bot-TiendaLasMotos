"""
Pins de Aislamiento de Singletons — [M4-ARNÉS-AISLAMIENTO-001]

Red anti-regresión del fixture autouse `purge_config_loader_singletons`
(tests/conftest.py): certifica que la higiene de ConfigLoader/FinanceConfigLoader
entre tests funciona bajo CUALQUIER orden de ejecución.

Contexto forense: tests/test_pcc_ficha_tecnica.py aloja 6 tests que instancian
ConfigLoader(db) contra Firestore de producción y dejan el singleton contaminado
(_instance/_initialized ligados a credenciales y config reales), corrompiendo
tests de concurrencia posteriores vía __init__ no-op.

Estrategia: PIN-ISO-1 (contaminador sintético con anti-silent-pass) definido
ANTES que PIN-ISO-2 (detector). pytest nativo garantiza orden in-file = orden
de definición, así que en ejecución secuencial la adyacencia asesina está
asegurada; bajo shuffle aleatorio, el detector es order-agnóstico por
construcción (donde caiga, debe estar verde).

WHY imports runtime (no a nivel módulo): tests/test_config_startup.py expulsa
`app.core.config*` de sys.modules (matchea "app.core.config" in m), lo que
re-importa config_loader como clase NUEVA. Importar dentro del cuerpo del test
garantiza que pin y fixture resuelven SIEMPRE la misma clase vigente
(fenómeno BOT-174: divergencia de identidad de clases por expulsión).
"""


def test_pin_iso_1_synthetic_polluter():
    """
    PIN-ISO-1 (contaminador sintético): instala un centinela sucio en ambos
    singletons y ASEVERA que la contaminación quedó efectivamente instalada
    (anti-silent-pass: el pin no puede pasar sin contaminar de verdad).

    NO restaura nada: la higiene queda delegada al fixture autouse
    `purge_config_loader_singletons` — esa es exactamente la tesis bajo prueba.
    """
    from unittest.mock import MagicMock
    from app.core.config_loader import ConfigLoader
    from app.services.config_loader import FinanceConfigLoader

    sentinel = MagicMock(name="sentinel_contamination")
    ConfigLoader._instance = sentinel
    ConfigLoader._initialized = True
    FinanceConfigLoader._instance = sentinel
    FinanceConfigLoader._initialized = True

    # Anti-silent-pass: la contaminación debe ser real y observable.
    assert ConfigLoader._instance is sentinel
    assert ConfigLoader._initialized is True
    assert FinanceConfigLoader._instance is sentinel
    assert FinanceConfigLoader._initialized is True


def test_pin_iso_2_isolation_detector():
    """
    PIN-ISO-2 (detector order-agnóstico): verde SOLO si el fixture autouse
    purgó los singletons tras cualquier test previo (en secuencial: el
    contaminador PIN-ISO-1 definido arriba).

    NO purga por cuenta propia — si lo hiciera, el pin no detectaría nada y
    sería una vacuna en lugar de una red.
    """
    from app.core.config_loader import ConfigLoader
    from app.services.config_loader import FinanceConfigLoader

    assert ConfigLoader._instance is None, (
        "ConfigLoader._instance contaminado al inicio del test: el fixture "
        "autouse purge_config_loader_singletons no purgó (setup/teardown)."
    )
    assert ConfigLoader._initialized is False, (
        "ConfigLoader._initialized contaminado al inicio del test."
    )
    assert FinanceConfigLoader._instance is None, (
        "FinanceConfigLoader._instance contaminado al inicio del test."
    )
    assert FinanceConfigLoader._initialized is False, (
        "FinanceConfigLoader._initialized contaminado al inicio del test."
    )
