import sqlite3
import random 
from datetime import datetime, timedelta 

def init_db():
    conn = sqlite3.connect("data/food_equity.db") #connection to our database, opneed one since it does not already exist 
    cursor = conn.cursor() #cursor tracks where we are inside the database(state trackker)
    cursor.execute("pragma foreign_keys = ON;")

    cursor.execute("DROP TABLE IF EXISTS distributions;")
    cursor.execute("DROP TABLE IF EXISTS shipments;")
    cursor.execute("DROP TABLE IF EXISTS pantries;")
    
    cursor.execute("""                  
    CREATE TABLE IF NOT EXISTS pantries(
    pantry_id TEXT PRIMARY KEY , 
    pantry_name TEXT NOT NULL,  
    neighborhood_zone TEXT NOT NULL,
    max_storage_capacity_lbs INTEGER NOT NULL);
    """)

    cursor.execute(""" 
    CREATE TABLE IF NOT EXISTS shipments(
    shipment_id INTEGER PRIMARY KEY AUTOINCREMENT, 
    pantry_id TEXT NOT NULL,  
    arrival_date TEXT NOT NULL,
    food_category TEXT NOT NULL,
    weight_received_lbs REAL NOT NULL,
    FOREIGN KEY (pantry_id) REFERENCES pantries (pantry_id));
    """)

    cursor.execute(""" 
    CREATE TABLE IF NOT EXISTS distributions(
    distribution_id INTEGER PRIMARY KEY AUTOINCREMENT, 
    pantry_id TEXT NOT NULL,  
    service_date TEXT NOT NULL,
    food_category TEXT NOT NULL,
    households_served INTEGER NOT NULL,
    weight_distributed_lbs REAL NOT NULL,
    FOREIGN KEY (pantry_id) REFERENCES pantries (pantry_id));
    """) #create 3 tables 

    conn.commit()
    return conn


def populate_data(conn):
    cursor = conn.cursor()
    random.seed(42)
    pantries = [('P01', 'The Common Hearth Food Center', 'South', 25000), 
                ('P02', 'East Ward Food Relief', 'East', 18000), 
                ('P03', 'Westside Community Hub', 'West', 22000),
                ('P04', 'North Star Pantry', 'North', 16000),
                ('P05', 'Metro Central Distribution', 'Downtown', 35000),
                ('P06', 'North Valley Food Hub', 'North', 21000),
                ('P07', 'Eastside Community Table', 'East', 17500),
                ('P08', 'West End Nourish Network', 'West', 29000)
                ]
    cursor.executemany("INSERT OR REPLACE INTO pantries VALUES (?, ?, ?, ?);", pantries)
    categories = ["Produce", "Shelf-Stable", "Dairy", "Protein"]
    start_date = datetime(2025, 9, 1)
    total_days = 365

    for day_off in range(total_days):
        current_date = start_date + timedelta(days=day_off)
        date_str = current_date.strftime("%Y-%m-%d")
        day_of_month = current_date.day 

        surge_multiplier = 1.4 if day_of_month >= 24 else 1.0

        for pantry_id, name, zone, capacity in pantries:
            for category in categories:
                base_households = random.randint(35, 70) if "Central" in name else random.randint(15, 35)
                households = int(base_households * surge_multiplier)
        
                avg_lbs = random.uniform(18.0, 32.0)
                weight_out = round(households * avg_lbs, 2)
        
                cursor.execute("""
                    INSERT INTO distributions (pantry_id, service_date, food_category, households_served, weight_distributed_lbs)
                    VALUES (?, ?, ?, ?, ?);
                """, (pantry_id, date_str, category, households, weight_out))

            # Shipments check runs per pantry, outside the category loop
            if random.random() < 0.45:
                category = random.choice(categories)
                weight_in = round(random.uniform(9000.0, 13000.0), 2)
                cursor.execute("""
                    INSERT INTO shipments (pantry_id, arrival_date, food_category, weight_received_lbs)
                    VALUES (?, ?, ?, ?);
                """, (pantry_id, date_str, category, weight_in))

    conn.commit()
    print("Database populated successfully.")


if __name__ == "__main__":
    conn = init_db()
    populate_data(conn)
    conn.close()