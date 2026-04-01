import firebase_admin
from firebase_admin import credentials, firestore
import os

try:
    cred = credentials.Certificate("firebase-key.json") if os.path.exists("firebase-key.json") else None
    if cred: 
        firebase_admin.initialize_app(cred)
    else: 
        firebase_admin.initialize_app()
    
    db = firestore.client()
    
    print("Conectado a Firestore. Buscando motos TVS...")
    items = db.collection("pagina").document("catalogo").collection("items").where("brand", "==", "TVS").stream()
    found = False
    for i in items:
        d = i.to_dict()
        if "Neo" in d.get("name", "") or "NEO" in d.get("name", "").upper():
            found = True
            print("MOTO:", d.get("name"))
            print("PRICE:", d.get("price"))
            print("REGISTRO CREDIT GENERAL:", d.get("registrationCreditGeneral"))
            print("REGISTRO:", d.get("registration"))
    print("Done. Found?", found)
except Exception as e:
    import traceback; traceback.print_exc()
    print("Error:", e)
