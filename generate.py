#!/usr/bin/env python3
"""
Generate the README + forkable dataset for the public h1b-sponsors-by-state repo
from the FlexApply shortlist aggregate (h1b-shortlist/data.json).

Lazy by design: no live fetching. It reshapes the same per-company worksite data
that already powers flexapply.org/sponsors/location/<state>/ into a GitHub-native
dataset + README, with every state linking back to its live location page and every
top sponsor linking to its company page. Run after each quarterly refresh.

    python3 generate.py
"""
import csv
import json
import datetime
import os
import re
from collections import defaultdict
from pathlib import Path

SITE = "https://flexapply.org"
FLEX = Path.home() / "flexapply"
SRC = FLEX / "tools/h1b-shortlist/data.json"
SUMMARY = FLEX / "tools/sponsor-data/out/summary.json"
HERE = Path(__file__).parent
FY = "FY2025"  # ponytail: single source, bump when the pipeline moves to a new DOL year

# live pages we are allowed to link to (never link a 404)
LOC_LIVE = set(os.listdir(FLEX / "sponsors/location")) if (FLEX / "sponsors/location").exists() else set()
CO_LIVE = set(os.listdir(FLEX / "sponsors/company")) if (FLEX / "sponsors/company").exists() else set()

STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
          "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "Washington DC", "FL": "Florida",
          "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
          "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
          "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
          "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
          "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
          "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
          "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
          "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
          "PR": "Puerto Rico"}


def slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def state_link(name):
    s = slug(name)
    return f"[{name}]({SITE}/sponsors/location/{s}/)" if s in LOC_LIVE else name


def company_link(name, s):
    return f"[{name}]({SITE}/sponsors/company/{s}/)" if s in CO_LIVE else name


