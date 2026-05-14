import httpx
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
from datetime import datetime

# Load credentials from GitHub secret
key_data = json.loads(os.environ["FIREBASE_KEY"])
cred = credentials.Certificate(key_data)
firebase_admin.initialize_app(cred)
db = firestore.client()

def scrape_and_save():
    print(f"Scraping at {datetime.now()}")

    response = httpx.get(
        "https://www.bencinaenlinea.cl/precio_regional",
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.select("table tbody tr")

    if not rows:
        print("No rows found — page may have changed")
        return

    price_totals = {}   # {fuel_type: [prices]}
    region_data  = {}   # {region: [prices]}
    saved = 0

    # Use batches — Firestore max 500 writes per batch
    batch = db.batch()
    batch_count = 0

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        name      = cells[0].text.strip()
        region    = cells[1].text.strip()
        fuel_type = cells[2].text.strip()
        raw_price = cells[3].text.strip().replace(".", "").replace("$","").replace(" ","")

        try:
            price = int(raw_price)
        except ValueError:
            continue

        station_id = name.lower().replace(" ", "-").replace("/", "-")

        # Save station doc (merge so it doesn't overwrite)
        station_ref = db.collection("stations").document(station_id)
        batch.set(station_ref, {
            "name":   name,
            "region": region,
        }, merge=True)

        # Save price record with timestamp
        price_ref = db.collection("prices").document()
        batch.set(price_ref, {
            "station_id": station_id,
            "fuel_type":  fuel_type,
            "price":      price,
            "scraped_at": datetime.now()
        })

        batch_count += 2  # 2 writes per row
        saved += 1

        price_totals.setdefault(fuel_type, []).append(price)
        region_data.setdefault(region, []).append(price)

        # Commit and start new batch every 400 writes
        if batch_count >= 400:
            batch.commit()
            batch = db.batch()
            batch_count = 0
            print(f"Batch committed at {saved} stations...")

    # Save national averages
    for fuel_type, prices in price_totals.items():
        avg_ref = db.collection("averages").document(fuel_type)
        batch.set(avg_ref, {
            "fuel_type":  fuel_type,
            "price":      int(sum(prices) / len(prices)),
            "updated_at": datetime.now()
        })
        batch_count += 1

    # Save region summaries
    for region, prices in region_data.items():
        region_slug = region.lower().replace(" ", "-")
        region_ref  = db.collection("regions").document(region_slug)
        batch.set(region_ref, {
            "region":         region,
            "min_price":      min(prices),
            "avg_price":      int(sum(prices) / len(prices)),
            "station_count":  len(prices),
            "updated_at":     datetime.now()
        })
        batch_count += 1

    # Commit remaining writes
    if batch_count > 0:
        batch.commit()

    print(f"Done — {saved} stations, {len(price_totals)} fuel types, {len(region_data)} regions")

scrape_and_save()
