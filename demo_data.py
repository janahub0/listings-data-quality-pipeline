# Makes a FAKE messy listings file in the Inside Airbnb format, only to test that the pipeline runs.
# It has problems added on purpose (missing prices, wrong coordinates, duplicate ids, odd names).
# Never use numbers from demo mode anywhere.
import os

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
os.makedirs("data_demo", exist_ok=True)
n = 2000
hoods = ["Beyoglu", "Sisli", "Kadikoy", "Fatih", "Besiktas", "Uskudar", "Sariyer", "Beylikduzu"]
rooms = ["Entire home/apt", "Private room", "Shared room", "Hotel room"]
d = pd.DataFrame({
    "id": np.arange(1, n + 1),
    "neighbourhood_cleansed": rng.choice(hoods, n),
    "room_type": rng.choice(rooms, n, p=[0.7, 0.2, 0.03, 0.07]),
    "accommodates": rng.integers(1, 9, n),
    "bedrooms": rng.integers(1, 5, n).astype(float),
    "beds": rng.integers(1, 6, n).astype(float),
    "latitude": 41.0 + rng.normal(0, 0.05, n),
    "longitude": 29.0 + rng.normal(0, 0.08, n),
    "review_scores_rating": np.round(rng.uniform(3.5, 5.0, n), 2),
    "amenities": ['["Wifi", "Kitchen", "TV", "Heating"]'] * n,
})
d["price"] = ["₺" + f"{p:,.2f}" for p in (400 + 250 * d["accommodates"]) * rng.lognormal(0, 0.3, n)]

# problems added on purpose
d.loc[rng.choice(n, 40, replace=False), "price"] = None
d.loc[rng.choice(n, 15, replace=False), "price"] = "₺0.00"
d.loc[rng.choice(n, 10, replace=False), "latitude"] = 48.1
d.loc[rng.choice(n, 10, replace=False), "longitude"] = 10.5
d.loc[rng.choice(n, 12, replace=False), "room_type"] = "Castle"
d.loc[rng.choice(n, 20, replace=False), "accommodates"] = 0
d.loc[rng.choice(n, 8, replace=False), "bedrooms"] = 99.0
d.loc[rng.choice(n, 30, replace=False), "neighbourhood_cleansed"] = " Kadikoy  "
d.loc[rng.choice(n, 5, replace=False), "neighbourhood_cleansed"] = "Atlantis"
d = pd.concat([d, d.sample(25, random_state=1)])      # 25 duplicate ids
d.to_csv("data_demo/listings.csv.gz", index=False)
print("made data_demo/listings.csv.gz (FAKE messy data)")
