import asyncio
from google.cloud import firestore
import json

async def find_moto():
    db = firestore.Client(project='tiendalasmotos')
    docs = db.collection("productos").where("name", ">=", "Apache 160").where("name", "<=", "Apache 160\uf8ff").get()
    results = []
    for doc in docs:
        results.append(doc.to_dict())
    print(json.dumps(results, indent=2))

if __name__ == '__main__':
    asyncio.run(find_moto())
