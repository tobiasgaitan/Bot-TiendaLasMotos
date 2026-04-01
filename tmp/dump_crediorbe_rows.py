import firebase_admin
from firebase_admin import credentials, firestore

if not firebase_admin._apps:
    import json
    # Use a dummy init if we are logged in with default credentials or we can just use the credentials path
    # Actually, simpler:
    cred = credentials.Certificate("firebase-key.json") if __import__('os').path.exists("firebase-key.json") else None
    if cred:
        firebase_admin.initialize_app(cred)
    else:
        firebase_admin.initialize_app()

db = firestore.client()
doc = db.collection('financial_config').document('general').collection('financieras').document('crediorbe').get()
if doc.exists:
    d = doc.to_dict()
    print("FNG:", d.get("fngRate"))
    print("Manejo Brilla:", d.get("brillaManagementRate"))
    print("Cobertura:", d.get("coverageRate"))
    print("Seguro:", d.get("life_insurance_monthly"))
    print("Registro GC:", d.get("registro"))
    
    # Busca la fila de 110cc
    rows = d.get("rows", [])
    for r in rows:
        minc = r.get("minCC", 0)
        maxc = r.get("maxCC", 9999)
        if minc <= 109.7 <= maxc:
            print("MATCHED ROW:", r)
