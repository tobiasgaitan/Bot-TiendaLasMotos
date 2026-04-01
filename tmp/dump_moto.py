import firebase_admin
from firebase_admin import credentials, firestore
import os

cred = credentials.Certificate("firebase-key.json") if os.path.exists("firebase-key.json") else None
if cred: 
    firebase_admin.initialize_app(cred)
else: 
    firebase_admin.initialize_app()

db = firestore.client()

items = db.collection("pagina").document("catalogo").collection("items").where("brand", "==", "TVS").stream()
for i in items:
    d = i.to_dict()
    if "Neo NX" in d.get("name", "") or "NEO" in d.get("name", "").upper():
        print("MOTO:", d.get("name"))
        print("PRICE:", d.get("price"))
        print("REGISTRO:", d.get("registrationCreditGeneral"), d.get("registration"))
