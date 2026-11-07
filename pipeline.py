# Data quality pipeline for the Inside Airbnb Istanbul listings file.
# Steps: 1 load  2 clean and map  3 validate every row  4 write clean table, rejected rows and a report.
# Run:  python pipeline.py             (needs data/listings.csv.gz)
#       python pipeline.py --demo      (FAKE messy data, only to test that the code runs)
import os
import sys

import duckdb
import pandas as pd
from pydantic import ValidationError

from rules import Listing, count_amenities, normalize_neighbourhood, parse_price

DEMO = "--demo" in sys.argv
LISTINGS = "data_demo/listings.csv.gz" if DEMO else "data/listings.csv.gz"
OUT = "output_demo" if DEMO else "output"
if DEMO:
    print("*** DEMO MODE: made-up messy data, the numbers mean nothing ***")
if not os.path.exists(LISTINGS):
    print("Missing file:", LISTINGS)
    print("Download listings.csv.gz for Istanbul from https://insideairbnb.com/get-the-data/ and put it in the data folder.")
    print("(Or run python demo_data.py first and use --demo.)")
    raise SystemExit(1)
os.makedirs(OUT, exist_ok=True)

# ---- 1. load everything as text, nothing is converted yet ----
con = duckdb.connect()
con.execute(f"CREATE TABLE raw AS SELECT * FROM read_csv_auto('{LISTINGS}', all_varchar=true)")
raw = con.execute("SELECT * FROM raw").fetchdf()
con.close()
n_raw = len(raw)
print("rows loaded:", n_raw)

wanted = ["id", "neighbourhood_cleansed", "room_type", "price", "accommodates", "bedrooms", "beds",
          "latitude", "longitude", "review_scores_rating", "amenities"]
missing_cols = [c for c in wanted if c not in raw.columns]
if missing_cols:
    print("columns not in this file (treated as empty):", missing_cols)
    for c in missing_cols:
        raw[c] = None
raw = raw.replace({"": None})

# share of empty values per column before cleaning
missing_before = raw[wanted].isna().mean().round(3)

# ---- 2. clean and map ----
def to_number(series):
    return pd.to_numeric(series, errors="coerce")

df = pd.DataFrame({
    "listing_id": to_number(raw["id"]),
    "neighbourhood_raw": raw["neighbourhood_cleansed"],
    "room_type": raw["room_type"].str.strip(),
    "price": raw["price"].map(parse_price),
    "accommodates": to_number(raw["accommodates"]),
    "bedrooms": to_number(raw["bedrooms"]),
    "beds": to_number(raw["beds"]),
    "latitude": to_number(raw["latitude"]),
    "longitude": to_number(raw["longitude"]),
    "review_score": to_number(raw["review_scores_rating"]),
    "amenities_n": raw["amenities"].map(count_amenities),
})
mapped = df["neighbourhood_raw"].map(normalize_neighbourhood)
df["neighbourhood"] = mapped.map(lambda t: t[0])
df["neighbourhood_in_list"] = mapped.map(lambda t: t[1])

# the mapping table, so every change can be checked
nmap = (df.assign(changed=df["neighbourhood_raw"].fillna("") != df["neighbourhood"].fillna(""))
          .groupby(["neighbourhood_raw", "neighbourhood", "neighbourhood_in_list"], dropna=False)
          .size().reset_index(name="rows").sort_values("rows", ascending=False))
nmap.to_csv(f"{OUT}/neighbourhood_map.csv", index=False)
unmapped = nmap[~nmap["neighbourhood_in_list"] & nmap["neighbourhood_raw"].notna()]

# duplicates: keep the first row of each listing id, reject the later ones
df["row_number"] = range(1, len(df) + 1)
dup_mask = df["listing_id"].notna() & df.duplicated("listing_id", keep="first")

# fixes that are logged, not rejected: impossible bedrooms or beds become empty
fixes = {}
for col in ["bedrooms", "beds"]:
    bad = df[col].notna() & ((df[col] < 0) | (df[col] > 50))
    fixes[f"{col} outside 0 to 50 set to empty"] = int(bad.sum())
    df.loc[bad, col] = None

