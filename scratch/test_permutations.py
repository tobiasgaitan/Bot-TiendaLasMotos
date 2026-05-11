
import asyncio
from google.cloud import firestore
from app.services.config_service import config_service
from app.services.financial_service import financial_service

async def test_permutation(precio, inicial, plazo, cc, fng_rate, reg_cost, base_aval_is_capital):
    monto_base = precio - inicial
    capital_inicial = monto_base + reg_cost
    fng_cost = capital_inicial * (fng_rate / 100)
    P_final = capital_inicial + fng_cost
    
    factor = 0.0523336 # for 24m
    cuota_financiera = P_final * factor
    
    base_aval = capital_inicial if base_aval_is_capital else P_final
    cuota_aval = (base_aval * 0.04) / 12
    
    total = cuota_financiera + cuota_aval
    return total, P_final

async def inspect():
    db = firestore.Client()
    config_service.initialize(db)
    
    p, i, t, cc = 11100000, 1500000, 24, 160.0
    
    print(f"Target: 589787")
    
    # Try 1: Current logic (FNG 20.66, Reg 0)
    res, p_fin = await test_permutation(p, i, t, cc, 20.66, 0, False)
    print(f"Try 1 (FNG 20.66, Reg 0, base_aval=P_final): {res:.0f} (P_fin: {p_fin:.0f})")
    
    # Try 2: FNG 11.99661, Reg 0
    res, p_fin = await test_permutation(p, i, t, cc, 11.99661, 0, False)
    print(f"Try 2 (FNG 11.99, Reg 0, base_aval=P_final): {res:.0f} (P_fin: {p_fin:.0f})")
    
    # Try 3: FNG 11.99661, Reg 0, base_aval=capital_inicial
    res, p_fin = await test_permutation(p, i, t, cc, 11.99661, 0, True)
    print(f"Try 3 (FNG 11.99, Reg 0, base_aval=cap): {res:.0f} (P_fin: {p_fin:.0f})")

    # Try 4: FNG 0, Reg 860000 (Global), base_aval=P_final
    res, p_fin = await test_permutation(p, i, t, cc, 0, 860000, False)
    print(f"Try 4 (FNG 0, Reg 860k, base_aval=P_final): {res:.0f} (P_fin: {p_fin:.0f})")
    
    # Try 5: FNG 11.99661, Reg 0, BUT factor for 24m is different?
    # No, factor is 0.0523336.
    
    # Try 6: What if FNG is calculated on monto_base only?
    fng_cost = (p - i) * (11.99661 / 100)
    p_fin = (p - i) + 0 + fng_cost
    res = p_fin * 0.0523336 + (p_fin * 0.04 / 12)
    print(f"Try 6 (FNG on base only, Reg 0): {res:.0f}")

    # Try 7: What if P_final includes Seguro de Vida?
    # 589787.
    # If P_final = 10594930.
    # 9600000 + 994930.
    # 994930 / 9600000 = 10.36%.
    
    # Wait! 10.36% is very close to 10% + IVA? No.
    
    # Wait! I just noticed something.
    # 11,100,000 * 0.0523336 = 580,903.
    # 11,100,000 * 0.0556669 = 617,902.
    
    # What if the simulation is for 0 initial?
    # No, the test says 1.5M init.

if __name__ == '__main__':
    asyncio.run(inspect())
