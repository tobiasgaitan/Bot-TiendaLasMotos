def calculate(registro, fng_rate, include_registro_in_aval=True):
    precio = 11100000
    inicial = 1500000
    monto_base = precio - inicial
    factor = 0.0523336
    cov_rate = 4.0
    
    capital_inicial = monto_base + registro
    fng_cost = round(capital_inicial * (fng_rate / 100), 0)
    P_final = capital_inicial + fng_cost
    
    if include_registro_in_aval:
        base_aval = P_final
    else:
        base_aval = capital_inicial
        
    cov_cost = round(base_aval * (cov_rate / 100), 0)
    cuota_aval_mensual = round(cov_cost / 12, 0)
    
    cuota_mensual = round((P_final * factor) + cuota_aval_mensual, 0)
    return cuota_mensual

target = 589787
print(f"Target: {target}")

# Try with different FNG rates and registrations
for fng in [0, 11.9966, 20.66]:
    for reg in [0, 860000]:
        for inc_reg in [True, False]:
            res = calculate(reg, fng, inc_reg)
            print(f"FNG: {fng}% | Reg: {reg} | IncRegAval: {inc_reg} | Result: {res} | Diff: {res - target}")