# ---- 3. validate every row with the Pydantic model ----
good, rejected = [], []
for rec in df.to_dict("records"):
    if rec["row_number"] and dup_mask.iloc[rec["row_number"] - 1]:
        rejected.append({"row_number": rec["row_number"], "listing_id": rec["listing_id"], "reason": "duplicate listing id"})
        continue
    row = {k: (None if pd.isna(v) else v) for k, v in rec.items()}
    try:
        for k in ("listing_id", "accommodates"):
            if row[k] is not None:
                row[k] = int(row[k])
        obj = Listing(**{k: row[k] for k in Listing.model_fields if k in row})
        clean = obj.model_dump()
        clean["amenities_n"] = row["amenities_n"]
        good.append(clean)
    except (ValidationError, TypeError, ValueError) as e:
        if isinstance(e, ValidationError):
            reason = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())
            if row.get("price") is None and reason.startswith("price:"):
                reason = "price: missing (empty in the raw file)"
        else:
            reason = str(e)
        rejected.append({"row_number": rec["row_number"], "listing_id": rec["listing_id"], "reason": reason})

clean_df = pd.DataFrame(good)
rej_df = pd.DataFrame(rejected, columns=["row_number", "listing_id", "reason"])

# price outliers are only flagged (1st and 99th percentile of the clean rows), not removed
lo, hi = clean_df["price"].quantile([0.01, 0.99])
clean_df["price_outlier_flag"] = ((clean_df["price"] < lo) | (clean_df["price"] > hi)).astype(int)

clean_df.to_csv(f"{OUT}/listings_clean.csv", index=False)
rej_df.to_csv(f"{OUT}/rejected_rows.csv", index=False)

# ---- 4. report ----
# group reasons by the first rule broken, so the counts are easy to read
reason_counts = rej_df["reason"].map(lambda r: r.split(";")[0].strip()).value_counts()

missing_after = clean_df[["neighbourhood", "price", "accommodates", "bedrooms", "beds", "latitude", "longitude", "review_score"]].isna().mean().round(3)

lines = []
def log(text=""):
    lines.append(text)
    print(text)

log("Data quality report")
log(f"Source file: {LISTINGS}")
log(f"Rows loaded: {n_raw}")
log(f"Rows kept: {len(clean_df)} ({len(clean_df) / n_raw:.1%})")
log(f"Rows rejected: {len(rej_df)} ({len(rej_df) / n_raw:.1%}), see rejected_rows.csv")
log()
log("Why rows were rejected (first rule broken, one count per row):")
log(reason_counts.to_string() if len(reason_counts) else "  none")
log()
log("Fixes made without rejecting the row:")
for k, v in fixes.items():
    log(f"  {k}: {v}")
log(f"  price outliers flagged, not removed (below {lo:.0f} or above {hi:.0f}): {int(clean_df['price_outlier_flag'].sum())}")
log()
log("Share of empty values before cleaning (raw file):")
log(missing_before.to_string())
log()
log("Share of empty values after cleaning (kept rows):")
log(missing_after.to_string())
log()
log(f"Neighbourhood names mapped to proper Turkish spelling: {int(nmap.loc[nmap['neighbourhood_in_list'], 'rows'].sum())} rows")
if len(unmapped):
    log("Names not in the district list, kept as they are (check them by hand):")
    log(unmapped[["neighbourhood_raw", "rows"]].to_string(index=False))
else:
    log("Every neighbourhood name was found in the district list.")
log()
log("Limits: the rules (price range, Istanbul bounding box, room types) are my own choices. A rejected row is not")
log("necessarily wrong data, it only broke a rule. The district list covers the Istanbul districts I know of.")
open(f"{OUT}/quality_report.txt", "w", encoding="utf-8").write("\n".join(lines) + "\n")
print()
print("saved:", ", ".join(os.listdir(OUT)))