import logging
import sys
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

from google.cloud import firestore
from app.services.catalog_service import catalog_service

db = firestore.Client()
catalog_service.initialize(db)

res = catalog_service.search_catalog("Tienen la Boxer")
for r in res:
    print(r["name"], r["price"], r["searchBy"], r.get("raw_price"))
