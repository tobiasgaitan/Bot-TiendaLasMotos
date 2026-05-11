import asyncio
from google.cloud import firestore
import json

async def dump_global_params():
    db = firestore.Client(project='tiendalasmotos')
    doc = db.collection("financial_config").document("general").collection("global_params").document("global_params").get()
    if doc.exists:
        data = doc.to_dict()
        print(json.dumps(data, indent=2))
    else:
        print("Global params not found at financial_config/general/global_params/global_params")

if __name__ == '__main__':
    asyncio.run(dump_global_params())
