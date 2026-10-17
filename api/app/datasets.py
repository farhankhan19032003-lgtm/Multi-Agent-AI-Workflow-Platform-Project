"""Optional public sample datasets (UCI / IBM). Metadata only; per-company data lives in tenantdb.py."""
from pathlib import Path

from .config import get_settings

# ---------------------------------------------------------------------------
# Dataset metadata (sources verified against the UCI repository / IBM GitHub)
# ---------------------------------------------------------------------------
DATASETS: dict[str, dict] = {
    "ai4i_machines": {
        "title": "AI4I 2020 Predictive Maintenance",
        "source": "UCI ML Repository #601 (CC BY 4.0). Synthetic data modelled on real industrial machines.",
        "description": "10,000 milling-machine records: process readings and failure flags.",
        "notes": {
            "type": "Product quality variant: L (50%), M (30%), H (20%)",
            "air_temperature_k": "Air temperature in Kelvin",
            "process_temperature_k": "Process temperature in Kelvin",
            "rotational_speed_rpm": "Spindle speed in rpm",
            "torque_nm": "Torque in Nm",
            "tool_wear_min": "Minutes of tool wear",
            "machine_failure": "1 if the machine failed in any of the 5 modes below",
            "twf": "Tool wear failure",
            "hdf": "Heat dissipation failure (documented: air-process temp gap < 8.6 K and speed < 1380 rpm)",
            "pwf": "Power failure (documented: power = torque x rad/s outside 3500-9000 W)",
            "osf": "Overstrain failure (documented: tool wear x torque above 11000/12000/13000 minNm for L/M/H)",
            "rnf": "Random failure (0.1% chance regardless of settings)",
        },
    },
    "online_retail": {
        "title": "Online Retail (UK gift retailer)",
        "source": "UCI ML Repository #352. Real transactions of a UK online retailer.",
        "description": "~541k invoice lines. Cancellations have invoice_no starting with 'C' and negative quantity.",
        "notes": {
            "invoice_no": "Invoice id; 'C' prefix = cancellation",
            "stock_code": "Product code",
            "quantity": "Units; negative on cancellations",
            "invoice_date": "Timestamp of the invoice",
            "unit_price": "Price per unit in GBP",
            "customer_id": "Customer id; about a quarter of rows are NULL (guest checkouts)",
            "revenue": "Derived: quantity * unit_price",
            "is_cancellation": "Derived: TRUE when invoice_no starts with 'C'",
        },
    },
    "telco_churn": {
        "title": "Telco Customer Churn (IBM sample)",
        "source": "IBM telco-customer-churn sample dataset (GitHub).",
        "description": "7,043 telecom customers with services, contract, charges and churn flag.",
        "notes": {
            "tenure": "Months the customer has stayed",
            "senior_citizen": "1 = senior citizen",
            "contract": "Month-to-month / One year / Two year",
            "monthly_charges": "Current monthly bill",
            "total_charges": "Lifetime charges (NULL for brand-new customers)",
            "churn": "'Yes' if the customer left in the last month",
        },
    },
    "bank_marketing": {
        "title": "Bank Marketing (Portuguese bank phone campaigns)",
        "source": "UCI ML Repository #222 (bank-full.csv). Real campaign data.",
        "description": "45,211 contacts from direct-marketing phone campaigns for term deposits.",
        "notes": {
            "credit_default": "Has credit in default? yes/no",
            "balance": "Average yearly balance in euros",
            "housing_loan": "Has housing loan? yes/no",
            "personal_loan": "Has personal loan? yes/no",
            "contact": "Contact channel (cellular/telephone/unknown)",
            "day_of_month": "Day of month of last contact",
            "month": "Month of last contact (jan..dec)",
            "duration": "Last call length in seconds",
            "campaign": "Number of contacts in this campaign",
            "pdays": "Days since previous campaign contact (-1 = never)",
            "poutcome": "Outcome of previous campaign",
            "subscribed": "'yes' if the client subscribed to a term deposit (the target)",
        },
    },
    "bike_sharing": {
        "title": "Bike Sharing (Capital Bikeshare, Washington DC)",
        "source": "UCI ML Repository #275 (hour.csv). Real rental counts 2011-2012 with weather.",
        "description": "17,379 hourly records of rentals with weather and calendar data.",
        "notes": {
            "date": "Calendar date",
            "season": "1 spring, 2 summer, 3 fall, 4 winter",
            "year_idx": "0 = 2011, 1 = 2012",
            "month": "1-12",
            "hour": "0-23",
            "weather_situation": "1 clear, 2 mist/cloudy, 3 light rain/snow, 4 heavy rain/snow",
            "temp_c": "Derived temperature in Celsius (temp * 47 - 8 per UCI readme)",
            "humidity_pct": "Derived humidity percent (hum * 100)",
            "casual": "Rentals by casual users",
            "registered": "Rentals by registered users",
            "total_rentals": "casual + registered",
        },
    },
    "adult_census": {
        "title": "Adult Census Income",
        "source": "UCI ML Repository #2 (adult.data), 1994 US Census extract.",
        "description": "~32.5k people with demographics, work and an income class.",
        "notes": {
            "fnlwgt": "Census sampling weight",
            "education_num": "Years-of-education code",
            "hours_per_week": "Working hours per week",
            "income": "'>50K' or '<=50K' per year (target)",
        },
    },
}

def db_path() -> Path:
    return Path(get_settings().data_dir) / "analytics.duckdb"


def is_loaded() -> bool:
    return db_path().exists()
