import pandas as pd
import requests
import time
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_FILE = BASE_DIR / "data" / "companies_clean.csv"
OUTPUT_FILE = BASE_DIR / "data" / "github_activity.csv"

df = pd.read_csv(INPUT_FILE)

print(f"Companies loaded: {len(df)}")

session = requests.Session()

session.headers.update({
    "Accept": "application/vnd.github+json",
    "User-Agent": "TechDisruptionIndex"
})


def normalize(name):
    name = str(name).lower()
    name = re.sub(r"[^a-z0-9]+", " ", name)
    return name.strip()


def find_github_org(company_name):
    query = normalize(company_name)

    url = "https://api.github.com/search/users"

    params = {
        "q": f"{query} type:org",
        "per_page": 5
    }

    try:
        response = session.get(
            url,
            params=params,
            timeout=20
        )

        if response.status_code == 403:
            print("GitHub rate limit reached.")
            return None

        response.raise_for_status()

        items = response.json().get("items", [])

        if not items:
            return None

        # First candidate for MVP
        return items[0]["login"]

    except Exception as e:
        print(f"Error for {company_name}: {e}")
        return None


def get_repositories(org):

    url = f"https://api.github.com/orgs/{org}/repos"

    params = {
        "type": "public",
        "per_page": 100,
        "page": 1
    }

    repositories = []

    while True:

        response = session.get(
            url,
            params=params,
            timeout=20
        )

        if response.status_code == 404:
            return []

        if response.status_code == 403:
            print("GitHub rate limit reached.")
            return []

        response.raise_for_status()

        data = response.json()

        if not data:
            break

        repositories.extend(data)

        if len(data) < 100:
            break

        params["page"] += 1

        # Avoid extremely large organizations dominating runtime
        if params["page"] > 10:
            break

        time.sleep(0.1)

    return repositories


results = []

for index, row in df.iterrows():

    company = row["company_name"]

    print(
        f"[{index + 1}/{len(df)}] {company}"
    )

    org = find_github_org(company)

    if org is None:

        results.append({
            "company_id": row["company_id"],
            "company": company,
            "ticker": row["ticker"],
            "github_org": None,
            "repositories": 0,
            "active_repositories": 0,
            "total_stars": 0,
            "total_forks": 0
        })

        continue

    repos = get_repositories(org)

    total_stars = sum(
        repo.get("stargazers_count", 0)
        for repo in repos
    )

    total_forks = sum(
        repo.get("forks_count", 0)
        for repo in repos
    )

    active_repositories = sum(
        not repo.get("archived", False)
        for repo in repos
    )

    results.append({
        "company_id": row["company_id"],
        "company": company,
        "ticker": row["ticker"],
        "github_org": org,
        "repositories": len(repos),
        "active_repositories": active_repositories,
        "total_stars": total_stars,
        "total_forks": total_forks
    })

    # Save progress every 100 companies
    if (index + 1) % 100 == 0:

        pd.DataFrame(results).to_csv(
            OUTPUT_FILE,
            index=False
        )

        print("Progress saved.")

    time.sleep(0.2)


result_df = pd.DataFrame(results)

result_df.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\nDONE")
print(f"Companies processed: {len(result_df)}")
print(f"GitHub matches: {result_df['github_org'].notna().sum()}")
print(f"Saved to: {OUTPUT_FILE}")