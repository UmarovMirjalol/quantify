import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]

INPUT_FILE = BASE_DIR / "data" / "startups" / "startups_raw.csv"

print("Looking for:", INPUT_FILE)

df = pd.read_csv(INPUT_FILE)

print("Rows:", len(df))

print("\nColumns:")
print(df.columns.tolist())

print("\nFirst 5 rows:")
print(df.head().to_string())