import asyncio
from google.cloud import firestore
import json

async def find_moto():
    db = firestore.Client(project='tiendalasmotos')
    docs = db.collection("productos").get()
    results = []
    for doc in docs:
        d = doc.to_dict()
        if 'Apache 160' in d.get('name', ''):
            results.append(d)
    print(json.dumps(results, indent=2))

if __name__ == '__main__':
    asyncio.run(find_moto())
