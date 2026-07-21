import asyncio
from google.cloud import firestore
import json

async def dump_matrix():
    db = firestore.Client(project='tiendalasmotos')
    doc = db.collection("financial_config").document("general").collection("financieras").document("crediorbe").get()
    if doc.exists:
        data = doc.to_dict()
        print(json.dumps(data, indent=2))
    else:
        print("Crediorbe doc not found at financial_config/general/financieras/crediorbe")

if __name__ == '__main__':
    asyncio.run(dump_matrix())
