
import asyncio
from google.cloud import firestore
from app.services.config_service import config_service
from app.services.finance import MotorFinanciero

async def test_legacy():
    db = firestore.Client()
    config_service.initialize(db)
    motor = MotorFinanciero(db, config_service)
    
    precio = 11100000
    inicial = 1500000
    plazo_meses = 24
    moto_cc = 160.0
    
    res = motor.calcular_cuota(precio, inicial, plazo_meses, moto_cc=moto_cc)
    print(f"Legacy Result: {res}")

if __name__ == '__main__':
    asyncio.run(test_legacy())
