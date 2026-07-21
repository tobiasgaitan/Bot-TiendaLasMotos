def calculate(reg):
    precio = 9649999
    inicial = 1500000
    monto_base = precio - inicial
    factor = 0.0523336
    seguro = 15000
    fng_rate = 20.66
    mgmt_rate = 5
    cov_rate = 4
    
    cap_inicial = round(monto_base + reg, 0)
    fng_cost = round(cap_inicial * (fng_rate / 100), 0)
    mgmt_cost = round((cap_inicial + fng_cost) * (mgmt_rate / 100), 0)
    cov_cost = round((cap_inicial + fng_cost) * (cov_rate / 100), 0)
    
    P_final = round(cap_inicial + fng_cost + mgmt_cost + cov_cost, 0)
    cuota = round((P_final * factor) + seguro, 0)
    return cuota

target = 589787
for r in range(0, 1000000, 100):
    if calculate(r) >= target:
        print(f"VALOR DE REGISTRO ENCONTRADO: {r} | CUOTA: {calculate(r)}")
        break
