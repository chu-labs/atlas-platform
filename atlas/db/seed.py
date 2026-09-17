"""Deterministic synthetic portfolio.

Shapes are modelled on an Australian strata book (state mix, lot counts, sums insured, premium
rates, peril mix, claims frequency and severity) but every record is invented. Plan numbers use
the obviously fictional 9xxxxx range and building names are generated.
"""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from ..domain.money import cents
from ..domain.renewals import business_today
from ..settings import settings
from .pool import conn

SEED = 42

STATES = [
    ("NSW", 0.38),
    ("VIC", 0.25),
    ("QLD", 0.20),
    ("WA", 0.08),
    ("SA", 0.05),
    ("ACT", 0.02),
    ("TAS", 0.01),
    ("NT", 0.01),
]
SUBURBS = {
    "NSW": [
        ("Parramatta", "2150"),
        ("Chatswood", "2067"),
        ("Wollongong", "2500"),
        ("Newcastle", "2300"),
        ("Bondi", "2026"),
        ("Penrith", "2750"),
        ("Ryde", "2112"),
        ("Hurstville", "2220"),
        ("Manly", "2095"),
        ("Liverpool", "2170"),
    ],
    "VIC": [
        ("Docklands", "3008"),
        ("St Kilda", "3182"),
        ("Geelong", "3220"),
        ("Box Hill", "3128"),
        ("Footscray", "3011"),
        ("Frankston", "3199"),
        ("Richmond", "3121"),
        ("Dandenong", "3175"),
    ],
    "QLD": [
        ("Surfers Paradise", "4217"),
        ("South Brisbane", "4101"),
        ("Cairns", "4870"),
        ("Townsville", "4810"),
        ("Maroochydore", "4558"),
        ("Chermside", "4032"),
        ("Broadbeach", "4218"),
    ],
    "WA": [
        ("Scarborough", "6019"),
        ("Fremantle", "6160"),
        ("Joondalup", "6027"),
        ("East Perth", "6004"),
        ("Mandurah", "6210"),
    ],
    "SA": [("Glenelg", "5045"), ("Adelaide", "5000"), ("Mawson Lakes", "5095"), ("Port Adelaide", "5015")],
    "ACT": [("Belconnen", "2617"), ("Braddon", "2612"), ("Woden", "2606")],
    "TAS": [("Sandy Bay", "7005"), ("Launceston", "7250")],
    "NT": [("Darwin", "0800"), ("Palmerston", "0830")],
}
NAMES_A = [
    "Harbourview",
    "Parkside",
    "The Meridian",
    "Sandstone",
    "Riverbend",
    "Aurora",
    "Banksia",
    "Wattle",
    "Coral",
    "Lighthouse",
    "Jacaranda",
    "Seabreeze",
    "Quarry",
    "Windsor",
    "Elm",
    "Marina",
    "Summit",
    "Grange",
    "Bayside",
    "Kingsway",
]
NAMES_B = [
    "Towers",
    "Apartments",
    "Residences",
    "Court",
    "Terraces",
    "Gardens",
    "Place",
    "Heights",
    "Quays",
    "Point",
    "Lofts",
    "Square",
    "Mews",
    "Rise",
    "Park",
]
BROKER_A = [
    "Southern Cross",
    "Coastline",
    "Meridian",
    "Harbour City",
    "Bluegum",
    "Redgum",
    "Sandstone",
    "Federation",
    "Anchor",
    "Pinnacle",
    "Compass",
    "Beacon",
    "Granite",
    "Keystone",
    "Northwind",
    "Silverline",
    "Cornerstone",
    "Ironbark",
    "Lantern",
    "Summit",
]
BROKER_B = ["Insurance Brokers", "Risk Partners", "Strata Brokers", "Broking Group", "Underwriting Agencies"]
PERILS = [
    ("water_damage", 0.45),
    ("storm", 0.25),
    ("impact", 0.08),
    ("fire", 0.05),
    ("liability", 0.04),
    ("theft", 0.03),
    ("malicious", 0.03),
    ("other", 0.07),
]
DESCRIPTIONS = {
    "water_damage": [
        "Burst flexi hose in lot {n} bathroom, damage to lot below",
        "Shower waterproofing failure, lots {n} and {m}",
        "Roof membrane leak into top floor lot {n}",
        "Hot water unit failure in common area plant room",
        "Blocked stormwater riser, ground floor lobby flooded",
    ],
    "storm": [
        "Storm damage to roof sheeting and guttering",
        "Hail damage to skylights and car park roof",
        "Wind-driven rain ingress via balcony doors, lot {n}",
        "Fallen tree damaged perimeter fence and carport",
    ],
    "impact": [
        "Vehicle impact to basement car park bollards and wall",
        "Delivery truck struck awning at entry",
        "Impact damage to boom gate",
    ],
    "fire": [
        "Kitchen fire in lot {n}, smoke damage to corridor",
        "Electrical fire in switchboard, common area",
        "BBQ fire on balcony, lot {n}",
    ],
    "liability": [
        "Slip and fall on wet lobby tiles, visitor injured",
        "Trip on uneven paving in common driveway",
    ],
    "theft": ["Break-in to basement storage cages", "Theft of copper from plant room"],
    "malicious": [
        "Graffiti and glass damage to ground floor entry",
        "Vandalism to lift car and lobby mirror",
    ],
    "other": [
        "Lift breakdown, mechanical failure",
        "Glass breakage to balcony balustrade, lot {n}",
        "Electrical surge damaged fire panel",
    ],
}


