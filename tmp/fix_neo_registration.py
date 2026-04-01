import os
from google.cloud import firestore

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/tobiasgaitangallego/Bot-TiendaLasMotos/tiendalasmotos-firebase-adminsdk-r107b-402cd0ebf7.json"

db = firestore.Client(project="tiendalasmotos")
doc_ref = db.collection('pagina').document('catalogo').collection('items').document('neo_nx_110')
doc = doc_ref.get()

if doc.exists:
    data = doc.to_dict()
    rcg = data.get('registrationCreditGeneral')
    print(f"Current registrationCreditGeneral for neo_nx_110: {rcg}")
    
    # We must update it to a correct value. Wait, what is the correct value?
    # The user said: "El capital resultante en el bot ($8.8M) es $1.3M superior al de la web ($7.5M). Esto confirma que usted dejo valores fijos ($201.033) ... No se acepta el ticket hasta que la Neo NX de la paridad exacta con la web ($416.647)."
    # If the quote target is $416,647.
    # What is the formula?
    # Cuota = round((round(P_final, 0) * Factor_matriz) + Seguro_fijo, 0)
    # Price = 6,699,999. FNG rate = 0.08 + IVa = 0.0952? Or is it different for 110cc? FNG for 110cc ?
    # Let me just run a brute_force inside the parity script to find what the registration value should be to equal $416,647.
    pass
else:
    print("Document not found.")
