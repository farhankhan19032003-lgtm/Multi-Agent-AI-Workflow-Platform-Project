"""Download real public datasets and load them into the DuckDB analytics file.

Usage (from api/):
    python -m scripts.load_datasets                 # download + load all six
    python -m scripts.load_datasets --only ai4i_machines bike_sharing
    python -m scripts.load_datasets --from-dir ./downloads   # use files you downloaded manually
    python -m scripts.load_datasets --sample        # tiny SYNTHETIC samples (offline demo / tests)

Sources (all public):
  ai4i_machines   https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip
  online_retail   https://archive.ics.uci.edu/static/public/352/online+retail.zip
  telco_churn     https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv
  bank_marketing  https://archive.ics.uci.edu/static/public/222/bank+marketing.zip
  bike_sharing    https://archive.ics.uci.edu/static/public/275/bike+sharing+dataset.zip
  adult_census    https://archive.ics.uci.edu/static/public/2/adult.zip
"""
import argparse
import io
import random
import re
import sys
import zipfile
from pathlib import Path

import duckdb
import httpx
import pandas as pd

from app.config import get_settings
from app.datasets import DATASETS, db_path

URLS = {
    "ai4i_machines": "https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip",
    "online_retail": "https://archive.ics.uci.edu/static/public/352/online+retail.zip",
    "telco_churn": "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv",
    "bank_marketing": "https://archive.ics.uci.edu/static/public/222/bank+marketing.zip",
    "bike_sharing": "https://archive.ics.uci.edu/static/public/275/bike+sharing+dataset.zip",
    "adult_census": "https://archive.ics.uci.edu/static/public/2/adult.zip",
}


def snake(name: str) -> str:
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name.strip())
    s = re.sub(r"[^0-9a-zA-Z]+", "_", s).strip("_").lower()
    return s