def _pick(rng: random.Random, weighted):
    r = rng.random()
    acc = 0.0
    for v, w in weighted:
        acc += w
        if r <= acc:
            return v
    return weighted[-1][0]


def _lognormal(rng: random.Random, median: float, sigma: float, lo: float, hi: float) -> float:
    import math

    return max(lo, min(hi, rng.lognormvariate(math.log(median), sigma)))


def reset() -> None:
    with conn() as c:
        c.execute(
            "truncate ai_reports, renewal_quotes, claims, policies, buildings, brokers restart identity cascade"
        )


def seed(buildings: int = 2500, as_of: date | None = None) -> dict:
    rng = random.Random(SEED)
    as_of = as_of or business_today(datetime.now(UTC), settings().business_tz)
    with conn() as c:
        if c.execute("select count(*) as n from buildings").fetchone()["n"]:
            return {"skipped": "already seeded"}

        # brokers
        brokers = []
        for i in range(40):
            state = _pick(rng, STATES)
            brokers.append((f"{rng.choice(BROKER_A)} {rng.choice(BROKER_B)} ({state})", state))
        cur = c.cursor()
        cur.executemany(
            "insert into brokers(name, state) values (%s, %s) returning id", brokers, returning=True
        )
        broker_ids = []
        while True:
            broker_ids.append(cur.fetchone()["id"])
            if not cur.nextset():
                break
        brokers_by_state: dict[str, list[int]] = {}
        for bid, (_, st) in zip(broker_ids, brokers):
            brokers_by_state.setdefault(st, []).append(bid)

        # buildings
        b_rows = []
        for i in range(buildings):
            state = _pick(rng, STATES)
            suburb, postcode = rng.choice(SUBURBS[state])
            lots = int(_lognormal(rng, 18, 0.9, 2, 400))
            floors = max(1, min(45, int(lots / rng.uniform(3, 9)) + (1 if lots < 12 else 0)))
            year = int(rng.triangular(1965, 2024, 2005))
            ctype = _pick(rng, [("concrete", 0.55), ("brick", 0.30), ("mixed", 0.10), ("timber", 0.05)])
            roof = _pick(rng, [("tile", 0.35), ("metal", 0.35), ("concrete", 0.2), ("membrane", 0.1)])
            coast = _lognormal(rng, 6, 1.2, 0.1, 400)
            flood = _pick(rng, [("none", 0.82), ("low", 0.13), ("high", 0.05)])
            bal = _pick(
                rng,
                [
                    ("none", 0.80),
                    ("low", 0.10),
                    ("12.5", 0.05),
                    ("19", 0.025),
                    ("29", 0.015),
                    ("40", 0.007),
                    ("FZ", 0.003),
                ],
            )
            cladding = year >= 2000 and floors >= 4 and rng.random() < 0.06
            inspection = as_of - timedelta(days=int(rng.uniform(30, 2200))) if rng.random() < 0.9 else None
            name = f"{rng.choice(NAMES_A)} {rng.choice(NAMES_B)}"
            b_rows.append(
                (
                    f"SP 9{i + 10000:05d}",
                    name,
                    suburb,
                    state,
                    postcode,
                    year,
                    floors,
                    lots,
                    ctype,
                    roof,
                    floors > 3 and rng.random() < 0.6,
                    flood,
                    bal,
                    round(coast, 1),
                    cladding,
                    inspection,
                )
            )
        cur.executemany(
            "insert into buildings(plan_number,name,suburb,state,postcode,year_built,floors,lots,construction_type,roof_type,"
            "sprinklers,flood_zone,bushfire_bal,distance_to_coast_km,cladding_flag,last_inspection) "
            "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            b_rows,
        )
        blds = c.execute("select id, state, lots, year_built, floors from buildings order by id").fetchall()

        # policies: one active per building, plus expired history for ~60%
        p_rows = []
        pn = 100000
        for b in blds:
            product = "commercial_strata" if rng.random() < 0.12 else "residential_strata"
            per_lot = _lognormal(
                rng, 520_000 if product == "residential_strata" else 700_000, 0.45, 180_000, 3_000_000
            )
            si = cents(Decimal(int(per_lot * b["lots"] / 1000) * 1000))
            rate = Decimal(str(round(rng.uniform(0.0019, 0.0034), 6)))
            premium = max(cents(si * rate), Decimal("1500.00"))
            expiry = as_of + timedelta(days=int(rng.uniform(-20, 365)))
            broker = rng.choice(brokers_by_state.get(b["state"]) or broker_ids)
            status = "active" if expiry >= as_of - timedelta(days=0) else "lapsed"
            if status == "lapsed" and rng.random() < 0.7:
                expiry = as_of + timedelta(days=int(rng.uniform(1, 365)))
                status = "active"
            p_rows.append(
                (
                    f"ATL-{pn}",
                    b["id"],
                    broker,
                    product,
                    expiry - timedelta(days=365),
                    expiry,
                    si,
                    premium,
                    status,
                )
            )
            pn += 1
            for k in range(rng.choice([0, 0, 1, 2, 3])):
                e = expiry - timedelta(days=365 * (k + 1))
                p_rows.append(
                    (
                        f"ATL-{pn}",
                        b["id"],
                        broker,
                        product,
                        e - timedelta(days=365),
                        e,
                        si,
                        cents(premium * Decimal(str(round(rng.uniform(0.85, 0.97), 3)))),
                        "lapsed",
                    )
                )
                pn += 1
        cur.executemany(
            "insert into policies(policy_number,building_id,broker_id,product,inception_date,expiry_date,sum_insured,base_premium,status) "
            "values (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            p_rows,
        )
        pols = c.execute(
            "select id, building_id, inception_date, expiry_date from policies order by id"
        ).fetchall()
        pol_by_building: dict[int, list] = {}
        for p in pols:
            pol_by_building.setdefault(p["building_id"], []).append(p)

        # claims: ~0.35 per lot-decade, heavier in older / wetter buildings
        c_rows = []
        cn = 500000
        for b in blds:
            age = as_of.year - b["year_built"]
            expected = b["lots"] * 6 * (0.03 + 0.0006 * age) * rng.uniform(0.4, 1.8)
            n = min(int(rng.expovariate(1 / max(expected, 0.2))), 120)
            for _ in range(n):
                loss = as_of - timedelta(days=int(rng.uniform(1, 6 * 365)))
                peril = _pick(rng, PERILS)
                median = {
                    "water_damage": 6000,
                    "storm": 9000,
                    "impact": 7000,
                    "fire": 45000,
                    "liability": 20000,
                    "theft": 3500,
                    "malicious": 2500,
                    "other": 5000,
                }[peril]
                incurred = cents(Decimal(int(_lognormal(rng, median, 1.0, 400, 900_000))))
                status = (
                    "open"
                    if (as_of - loss).days < 120 and rng.random() < 0.6
                    else ("declined" if rng.random() < 0.06 else "closed")
                )
                paid = (
                    Decimal("0.00")
                    if status != "closed"
                    else cents(incurred * Decimal(str(round(rng.uniform(0.85, 1.0), 3))))
                )
                cands = [
                    p for p in pol_by_building[b["id"]] if p["inception_date"] <= loss <= p["expiry_date"]
                ] or pol_by_building[b["id"]]
                pol = rng.choice(cands)
                desc = rng.choice(DESCRIPTIONS[peril]).format(
                    n=rng.randint(1, b["lots"]), m=rng.randint(1, b["lots"])
                )
                c_rows.append(
                    (
                        f"CLM-{cn}",
                        pol["id"],
                        b["id"],
                        loss,
                        loss + timedelta(days=int(rng.uniform(0, 21))),
                        peril,
                        status,
                        incurred,
                        paid,
                        desc,
                    )
                )
                cn += 1
        cur.executemany(
            "insert into claims(claim_number,policy_id,building_id,loss_date,reported_date,peril,status,incurred,paid,description) "
            "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            c_rows,
        )
        return {
            "brokers": len(brokers),
            "buildings": len(b_rows),
            "policies": len(p_rows),
            "claims": len(c_rows),
        }
