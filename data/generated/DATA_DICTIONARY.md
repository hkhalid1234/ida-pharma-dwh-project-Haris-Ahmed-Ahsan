# Oversampled Data Dictionary - Phase 1 (SDI Data Mart)
**Course:** Intelligent Data Architectures (Fall 2026)  
**Deliverable:** Milestone 1 - Oversampled data folder along with data dictionary  
**Team:** Ahsan Imran (28376), Haris Khalid (28557), Syed Ahmed Farrukh (28543)  

---

## 1. Overview of Oversampled Datasets

To simulate a live 24/7 automated pipeline, the data oversampling layer synthesizes incremental monthly batches that append to historical data without deleting or truncating the warehouse.

* **Refresh 1 (`R01` - January 2026):** Models a peak winter seasonal month (seasonal demand factor 3.41x historical average).
* **Refresh 2 (`R02` - February 2026):** Models a post-peak month (seasonal factor 0.46x) and injects Slowly Changing Dimension (SCD Type 2) attribute changes for 3 medicines.
* **Corrupted Record Injection:** An intentional 0.5% dirty-data rate is applied to test data validation rules (negative quantities, missing medicine IDs, invalid dates).

---

## 2. Dataset: Master Data (`01_master_data`)

Files: `01_master_data__R01.csv`, `01_master_data__R02.csv`  
Granularity: 1 row = 1 Medicine SKU version

| Column Name | Data Type | Description | Constraints & Business Rules |
| :--- | :--- | :--- | :--- |
| `MedicineID` | VARCHAR(10) | Unique natural business identifier | Primary Key, format `MED####` |
| `InternalSKU` | VARCHAR(15) | Internal stock keeping unit code | Unique, format `SKU-#####` |
| `GTIN14` | CHAR(14) | Global Trade Item Number (GS1 barcode) | 14-digit numeric string |
| `GenericName` | VARCHAR(60) | International non-proprietary drug name | Mandatory |
| `FictionalBrandName` | VARCHAR(60) | Commercial trade/brand name | Mandatory |
| `DiseaseCategory` | VARCHAR(50) | Clinical therapeutic indication category | Diabetes, Oncology, Cardiovascular, etc. |
| `ICD10Category` | CHAR(3) | International classification of disease code | 3-character alphanumeric |
| `ATCCode` | VARCHAR(10) | Anatomical Therapeutic Chemical classification | Standard ATC code |
| `TherapeuticClass` | VARCHAR(50) | Pharmacological drug class | Biologic, Vaccine, Insulin, etc. |
| `DosageForm` | VARCHAR(30) | Physical presentation form | Tablet, Capsule, Solution for injection |
| `Strength` | VARCHAR(40) | Active pharmaceutical ingredient concentration | E.g., `10 mg`, `50 mg` |
| `RouteOfAdministration`| VARCHAR(20) | Route of drug administration | Oral, Injection, Intravenous |
| `PackSize` | SMALLINT | Number of units per commercial package | **SCD Type 2 Tracked Attribute** |
| `PrescriptionClass` | VARCHAR(20) | Regulatory dispense status | **SCD Type 2 Tracked** (`Prescription`, `OTC`) |
| `ControlledMedicineFlag`| CHAR(1) | Controlled substance regulatory indicator | `Y` or `N` |
| `ColdChainFlag` | CHAR(1) | Requires 2°C to 8°C cold chain storage | Always `Y` in this supply chain |
| `ProductStatus` | VARCHAR(15) | Lifecycle status of medicine SKU | Active, Discontinued |
| `EffectiveFromDate` | DATE / ISO | Date from which current attributes are valid | YYYY-MM-DD or M/D/YYYY |

### Oversampling Behavior:
* **R01 (Jan 2026):** 0 rows modified (master data is stable).
* **R02 (Feb 2026):** 3 rows emitted with updated `PackSize` and `PrescriptionClass` for `MED014`, `MED023`, and `MED058` to demonstrate SCD Type 2 dimension expiration and re-insertion.

---

## 3. Dataset: Pharmacy Sales Data (`05_pharmacy_sales_data`)

Files: `05_pharmacy_sales_data__R01.csv`, `05_pharmacy_sales_data__R02.csv`  
Granularity: 1 row = 1 Retail, Hospital, or E-commerce Sales Transaction