def main():
    companies = json.loads(SRC.read_text())["companies"]
    summary = json.loads(SUMMARY.read_text()) if SUMMARY.exists() else {}
    total_companies = summary.get("companies", len(companies))
    total_positions = summary.get("rows_certified_h1b")
    today = datetime.date.today().isoformat()

    # aggregate per state from reported worksite cities (same method as the live location pages)
    filings = defaultdict(int)                    # ST -> total filings
    comp_count = defaultdict(set)                 # ST -> distinct company slugs
    comp_filings = defaultdict(lambda: defaultdict(int))  # ST -> {slug: filings}
    names = {}                                    # slug -> display name
    for c in companies:
        names[c["s"]] = c["n"]
        for city, n in c.get("c", []):
            st = city.split(",")[-1].strip()
            if st not in STATES:
                continue
            filings[st] += n
            comp_count[st].add(c["s"])
            comp_filings[st][c["s"]] += n

    # build per-state rows, sorted by filing volume
    states = []
    for st in filings:
        top = sorted(comp_filings[st].items(), key=lambda x: -x[1])
        top10 = [{"company": names[s], "slug": s, "h1b_filings": n,
                  "flexapply_url": f"{SITE}/sponsors/company/{s}/"} for s, n in top[:10]]
        states.append({
            "state": STATES[st], "state_code": st,
            "sponsoring_companies": len(comp_count[st]),
            "h1b_filings": filings[st],
            "top_sponsor": names[top[0][0]], "top_sponsor_slug": top[0][0],
            "top_sponsor_filings": top[0][1],
            "location_url": f"{SITE}/sponsors/location/{slug(STATES[st])}/",
            "top10_companies": top10,
        })
    states.sort(key=lambda x: -x["h1b_filings"])

    # --- full dataset: CSV + JSON ---
    with (HERE / "data" / f"h1b-sponsors-by-state-{FY.lower()}.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["state", "state_code", "sponsoring_companies", "h1b_filings",
                    "top_sponsor", "top_sponsor_h1b_filings", "flexapply_location_url"])
        for s in states:
            w.writerow([s["state"], s["state_code"], s["sponsoring_companies"], s["h1b_filings"],
                        s["top_sponsor"], s["top_sponsor_filings"], s["location_url"]])
    (HERE / "data" / f"h1b-sponsors-by-state-{FY.lower()}.json").write_text(
        json.dumps(states, indent=None, separators=(",", ":")))

    # --- README ---
    rows = []
    for i, s in enumerate(states, 1):
        rows.append(
            f'| {i} | {state_link(s["state"])} | {s["sponsoring_companies"]:,} '
            f'| {s["h1b_filings"]:,} | {company_link(s["top_sponsor"], s["top_sponsor_slug"])} |'
        )
    table = "\n".join(rows)
    top5 = ", ".join(s["state"] for s in states[:5])
    n_states = len(states)
    pos_line = (f"{total_positions:,} certified H-1B positions across {total_companies:,} employers"
                if total_positions else f"{total_companies:,} employers")

    readme = f"""# H-1B Visa Sponsors by State ({FY[2:]})

A free breakdown of which U.S. states have the most H-1B visa sponsors, built from
official U.S. Department of Labor data for fiscal year 2025. It covers {pos_line},
grouped by the state where the work happens.

If you are on OPT or STEM OPT, or job searching and open to relocating, this answers a
practical question most sponsor lists skip: where are the H-1B sponsors actually hiring?
The counts below are U.S. only and rebuilt each quarter from the newest DOL file.

Browse the full searchable version, with a page per state and a page per company showing
roles, cities, and wage bands: **{SITE}/sponsors/companies/**

## H-1B sponsors by state, {FY}

Ranked by number of certified H-1B filings at worksites in each state.

| # | State | Sponsoring companies | H-1B filings ({FY}) | Largest sponsor |
|---|-------|---------------------|---------------------|-----------------|
{table}

Each state links to its live page with the full ranked employer list. The machine
readable version, including the top 10 sponsors in every state, is in
[`data/h1b-sponsors-by-state-{FY.lower()}.csv`](data/h1b-sponsors-by-state-{FY.lower()}.csv)
(and [`.json`](data/h1b-sponsors-by-state-{FY.lower()}.json)). Fork it, filter it, build on it.

## How to use this

- Sort by filings to see where sponsorship is most common, or by company count to find
  states with a wider spread of employers rather than one or two giants.
- Pick your state, open its page, and work down the ranked list of employers that filed.
- New to the H-1B job search? Free guide: {SITE}/free-guide/

## Frequently asked questions

### Which states sponsor the most H-1B visas?

By {FY} filing volume the top states are {top5}. Large tech and consulting hubs pull the
most filings, but every state in the table has employers that sponsor.

### Are these the states where I have to live?

Not necessarily. The state reflects the worksite listed on the filing. Many roles are
now hybrid or remote, and large sponsors file in several states at once, so treat this as
a map of where sponsorship is concentrated, not a hard requirement.

### How is a state's count calculated?

It sums certified H-1B labor condition applications by the worksite city and state that
the employer reported. A company that hires in several states is counted in each.

### Is this free?

Yes. The data is public and this list is free to use, fork, and share.

## About the data

Source: U.S. DOL LCA Disclosure Data {FY} Q4 (the full-year file). Counts are certified
H-1B labor condition applications, the standard public proxy for who sponsors, grouped by
the reported worksite location. An LCA is a step in the process, not a promise that a
specific role is open today, so read the counts as a signal of where sponsors are, not as
a live job board.

Maintained by [FlexApply]({SITE}) and updated quarterly when DOL posts new data.
Last updated: {today}.

## License

The underlying data is public (U.S. Department of Labor). This dataset and its build
script are released under the MIT License. Attribution to FlexApply is appreciated.
"""
    (HERE / "README.md").write_text(readme)
    print(f"OK: {n_states} states. Top: {states[0]['state']} "
          f"({states[0]['h1b_filings']:,} filings, {states[0]['sponsoring_companies']:,} companies). "
          f"Largest sponsor there: {states[0]['top_sponsor']}.")


if __name__ == "__main__":
    main()
