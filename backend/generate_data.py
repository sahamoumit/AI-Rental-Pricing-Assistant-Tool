"""Generate synthetic datasets for the AI Rental Pricing Assistant prototype.

Writes properties.csv, rental_history.csv, and analyst_feedback.csv into
./backend/data. Run from the backend directory:

    cd backend
    python generate_data.py
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

# ---------- Config ----------
SEED = 42
NUM_PROPERTIES = 100
NUM_RENTAL_HISTORY = 300
NUM_FEEDBACK = 50

DATA_DIR = Path(__file__).parent / "data"

# Seed every RNG so runs are reproducible
fake = Faker("en_IN")
Faker.seed(SEED)
random.seed(SEED)
np.random.seed(SEED)


# ---------- Domain constants ----------
# Pune localities: (approx latitude center, longitude center, rent multiplier)
# The multiplier lets premium areas like Koregaon Park price higher than Hadapsar.
LOCALITIES = {
    "Balewadi":      (18.5760, 73.7770, 1.10),
    "Baner":         (18.5590, 73.7810, 1.15),
    "Wakad":         (18.5980, 73.7620, 1.05),
    "Hinjewadi":     (18.5910, 73.7380, 1.00),
    "Aundh":         (18.5590, 73.8080, 1.20),
    "Kharadi":       (18.5510, 73.9430, 1.15),
    "Viman Nagar":   (18.5670, 73.9140, 1.25),
    "Kothrud":       (18.5070, 73.8080, 1.10),
    "Hadapsar":      (18.5090, 73.9260, 0.95),
    "Magarpatta":    (18.5150, 73.9260, 1.20),
    "Koregaon Park": (18.5360, 73.8930, 1.35),
    "Shivaji Nagar": (18.5310, 73.8470, 1.05),
}

PROPERTY_TYPES = ["Apartment", "Villa", "Studio", "Penthouse"]
FURNISHING = ["Furnished", "Semi-Furnished", "Unfurnished"]
FLOOD_RISK = ["Low", "Medium", "High"]
ROAD_NOISE = ["Low", "Medium", "High"]
OCCUPANCY_STATUS = ["Occupied", "Vacant"]
TENANT_TYPES = ["Family", "Bachelor", "Corporate"]

NAME_PREFIXES = [
    "Maple", "Willow", "Cedar", "Oak", "Pine", "Birch", "Elm",
    "Skyline", "Sunrise", "Silver", "Green", "Royal", "Emerald",
    "Riverside", "Hilltop",
]
NAME_SUFFIXES = [
    "Residency", "Heights", "Court", "Enclave", "Towers",
    "Grove", "Vista", "Meadows", "Palms", "Habitat",
]

FEEDBACK_COMMENTS = [
    "Ignore highway-facing apartments.",
    "School quality should have higher weight.",
    "Remove this comparable due to recent renovation.",
    "Flood-prone properties should receive a discount.",
    "Metro proximity is underweighted in the model.",
    "Vacancy trend suggests rent is too high.",
    "Amenities like pool are over-valued in this locality.",
    "Recent lease shows a 10% jump — factor this in.",
    "Ground-floor units should be discounted.",
    "Furnishing status not correctly reflected.",
]

ACTIONS = [
    "Comparable Removed",
    "Updated Pricing",
    "Updated Similarity",
    "Manual Override",
]


# ---------- Helpers ----------
def make_property_name(rng: random.Random) -> str:
    """Return a realistic-sounding building name plus unit label."""
    prefix = rng.choice(NAME_PREFIXES)
    suffix = rng.choice(NAME_SUFFIXES)
    unit = f"{rng.randint(1, 20)}{rng.choice('ABCD')}"
    return f"{prefix} {suffix}, Unit {unit}"


def round_to_hundred(value: float) -> int:
    """Rents feel more natural when rounded to the nearest ₹100."""
    return int(round(value / 100) * 100)


# ---------- Dataset generators ----------
def generate_properties(n: int) -> pd.DataFrame:
    """Build the properties dataset with realistic Pune-scoped attributes.

    Rent is derived from a base per-sqft rate, scaled by locality and amenity
    bonus, then depreciated for age — so the numbers stay internally consistent.
    """
    rng = random.Random(SEED)
    rows = []

    for i in range(1, n + 1):
        locality = rng.choice(list(LOCALITIES.keys()))
        lat_c, lng_c, loc_mult = LOCALITIES[locality]
        # Jitter within ~1 km of the locality center
        latitude = round(lat_c + rng.uniform(-0.009, 0.009), 6)
        longitude = round(lng_c + rng.uniform(-0.009, 0.009), 6)

        # Bedrooms drive area, which drives rent
        bedrooms = rng.choices([1, 2, 3, 4], weights=[15, 40, 35, 10])[0]
        bathrooms = max(1, bedrooms - rng.choice([0, 1]))
        area_sqft = int(np.clip(np.random.normal(450 * bedrooms + 250, 120), 350, 3500))

        total_floors = rng.randint(4, 25)
        floor = rng.randint(1, total_floors)
        year_built = rng.randint(2000, 2024)
        property_age = 2026 - year_built

        # Amenities
        gym = int(rng.random() < 0.55)
        swimming_pool = int(rng.random() < 0.35)
        lift = int(total_floors >= 4 or rng.random() < 0.9)
        parking = int(rng.random() < 0.85)
        balcony = int(rng.random() < 0.75)
        amenity_score = gym + swimming_pool + lift + parking + balcony
        amenity_bonus = 1 + 0.03 * amenity_score  # up to +15%

        # Rent = base ₹/sqft * area * locality mult * amenity bonus - age depreciation
        base_psf = rng.uniform(22, 32)
        rent = base_psf * area_sqft * loc_mult * amenity_bonus
        rent *= 1 - min(property_age, 20) * 0.005  # ~0.5% per year, capped at 20 yrs
        rent += np.random.normal(0, 1500)          # noise so comps aren't identical
        current_rent = round_to_hundred(np.clip(rent, 8000, 250000))

        # Maintenance runs ~3-8% of rent
        monthly_maintenance = round_to_hundred(current_rent * rng.uniform(0.03, 0.08))

        occupancy_status = rng.choices(OCCUPANCY_STATUS, weights=[85, 15])[0]
        vacancy_days = 0 if occupancy_status == "Occupied" else rng.randint(5, 120)

        rows.append({
            "property_id": f"P{i:04d}",
            "property_name": make_property_name(rng),
            "address": f"{fake.building_number()} {fake.street_name()}, {locality}, Pune",
            "locality": locality,
            "latitude": latitude,
            "longitude": longitude,
            "property_type": rng.choices(PROPERTY_TYPES, weights=[75, 10, 10, 5])[0],
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "area_sqft": area_sqft,
            "floor": floor,
            "total_floors": total_floors,
            "parking": parking,
            "balcony": balcony,
            "gym": gym,
            "swimming_pool": swimming_pool,
            "lift": lift,
            "property_age": property_age,
            "furnishing": rng.choice(FURNISHING),
            "monthly_maintenance": monthly_maintenance,
            "current_rent": current_rent,
            "occupancy_status": occupancy_status,
            "vacancy_days": vacancy_days,
            "school_rating": round(rng.uniform(5, 10), 1),
            "crime_index": round(rng.uniform(1, 10), 1),
            "flood_risk": rng.choices(FLOOD_RISK, weights=[70, 22, 8])[0],
            "road_noise": rng.choices(ROAD_NOISE, weights=[55, 30, 15])[0],
            "walkability_score": rng.randint(40, 100),
            "metro_distance_m": rng.randint(150, 6000),
            "park_distance_m": rng.randint(80, 3000),
            "shopping_distance_m": rng.randint(100, 4000),
            "hospital_distance_m": rng.randint(200, 5000),
            "year_built": year_built,
        })

    return pd.DataFrame(rows)


def generate_rental_history(properties: pd.DataFrame, n: int) -> pd.DataFrame:
    """Build lease history tied to real property_ids, with rent trending upward.

    Older leases are back-solved from the property's current rent using ~7%
    annual growth, so rent_increase_percent between leases stays realistic.
    """
    rng = random.Random(SEED + 1)
    property_ids = properties["property_id"].tolist()
    rent_lookup = dict(zip(properties["property_id"], properties["current_rent"]))

    rows = []
    for i in range(1, n + 1):
        pid = rng.choice(property_ids)
        current_rent = rent_lookup[pid]

        # Lease start anywhere in the 2020-01-01 to 2026-06-30 window
        window_days = (date(2026, 6, 30) - date(2020, 1, 1)).days
        lease_start = date(2020, 1, 1) + timedelta(days=rng.randint(0, window_days))
        lease_length_months = rng.choice([11, 12, 24, 36])
        lease_end = lease_start + timedelta(days=lease_length_months * 30)

        # Discount current rent backward at ~7% annual growth to get historical rent
        years_ago = (date(2026, 1, 1) - lease_start).days / 365.25
        historical_rent = current_rent / (1.07 ** years_ago)
        historical_rent *= rng.uniform(0.95, 1.05)  # small variance per tenant
        monthly_rent = round_to_hundred(historical_rent)

        rows.append({
            "history_id": f"H{i:05d}",
            "property_id": pid,
            "lease_start_date": lease_start.isoformat(),
            "lease_end_date": lease_end.isoformat(),
            "monthly_rent": monthly_rent,
            "occupancy_rate": round(rng.uniform(0.75, 1.0), 2),
            "vacancy_days": rng.randint(0, 60),
            "tenant_type": rng.choice(TENANT_TYPES),
            "rent_increase_percent": round(rng.uniform(-2.0, 12.0), 2),
        })

    return pd.DataFrame(rows)


def generate_feedback(properties: pd.DataFrame, n: int) -> pd.DataFrame:
    """Build analyst feedback rows, each linked to a valid property_id."""
    rng = random.Random(SEED + 2)
    property_ids = properties["property_id"].tolist()

    rows = []
    for i in range(1, n + 1):
        days_ago = rng.randint(0, 365)
        created_at = date(2026, 7, 1) - timedelta(days=days_ago)
        rows.append({
            "feedback_id": f"F{i:04d}",
            "property_id": rng.choice(property_ids),
            "feedback": rng.choice(FEEDBACK_COMMENTS),
            "action_taken": rng.choice(ACTIONS),
            "created_at": created_at.isoformat(),
        })

    return pd.DataFrame(rows)


# ---------- Entrypoint ----------
def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    properties = generate_properties(NUM_PROPERTIES)
    rental_history = generate_rental_history(properties, NUM_RENTAL_HISTORY)
    feedback = generate_feedback(properties, NUM_FEEDBACK)

    properties.to_csv(DATA_DIR / "properties.csv", index=False)
    rental_history.to_csv(DATA_DIR / "rental_history.csv", index=False)
    feedback.to_csv(DATA_DIR / "analyst_feedback.csv", index=False)

    print(f"Wrote {len(properties):>4} rows -> {DATA_DIR / 'properties.csv'}")
    print(f"Wrote {len(rental_history):>4} rows -> {DATA_DIR / 'rental_history.csv'}")
    print(f"Wrote {len(feedback):>4} rows -> {DATA_DIR / 'analyst_feedback.csv'}")


if __name__ == "__main__":
    main()
