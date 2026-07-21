factor = 0.0523336
target_cuota = 416647

P_final = (target_cuota - 15000) / factor
print(f"Required P_final: {P_final}")

precio = 6699999
inicial = 1004999
M = precio - inicial
print(f"Monto Base: {M}")

fng_rate = 0.2066
mgmt_rate = 0.05
cov_rate = 0.04/12

# P_final = (M + Reg) * (1 + fng_rate + mgmt_rate + (1 + fng_rate + mgmt_rate)*cov_rate)
mult = (1 + fng_rate + mgmt_rate) * (1 + cov_rate)
print(f"Multiplier: {mult}")

req_M_plus_Reg = P_final / mult
print(f"Required M + Reg: {req_M_plus_Reg}")
print(f"Required Reg: {req_M_plus_Reg - M}")
