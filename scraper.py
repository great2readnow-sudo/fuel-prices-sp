import httpx
from bs4 import BeautifulSoup
import psycopg2
import os
from datetime import datetime

def get_db():
    return psycopg2.connect(os.environ["DATABASE_URL"], sslmode="require")

def scrape_and_save():
    print(f"Scraping at {datetime.now()}")

    try:
        response = httpx.get(
            "https://www.bencinaenlinea.cl/precio_regional",
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch page: {e}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.select("table tbody tr")

    if not rows:
        print("No rows found — page structure may have changed")
        return

    conn = get_db()
    cur  = conn.cursor()

    price_totals = {}
    region_data  = {}
    saved = 0

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

        # Save station
        cur.execute("""
            INSERT INTO stations (id, name, region)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        """, (station_id, name, region))

        # Save price record
        cur.execute("""
            INSERT INTO prices (station_id, fuel_type, price)
            VALUES (%s, %s, %s)
        """, (station_id, fuel_type, price))

        price_totals.setdefault(fuel_type, []).append(price)
        region_data.setdefault(region, []).append(price)
        saved += 1

    # Save national averages
    for fuel_type, prices in price_totals.items():
        cur.execute("""
            INSERT INTO averages (fuel_type, price, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (fuel_type) DO UPDATE
            SET price = EXCLUDED.price,
                updated_at = NOW()
        """, (fuel_type, int(sum(prices)/len(prices))))

    # Save region summaries
    for region, prices in region_data.items():
        cur.execute("""
            INSERT INTO regions (region, min_price, avg_price, station_count, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (region) DO UPDATE
            SET min_price     = EXCLUDED.min_price,
                avg_price     = EXCLUDED.avg_price,
                station_count = EXCLUDED.station_count,
                updated_at    = NOW()
        """, (region, min(prices), int(sum(prices)/len(prices)), len(prices)))

    conn.commit()
    cur.close()
    conn.close()
    print(f"Done — {saved} records, {len(price_totals)} fuel types, {len(region_data)} regions")

scrape_and_save()