| Column Name | Data Type | Description | Constraints & Business Rules |
| :--- | :--- | :--- | :--- |
| `SalesTransactionID` | VARCHAR(20) | Unique transaction identifier | Primary Key, sequence continued from history |
| `PharmacyOrderID` | VARCHAR(15) | Upstream pharmacy order reference | Format `ORD#######` |
| `PharmacyDeliveryID` | VARCHAR(15) | Logistics delivery / dispatch ID | Format `DEL#######` |
| `PrescriptionID` | VARCHAR(15) | Medical prescription serial number | Required if `PrescriptionRequiredFlag = 'Y'` |
| `WarehouseLotID` | VARCHAR(15) | Originating inventory lot identifier | Cold-chain traceability key |
| `ProductionBatchID` | VARCHAR(20) | Manufacturing batch lot reference | Format `MO#####` |
| `SalesDate` | DATE / Text | Date transaction took place | ISO or M/D/YYYY; must be in batch month |
| `SalesTimestampUTC` | TIMESTAMP | Exact UTC timestamp of transaction | ISO-8601 UTC format |
| `SalesChannel` | VARCHAR(20) | Distribution channel | `Physical Pharmacy` (In store), `Ecommerce` (Online) |
| `PharmacyID` | VARCHAR(10) | Selling pharmacy foreign key | Must exist in `DimPharmacy` |
| `PharmacyGLN` | CHAR(13) | Global Location Number of store | 13-digit GS1 identifier |
| `PharmacyName` | VARCHAR(60) | Business store name | Informational |
| `PharmacyType` | VARCHAR(25) | Type of pharmacy | Chain, Independent, Hospital Pharmacy |
| `HospitalID` | VARCHAR(10) | Associated hospital code | Nullable for independent/chain retail |
| `PharmacyCity` | VARCHAR(40) | Municipality of dispensing location | Mapped to `DimLocation` |
| `PharmacyState` | CHAR(2) | Two-letter US state code | Valid US state abbreviation |
| `CountryCode` | CHAR(2) | Dispensing country code | `US` |
| `MedicineID` | VARCHAR(10) | Dispensed pharmaceutical product | Foreign Key to `DimMedicine` |
| `QuantitySoldPacks` | INT | Number of commercial packs sold | Must be > 0 (violation filtered to rejects) |
| `NetSalesAmountUSD` | DECIMAL(12,2)| Revenue realized after discount | Must be > 0 (enforces valid positive price) |
| `DiscountAmountUSD` | DECIMAL(12,2)| Total promotional discount applied | Must be >= 0 |
| `CostOfGoodsSoldUSD` | DECIMAL(12,2)| Manufacturer cost of goods sold | CoGS used for gross margin calculation |
| `ReturnedQuantityPacks`| INT | Returned product packs | Defaults to 0 |
| `CustomerSegment` | VARCHAR(25) | Retail customer demographic | retail, chronic, senior |
| `PayerType` | VARCHAR(20) | Primary payer category | Insurance, Government, Cash |
| `PaymentMethod` | VARCHAR(20) | Settlement instrument | Card, Cash, Insurance claim |
| `SaleStatus` | VARCHAR(20) | Transaction status | `Completed`, `Returned` |
| `DaysToExpiryAtSale` | INT | Days until drug expiry date at sale | Cold chain shelf life indicator |

### Oversampling Behavior:
* **R01 (Jan 2026):** 48,737 rows generated (seasonal factor 3.41x). Bootstrapped from historical January distributions with scaled quantities and revenue. 243 corrupted rows intentionally injected.
* **R02 (Feb 2026):** 7,144 rows generated (seasonal factor 0.46x). 35 corrupted rows intentionally injected.

---

## 4. Dataset: Hospital Demand Data (`06_hospital_demand_data`)

Files: `06_hospital_demand_data__R01.csv`, `06_hospital_demand_data__R02.csv`  
Granularity: 1 row = 1 Hospital x 1 Medicine x 1 Month

| Column Name | Data Type | Description | Constraints & Business Rules |
| :--- | :--- | :--- | :--- |
| `HospitalDemandRecordID`| VARCHAR(15)| Unique monthly demand log entry ID | Primary Key, sequence continued from history |
| `DemandMonth` | DATE / Text | Target consumption month | First day of month (e.g., `2026-01-01`) |
| `HospitalID` | VARCHAR(10) | Hospital facility foreign identifier | Format `HOSP01` to `HOSP12` |
| `HospitalGLN` | CHAR(13) | Global Location Number of facility | 13-digit GS1 identifier |
| `HospitalName` | VARCHAR(60) | Name of medical center | Informational |
| `HospitalType` | VARCHAR(30) | Classification of healthcare provider | Teaching, General, Specialty |
| `HospitalPharmacyID` | VARCHAR(10) | In-hospital dispensing pharmacy ID | Mapped to `DimPharmacy` |
| `City` | VARCHAR(40) | City location of hospital | Mapped to `DimLocation` |
| `State` | CHAR(2) | State of hospital facility | US State abbreviation |
| `LicensedBeds` | SMALLINT | Total certified bed capacity | Integer >= 50 |
| `ICUBeds` | SMALLINT | Intensive care unit bed capacity | Integer >= 10 |
| `TraumaLevel` | VARCHAR(10) | Verified emergency trauma rating | `Level 1`, `Level 2`, `Not rated` |
| `MedicineID` | VARCHAR(10) | Prescribed medicine product key | Foreign Key to `DimMedicine` |
| `MedicationRequestStatus`| VARCHAR(20)| Hospital procurement fulfillment status | `Completed`, `Partially Filled` |
| `FormularyStatus` | VARCHAR(25) | Institutional drug formulary tier | `Formulary`, `Restricted`, `Non-formulary` |
| `ForecastDemandPacks` | INT | Advanced clinical demand forecast | Must be >= 0 |
| `RequestedQuantityPacks`| INT | Total quantity requisitioned | Must be >= 0 |
| `ConsumedQuantityPacks` | INT | Actual packs administered to patients | Must be <= RequestedQuantityPacks |
| `UnfulfilledDemandPacks`| INT | Shortfall in requisitioned packs | `Requested - Consumed` |
| `ClosingStockPacks` | INT | Remaining inventory packs at month-end | Semi-additive stock measure |

### Oversampling Behavior:
* **R01 & R02:** Exactly 756 records per month (full matrix of 12 hospitals x 63 medicines).
* Incorporates ~6% stochastic Gaussian variance across requested and consumed quantities while enforcing that unfulfilled packs never exceed requested amounts.
