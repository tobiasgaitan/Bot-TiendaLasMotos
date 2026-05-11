
import math

def calculate_payment(precio, inicial, plazo, fng_rate, registro, cov_rate=4.0, factor=0.0523336):
    monto_base = precio - inicial
    capital_inicial = monto_base + registro
    fng_cost = round(capital_inicial * (fng_rate / 100), 0)
    P_final = capital_inicial + fng_cost
    
    # Crediorbe logic
    base_aval = P_final # For CC > 124
    cov_cost = round(base_aval * (cov_rate / 100), 0)
    cuota_aval_mensual = round(cov_cost / 12, 0)
    
    cuota_mensual = round((P_final * factor) + cuota_aval_mensual, 0)
    return cuota_mensual

target = 589787
precio = 11100000
inicial = 1500000
plazo = 24

print(f"Target: {target}")

# Possible FNG rates in Crediorbe: 20.66, 11.9966, 0
for fng in [0, 11.99661, 20.66]:
    # What registration would we need?
    # cuota = (capital_inicial * (1 + fng/100) * factor) + (capital_inicial * (1 + fng/100) * cov_rate/100 / 12)
    # cuota = capital_inicial * (1 + fng/100) * (factor + cov_rate/100/12)
    # capital_inicial = cuota / ((1 + fng/100) * (factor + cov_rate/100/12))
    
    denom = (1 + fng/100) * (0.0523336 + 0.04/12)
    cap_needed = target / denom
    reg_needed = cap_needed - (precio - inicial)
    
    res = calculate_payment(precio, inicial, plazo, fng, reg_needed)
    print(f"FNG: {fng}% | Reg needed: {reg_needed:,.2f} | Result with this Reg: {res}")
