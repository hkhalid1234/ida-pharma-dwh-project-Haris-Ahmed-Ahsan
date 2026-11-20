"""Builds a small synthetic dataset with the SAME column layout as the course CSVs
(01_master_data, 05_pharmacy_sales_data, 06_hospital_demand_data). Used only for tests/dev."""
from pathlib import Path

import numpy as np
import pandas as pd


def _fmt(dt_index_or_series):
    # Cross-platform date format M/D/YYYY without leading zeroes (works on Windows, Linux, macOS)
    dt = pd.to_datetime(dt_index_or_series)
    m = dt.dt.month if hasattr(dt, "dt") else dt.month
    d = dt.dt.day if hasattr(dt, "dt") else dt.day
    y = dt.dt.year if hasattr(dt, "dt") else dt.year
    return m.astype(str) + "/" + d.astype(str) + "/" + y.astype(str)


def make(out: Path, n_sales=20000, seed=7):
    rng = np.random.default_rng(seed)
    out.mkdir(parents=True, exist_ok=True)
    cls = ["Antidiabetic", "Vaccine", "Biologic", "Insulin", "Anticoagulant", "Antiviral", "Oncology"]
    cat = ["Diabetes", "Infectious Disease", "Autoimmune", "Diabetes", "Cardiovascular", "Infectious Disease", "Cancer"]
    med = pd.DataFrame({
        "MedicineID": [f"MED{i:04d}" for i in range(1, 64)],
        "InternalSKU": [f"SKU-{i:05d}" for i in range(1, 64)],
        "GTIN14": [f"0{9506000000000 + i}" for i in range(63)],
        "GenericName": [f"generic drug {i}" for i in range(63)],
        "FictionalBrandName": [f"Brand{i}" for i in range(63)],
        "DiseaseCategory": [cat[i % 7] for i in range(63)], "ICD10Category": [f"e{i%9:02d}" for i in range(63)],
        "TherapeuticClass": [cls[i % 7] for i in range(63)],
        "DosageForm": rng.choice(["Tablet", "Capsule", "Solution for injection", "Oral solution"], 63),
        "Strength": [f"{x} mg" for x in rng.choice([5, 10, 50, 500], 63)],
        "RouteOfAdministration": rng.choice(["Oral", "Injection"], 63),
        "PackSize": rng.choice([10, 28, 30, 60], 63).astype(str),
        "PrescriptionClass": rng.choice(["Prescription", "OTC"], 63, p=[.8, .2]),
        "ControlledMedicineFlag": rng.choice(["Y", "N"], 63, p=[.1, .9]),
        "ColdChainFlag": "Y", "ProductStatus": "Active", "EffectiveFromDate": "1/1/2023"})
    med.to_csv(out / "01_master_data.csv", index=False)

    cities = [("New York", "NY"), ("Philadelphia", "PA"), ("Chicago", "IL"), ("Houston", "TX"), ("Los Angeles", "CA"),
              ("Phoenix", "AZ"), ("Boston", "MA"), ("Atlanta", "GA"), ("Seattle", "WA"), ("Denver", "CO"),
              ("Miami", "FL"), ("Dallas", "TX"), ("Detroit", "MI"), ("Columbus", "OH"), ("Charlotte", "NC"),
              ("Nashville", "TN"), ("Portland", "OR"), ("Baltimore", "MD")]
    ph = pd.DataFrame({
        "PharmacyID": [f"PH{i:03d}" for i in range(1, 61)],
        "PharmacyName": [f"Community Pharmacy {i}" for i in range(1, 61)],
        "PharmacyType": rng.choice(["Chain Pharmacy", "Independent Pharmacy", "Hospital Pharmacy"], 60),
        "PharmacyCity": [cities[i % 18][0] for i in range(60)], "PharmacyState": [cities[i % 18][1] for i in range(60)]})
    ph["HospitalID"] = None
    ph.loc[ph.PharmacyType == "Hospital Pharmacy", "HospitalID"] = "HOSP01"

    days = pd.date_range("2023-01-01", "2025-12-31")
    p = rng.integers(0, 60, n_sales)
    m = rng.integers(0, 63, n_sales)
    sd = days[rng.integers(0, len(days), n_sales)]
    q = rng.integers(1, 40, n_sales)
    price = rng.uniform(8, 120, n_sales)
    gross = q * price
    disc = gross * rng.uniform(0, .15, n_sales)
    sales = pd.DataFrame({
        "SalesTransactionID": [f"SALE{i:08d}" for i in range(1, n_sales + 1)],
        "PharmacyOrderID": [f"ORD{i:07d}" for i in range(n_sales)], "PharmacyDeliveryID": [f"DEL{i//3:07d}" for i in range(n_sales)],
        "PrescriptionID": [f"RX{i:07d}" if i % 3 else None for i in range(n_sales)],
        "WarehouseLotID": [f"LOT{i%900:05d}" for i in range(n_sales)], "ProductionBatchID": [f"MO{i%500:05d}" for i in range(n_sales)],
        "QuantitySoldPacks": q, "NetSalesAmountUSD": np.round(gross - disc, 2), "DiscountAmountUSD": np.round(disc, 2),
        "CostOfGoodsSoldUSD": np.round(gross * .6, 2), "ReturnedQuantityPacks": (rng.random(n_sales) < .03).astype(int),
        "PharmacyID": ph.PharmacyID.values[p], "PharmacyGLN": "9.506E+11", "PharmacyName": ph.PharmacyName.values[p],
        "PharmacyType": ph.PharmacyType.values[p], "HospitalID": ph.HospitalID.values[p],
        "PharmacyCity": ph.PharmacyCity.values[p], "PharmacyState": ph.PharmacyState.values[p], "CountryCode": "US",
        "SalesDate": _fmt(sd), "PharmacyDeliveryDate": _fmt(sd - pd.to_timedelta(rng.integers(0, 5, n_sales), unit="D")),
        "MedicineID": med.MedicineID.values[m],
        "SalesChannel": rng.choice(["Physical Pharmacy", "Ecommerce"], n_sales, p=[.7, .3]),
        "CustomerSegment": rng.choice(["retail", "chronic", "senior"], n_sales),
        "PayerType": rng.choice(["Insurance", "Government", "Cash"], n_sales),
        "PaymentMethod": rng.choice(["Card", "Cash", "Insurance claim"], n_sales),
        "PromotionCode": rng.choice([None, "PROMO10", "WELCOME"], n_sales, p=[.84, .1, .06]),
        "PrescriptionRequiredFlag": rng.choice(["Y", "N"], n_sales), "ReturnFlag": rng.choice(["Y", "N"], n_sales, p=[.03, .97]),
        "SaleStatus": "Completed", "EcommerceDeliveryStatus": None, "DaysToExpiryAtSale": rng.integers(9, 1076, n_sales)})
    sales.to_csv(out / "05_pharmacy_sales_data.csv", index=False)

    hosp = [f"HOSP{i:02d}" for i in range(1, 13)]
    months = pd.date_range("2023-01-01", "2025-12-01", freq="MS")
    rows = []
    for mo in months:
        for hi, h in enumerate(hosp):
            for mi in range(63):
                base = rng.integers(50, 500)
                rows.append((mo, h, mi, base))
    d = pd.DataFrame(rows, columns=["mo", "h", "mi", "base"])
    n = len(d)
    req = (d.base * rng.uniform(.9, 1.2, n)).round().astype(int)
    hdf = pd.DataFrame({
        "HospitalDemandRecordID": [f"HD{i:08d}" for i in range(1, n + 1)], "HospitalID": d.h,
        "HospitalGLN": "9.506E+12", "HospitalName": [f"General Hospital {x[-2:]}" for x in d.h],
        "HospitalType": "Teaching", "HospitalPharmacyID": [f"PH{int(x[-2:]):03d}" for x in d.h],
        "LicensedBeds": [200 + 60 * int(x[-2:]) for x in d.h], "ICUBeds": 30,
        "AverageOccupancyRatePct": 78.5, "TraumaLevel": [("Level 1" if int(x[-2:]) % 2 else None) for x in d.h],
        "CatchmentPopulation": 500000, "City": [cities[int(x[-2:]) % 18][0] for x in d.h],
        "State": [cities[int(x[-2:]) % 18][1] for x in d.h], "CountryCode": "US",
        "DemandMonth": _fmt(d.mo), "MedicineID": med.MedicineID.values[d.mi],
        "MedicationRequestStatus": rng.choice(["Completed", "Partially Filled"], n, p=[.8, .2]),
        "FormularyStatus": rng.choice(["Formulary", "Restricted", "Non-formulary exception"], n, p=[.7, .2, .1]),
        "ForecastDemandPacks": (d.base * rng.uniform(.85, 1.15, n)).round().astype(int), "RequestedQuantityPacks": req,
        "ConsumedQuantityPacks": (req * rng.uniform(.8, 1.0, n)).round().astype(int),
        "UnfulfilledDemandPacks": (req * rng.uniform(0, .15, n)).round().astype(int),
        "ClosingStockPacks": rng.integers(0, 600, n)})
    hdf.to_csv(out / "06_hospital_demand_data.csv", index=False)
