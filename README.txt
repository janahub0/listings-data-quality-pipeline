Listings data quality pipeline (Python, SQL, Pydantic)

What this is
A small practice project: a pipeline that loads the public Inside Airbnb listings file for Istanbul, cleans and maps
the messy columns, checks every row against written rules, and produces a clean table, a list of rejected rows with
the reason, and a short data quality report. It is a practice project on public data, not any company's data.

Data
Public Inside Airbnb file for Istanbul: listings.csv.gz (the detailed one). Download it yourself from
https://insideairbnb.com/get-the-data/ and put it in the data folder. Do not unzip it. Check the licence on the
site and credit Inside Airbnb. Do not upload the data file to GitHub (the .gitignore skips it).
Snapshot date: 28 to 29 September 2026 (the last_scraped column in the file).

How to run
  pip install -r requirements.txt
  python pipeline.py
  python -m pytest tests
The results appear in the output folder: listings_clean.csv, rejected_rows.csv, neighbourhood_map.csv, quality_report.txt.
To test the code first on FAKE messy data: python demo_data.py, then python pipeline.py --demo.
Never use numbers from demo mode.

What the pipeline does
1 Load: DuckDB reads the file with every column as text, so nothing is converted by accident.
2 Clean and map: prices like "₺1,569.00" become numbers, the amenities list is counted, neighbourhood names written
  without Turkish letters are mapped to the proper spelling (a table of every change is saved), impossible bedrooms
  or beds are set to empty and counted.
3 Validate: every row goes through a Pydantic model (rules.py). A row is rejected if it has no valid price,
  a price at or below 0 or above 1,000,000, guests outside 1 to 50, coordinates outside a box around Istanbul,
  an unknown room type, or a duplicate listing id (the first one is kept).
4 Report: counts of rows kept and rejected, the reasons, the fixes, empty values before and after, and the
  neighbourhood names that were not in the district list (kept as they are, to check by hand).
Price outliers (below the 1st or above the 99th percentile) are flagged in the clean table, not removed.

Files
rules.py        the cleaning functions and the validation model
pipeline.py     the four steps
tests/          pytest tests for the rules
demo_data.py    makes fake messy data for testing only

Limits
- The rules are my own choices (price range, the Istanbul box, allowed room types). A rejected row broke a rule,
  that does not prove the data is wrong.
- The district list is the Istanbul districts I know of. Names not on it are kept and reported, not guessed.
- It checks the columns listed in the report. It does not check descriptions, photos or host data.
- One snapshot, one city. No claim about how it behaves on other files.
