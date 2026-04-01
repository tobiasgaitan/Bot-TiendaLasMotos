def calculate(reg):
    m = 8149999 + reg
    f = round(m * 0.2066, 0)
    base = m + f
    gm = round(base * 0.05, 0)
    av = round(base * 0.04, 0)
    p = round(base + gm + av, 0)
    return round((p * 0.0523336) + 15000, 0)

target = 589787
for r in range(0, 1000000):
    if int(calculate(r)) == target:
        print(f"MATCH_FOUND_REGISTER:{r}")
        break