# ---------------------------------------------------------------- zip helpers
def _find_in_zip(data: bytes, wanted: str) -> bytes:
    """Find a file by name in a zip, descending into nested zips."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            base = info.filename.rsplit("/", 1)[-1]
            if base.lower() == wanted.lower():
                return z.read(info)
        for info in z.infolist():
            if info.filename.lower().endswith(".zip"):
                try:
                    return _find_in_zip(z.read(info), wanted)
                except FileNotFoundError:
                    continue
    raise FileNotFoundError(wanted)


# ------------------------------------------------------------------- parsers
def parse_ai4i(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(_find_in_zip(raw, "ai4i2020.csv")))
    names = ["udi", "product_id", "type", "air_temperature_k", "process_temperature_k",
             "rotational_speed_rpm", "torque_nm", "tool_wear_min", "machine_failure",
             "twf", "hdf", "pwf", "osf", "rnf"]
    if len(df.columns) != len(names):
        raise ValueError(f"Unexpected AI4I column count: {len(df.columns)}")
    df.columns = names
    return df


def parse_online_retail(raw: bytes) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(_find_in_zip(raw, "Online Retail.xlsx")))
    df.columns = ["invoice_no", "stock_code", "description", "quantity", "invoice_date",
                  "unit_price", "customer_id", "country"]
    df["invoice_no"] = df["invoice_no"].astype(str)
    df["stock_code"] = df["stock_code"].astype(str)
    df["customer_id"] = df["customer_id"].astype("Int64")
    df["revenue"] = df["quantity"] * df["unit_price"]
    df["is_cancellation"] = df["invoice_no"].str.startswith("C")
    return df


def parse_telco(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw))
    df.columns = [snake(c) for c in df.columns]
    df["total_charges"] = pd.to_numeric(df["total_charges"], errors="coerce")
    return df


def parse_bank(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(_find_in_zip(raw, "bank-full.csv")), sep=";")
    df.columns = ["age", "job", "marital", "education", "credit_default", "balance",
                  "housing_loan", "personal_loan", "contact", "day_of_month", "month",
                  "duration", "campaign", "pdays", "previous", "poutcome", "subscribed"]
    return df


def parse_bike(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(_find_in_zip(raw, "hour.csv")))
    df = df.rename(columns={
        "dteday": "date", "yr": "year_idx", "mnth": "month", "hr": "hour",
        "weathersit": "weather_situation", "hum": "humidity", "cnt": "total_rentals"})
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["temp_c"] = (df["temp"] * 47 - 8).round(1)
    df["humidity_pct"] = (df["humidity"] * 100).round(0)
    return df


def parse_adult(raw: bytes) -> pd.DataFrame:
    names = ["age", "workclass", "fnlwgt", "education", "education_num", "marital_status",
             "occupation", "relationship", "race", "sex", "capital_gain", "capital_loss",
             "hours_per_week", "native_country", "income"]
    return pd.read_csv(io.BytesIO(_find_in_zip(raw, "adult.data")), header=None, names=names,
                       skipinitialspace=True, na_values="?")


PARSERS = {
    "ai4i_machines": parse_ai4i, "online_retail": parse_online_retail,
    "telco_churn": parse_telco, "bank_marketing": parse_bank,
    "bike_sharing": parse_bike, "adult_census": parse_adult,
}


def _fetch(name: str, from_dir: Path | None) -> bytes:
    if from_dir:
        norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())  # noqa: E731
        want = norm(Path(URLS[name]).name)
        for f in from_dir.iterdir():
            if norm(f.name) == want:
                return f.read_bytes()
        raise FileNotFoundError(f"{Path(URLS[name]).name} not found in {from_dir}")
    print(f"  downloading {URLS[name]}")
    with httpx.Client(follow_redirects=True, timeout=300) as c:
        r = c.get(URLS[name])
        r.raise_for_status()
        return r.content


# ------------------------------------------------------- synthetic offline sample
def make_samples() -> dict[str, pd.DataFrame]:
    rnd = random.Random(7)
    n = 400
    ai4i = []
    for i in range(1, n + 1):
        t = rnd.choices(["L", "M", "H"], [5, 3, 2])[0]
        air, rpm, torque, wear = rnd.gauss(300, 2), rnd.gauss(1500, 150), rnd.gauss(40, 10), rnd.randint(0, 250)
        proc = air + 10 + rnd.gauss(0, 1)
        osf = int(wear * torque > {"L": 11000, "M": 12000, "H": 13000}[t])
        hdf = int(proc - air < 8.6 and rpm < 1380)
        twf, pwf, rnf = int(wear > 235), 0, int(rnd.random() < 0.001)
        ai4i.append([i, f"{t}{i}", t, round(air, 1), round(proc, 1), int(rpm), round(torque, 1), wear,
                     int(osf or hdf or twf or rnf), twf, hdf, pwf, osf, rnf])
    ai4i = pd.DataFrame(ai4i, columns=["udi", "product_id", "type", "air_temperature_k",
                                       "process_temperature_k", "rotational_speed_rpm", "torque_nm",
                                       "tool_wear_min", "machine_failure", "twf", "hdf", "pwf", "osf", "rnf"])
    days = pd.date_range("2011-01-01", periods=300, freq="D")
    retail = []
    for d in days:
        for _ in range(rnd.randint(2, 6)):
            q, p = rnd.randint(1, 12), round(rnd.uniform(0.5, 25), 2)
            inv = f"{rnd.randint(500000, 599999)}"
            cancel = rnd.random() < 0.05
            retail.append([("C" if cancel else "") + inv, f"SKU{rnd.randint(1, 60)}", "SAMPLE ITEM",
                           -q if cancel else q, d, p, rnd.choice([None] + list(range(12000, 12120))),
                           rnd.choices(["United Kingdom", "France", "Germany"], [8, 1, 1])[0],
                           (-q if cancel else q) * p, cancel])
    retail = pd.DataFrame(retail, columns=["invoice_no", "stock_code", "description", "quantity",
                                           "invoice_date", "unit_price", "customer_id", "country",
                                           "revenue", "is_cancellation"])
    retail["customer_id"] = retail["customer_id"].astype("Int64")
    telco = []
    for i in range(500):
        ten = rnd.randint(0, 72)
        contract = rnd.choices(["Month-to-month", "One year", "Two year"], [6, 2, 2])[0]
        monthly = round(rnd.uniform(18, 115), 2)
        churn = "Yes" if rnd.random() < (0.45 if contract == "Month-to-month" else 0.08) else "No"
        telco.append([f"C{i:04d}", rnd.choice(["Male", "Female"]), int(rnd.random() < 0.16),
                      rnd.choice(["Yes", "No"]), rnd.choice(["Yes", "No"]), ten, "Yes", "No",
                      rnd.choice(["DSL", "Fiber optic", "No"]), "No", "No", "No", "No", "No", "No",
                      contract, rnd.choice(["Yes", "No"]),
                      rnd.choice(["Electronic check", "Mailed check", "Bank transfer", "Credit card"]),
                      monthly, round(monthly * ten, 2) if ten else None, churn])
    telco = pd.DataFrame(telco, columns=[snake(c) for c in [
        "customerID", "gender", "SeniorCitizen", "Partner", "Dependents", "tenure", "PhoneService",
        "MultipleLines", "InternetService", "OnlineSecurity", "OnlineBackup", "DeviceProtection",
        "TechSupport", "StreamingTV", "StreamingMovies", "Contract", "PaperlessBilling",
        "PaymentMethod", "MonthlyCharges", "TotalCharges", "Churn"]])
    bank = pd.DataFrame([[rnd.randint(19, 80), rnd.choice(["admin.", "technician", "retired", "student"]),
                          rnd.choice(["married", "single", "divorced"]), rnd.choice(["primary", "secondary", "tertiary"]),
                          "no", rnd.randint(-500, 9000), rnd.choice(["yes", "no"]), rnd.choice(["yes", "no"]),
                          rnd.choice(["cellular", "telephone", "unknown"]), rnd.randint(1, 28),
                          rnd.choice(["jan", "may", "jul", "oct"]), rnd.randint(5, 900), rnd.randint(1, 6),
                          -1, 0, "unknown", rnd.choices(["yes", "no"], [1, 8])[0]] for _ in range(600)],
                        columns=["age", "job", "marital", "education", "credit_default", "balance",
                                 "housing_loan", "personal_loan", "contact", "day_of_month", "month",
                                 "duration", "campaign", "pdays", "previous", "poutcome", "subscribed"])
    bike = []
    for k, d in enumerate(pd.date_range("2011-01-01", periods=60, freq="D")):
        for h in range(24):
            temp = rnd.uniform(0.1, 0.9)
            casual, reg = rnd.randint(0, 40), rnd.randint(5, 250)
            bike.append([k * 24 + h + 1, d.date(), 1, 0, d.month, h, 0, d.weekday(), int(d.weekday() < 5),
                         rnd.choice([1, 1, 2, 3]), temp, temp, rnd.uniform(0.3, 0.9), rnd.uniform(0, 0.5),
                         casual, reg, casual + reg, round(temp * 47 - 8, 1), 60.0])
    bike = pd.DataFrame(bike, columns=["instant", "date", "season", "year_idx", "month", "hour", "holiday",
                                       "weekday", "workingday", "weather_situation", "temp", "atemp",
                                       "humidity", "windspeed", "casual", "registered", "total_rentals",
                                       "temp_c", "humidity_pct"])
    adult = pd.DataFrame([[rnd.randint(18, 70), rnd.choice(["Private", "Self-emp", "Gov"]), rnd.randint(20000, 400000),
                           rnd.choice(["HS-grad", "Bachelors", "Masters"]), rnd.randint(9, 16),
                           rnd.choice(["Married", "Never-married"]), rnd.choice(["Sales", "Tech-support", "Craft-repair"]),
                           "Husband", "White", rnd.choice(["Male", "Female"]), 0, 0, rnd.randint(20, 60),
                           "United-States", rnd.choices([">50K", "<=50K"], [1, 3])[0]] for _ in range(500)],
                         columns=["age", "workclass", "fnlwgt", "education", "education_num", "marital_status",
                                  "occupation", "relationship", "race", "sex", "capital_gain", "capital_loss",
                                  "hours_per_week", "native_country", "income"])
    return {"ai4i_machines": ai4i, "online_retail": retail, "telco_churn": telco,
            "bank_marketing": bank, "bike_sharing": bike, "adult_census": adult}


# ---------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", choices=list(DATASETS), help="load only these datasets")
    ap.add_argument("--from-dir", type=Path, help="folder with manually downloaded files")
    ap.add_argument("--sample", action="store_true", help="load tiny SYNTHETIC samples (no download)")
    args = ap.parse_args()

    targets = args.only or list(DATASETS)
    Path(get_settings().data_dir).mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path()))
    failures = []
    try:
        samples = make_samples() if args.sample else {}
        for name in targets:
            print(f"[{name}]")
            try:
                df = samples[name] if args.sample else PARSERS[name](_fetch(name, args.from_dir))
                con.register("df_in", df)
                con.execute(f'CREATE OR REPLACE TABLE "{name}" AS SELECT * FROM df_in')
                con.unregister("df_in")
                print(f"  loaded {len(df):,} rows" + (" (SYNTHETIC SAMPLE)" if args.sample else ""))
            except Exception as e:  # keep going so one bad download does not block the rest
                failures.append(name)
                print(f"  FAILED: {e}")
    finally:
        con.close()
    if failures:
        print(f"\nFailed: {', '.join(failures)}. Download those files manually from the URLs in the "
              "script header and rerun with --from-dir <folder>.")
        sys.exit(1)
    print("\nDone. Datasets are ready.")


if __name__ == "__main__":
    main()
