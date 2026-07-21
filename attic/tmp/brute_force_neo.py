import math

def calculate_cuota(registro):
    precio = 6699999
    inicial = 1004999
    meses = 24
    factor = 0.0523336
    
    # 1. Base
    capital_inicial = (precio - inicial) + registro
    
    # 2. Aval Diferido
    # Not crediorbe? Ah wait. For crediorbe, there's NO FNG (unless it's in the config?). Wait, crediorbe uses includeRegistration = 'No' or 'Yes'?
    # Let me actually just call MotorFinanciero with a mock that injects the registry and see what happens!
    from app.services.finance import MotorFinanciero
    from app.services.config_service import ConfigService
    
    cf = ConfigService()
    cf._financial_config = {
        "tasa_nmv_banco": 1.87,
        "tasa_nmv_fintech": 2.22,
        "fng_rate": 20.66,
        "life_insurance_monthly": 15000,
        "brillaManagementRate": 5,
        "coverageRate": 4
    }
    cf._partners_config = {}
    
    m = MotorFinanciero(cf)
    
    for r in range(100000, 300000, 1000):
        m._get_matrix_row = lambda a,b,c: {"registrationCreditGeneral": r, "factors": {"24": factor}}
        m._get_entity_config = lambda a: {"lifeInsuranceValue": 15000}
        
        try:
            res = m.calcular_cuota(precio=precio, inicial=inicial, plazo_meses=meses, entidad="crediorbe", moto_cc=109.7)
            if round(res.get("cuota_mensual", 0), 0) == 416647:
                print(f"BINGO! Registration is {r}")
                print(res)
                return
        except Exception:
            pass
            
calculate_cuota(0)

