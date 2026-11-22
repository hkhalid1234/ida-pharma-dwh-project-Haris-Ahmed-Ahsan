# Complete Oversampled Data Dictionary - Phase 1 (SDI Data Mart)
 **Course:** Intelligent Data Architectures (Fall 2026)  
 **Deliverable:** Milestone 1 - Oversampled data folder along with data dictionary  
**Team:** Ahsan Imran (28376), Haris Khalid (28557), Syed Ahmed Farrukh (28543)  
 
 ---
 
## 1. Overview & Oversampling Methodology
 
To simulate a live 24/7 automated pipeline, our data oversampling layer synthesizes incremental monthly batches that append to historical data without deleting or truncating the warehouse.
 
* **Refresh 1 (R01 - January 2026):** Models a peak winter seasonal month (seasonal demand factor 3.41x historical average).
* **Refresh 2 (R02 - February 2026):** Models a post-peak month (seasonal factor 0.46x) and injects Slowly Changing Dimension (SCD Type 2) attribute changes for 3 medicines (MED014, MED023, MED058).
 * **Corrupted Record Injection:** An intentional 0.5% dirty-data rate is applied to test data validation rules (negative quantities, missing medicine IDs, invalid dates).
 
 ---
 
## 2. Dataset: 01_master_data (34 Columns)
**Files in folder:** 01_master_data__R01.csv, 01_master_data__R02.csv  
**Granularity:** 1 row = 1 Medicine SKU version (63 active medicines in catalogue)  
**Oversampling Behavior:** R01 has 0 modified rows (catalogue is stable). R02 emits 3 changed rows (MED014, MED023, MED058) with new PackSize and PrescriptionClass to trigger SCD Type 2 logic.

| # | Column Name | Data Type | Description | Constraints & Business Rules |
| :--- | :--- | :--- | :--- | :--- |
| 1 | MedicineID | VARCHAR(10) | Unique natural business identifier for medicine | PK, format MED### |
| 2 | InternalSKU | VARCHAR(15) | Internal stock keeping unit code in ERP | Format SKU-##-#### |
| 3 | GTIN14 | CHAR(14) | Global Trade Item Number barcode | 14-digit GS1 identifier |
| 4 | GenericName | VARCHAR(60) | International non-proprietary drug name | Active pharmaceutical ingredient |
| 5 | FictionalBrandName | VARCHAR(60) | Commercial trade/brand name | Commercial name |
| 6 | DiseaseCategory | VARCHAR(50) | Clinical therapeutic indication category | Diabetes, Oncology, etc. |
| 7 | ICD10Category | CHAR(7) | International classification of disease code | Format E11, J40-J47, etc. |
| 8 | ATCCode | VARCHAR(10) | Anatomical Therapeutic Chemical code | WHO ATC classification |
| 9 | TherapeuticClass | VARCHAR(50) | Pharmacological drug mechanism class | Biguanide, Statin, Biologic, etc. |
| 10 | DosageForm | VARCHAR(30) | Physical pharmaceutical delivery form | Tablet, Inhalation capsule, Vial, etc. |
| 11 | Strength | VARCHAR(40) | Active drug concentration / strength | E.g., 500 mg, 18 mcg |
| 12 | RouteOfAdministration | VARCHAR(20) | Route of drug intake | Oral, Inhalation, Injection, Subcutaneous |
| 13 | PackSize | SMALLINT | Number of units per commercial pack | SCD Type 2 tracked attribute |
| 14 | BaseUnitOfMeasure | VARCHAR(15) | Unit of measurement | pack, vial, bottle |
| 15 | PrescriptionClass | VARCHAR(20) | Regulatory dispensing category | SCD Type 2 tracked (Prescription, OTC) |
| 16 | ControlledMedicineFlag | CHAR(1) | Controlled substance classification flag | Y or N |
| 17 | ColdChainFlag | CHAR(1) | Requires temperature controlled cold chain | Y (2-8 C) or N (15-25 C) |
| 18 | StorageMinTempC | SMALLINT | Minimum allowable storage temperature in Celsius | E.g., 2 or 15 |
| 19 | StorageMaxTempC | SMALLINT | Maximum allowable storage temperature in Celsius | E.g., 8 or 25 |
| 20 | MaxHumidityPct | SMALLINT | Maximum permissible relative humidity percentage | E.g., 60 or 65 |
| 21 | ShelfLifeMonths | SMALLINT | Total nominal shelf life in months | E.g., 24 or 36 |
| 22 | MinimumRemainingShelfLifeDays | INT | Minimum remaining shelf life allowed for dispatch | E.g., 180 to 270 days |
| 23 | PrimarySupplierID | VARCHAR(10) | Primary active ingredient chemical supplier ID | Format SUP### |
| 24 | PrimaryPlantID | VARCHAR(10) | Primary manufacturing production plant ID | Format PLT## |
| 25 | ManufacturingLeadTimeDays | INT | Standard production lead time in days | Integer days |
| 26 | StandardBatchSizePacks | INT | Standard manufacturing batch output size | Commercial pack quantity |
| 27 | SafetyStockDays | INT | Recommended safety stock buffer in days | Inventory policy parameter |
| 28 | ReorderReviewCycleDays | INT | Review frequency for replenishment cycle | E.g., 7 or 14 days |
| 29 | UnitManufacturingCostUSD | DECIMAL(10,2) | Direct unit cost to manufacture one pack | Cost in USD |
| 30 | WholesalePriceUSD | DECIMAL(10,2) | Standard wholesale price to distributors | Price in USD |
| 31 | RecommendedRetailPriceUSD | DECIMAL(10,2) | Suggested retail price for dispensing | Price in USD |
| 32 | ProductStatus | VARCHAR(15) | Product lifecycle availability status | Active, Discontinued |
| 33 | EffectiveFromDate | DATE | Effective start date of current version | ISO YYYY-MM-DD |
| 34 | SourceSystem | VARCHAR(30) | Originating transactional system | PHARMACY_POS, ECOMM_STORE |
 
 ---
 
## 3. Dataset: 05_pharmacy_sales_data (45 Columns)
**Files in folder:** 05_pharmacy_sales_data__R01.csv, 05_pharmacy_sales_data__R02.csv  
**Granularity:** 1 row = 1 Retail, Hospital, or E-commerce Sales Transaction  
**Oversampling Behavior:** R01 generates 48,737 sales rows (seasonal factor 3.41x) with 243 corrupted rows. R02 generates 7,144 sales rows (seasonal factor 0.46x) with 35 corrupted rows.

| # | Column Name | Data Type | Description | Constraints & Business Rules |
| :--- | :--- | :--- | :--- | :--- |
| 1 | SalesTransactionID | VARCHAR(20) | Unique retail/hospital sales transaction ID | PK, format SALE-######### |
| 2 | SalesDate | DATE | Calendar date of sales transaction | ISO YYYY-MM-DD |
| 3 | SalesTimestampUTC | TIMESTAMP | Exact UTC transaction timestamp | ISO-8601 UTC timestamp |
| 4 | SalesChannel | VARCHAR(20) | Distribution sales channel | Physical Pharmacy, Ecommerce |
| 5 | PharmacyID | VARCHAR(10) | Dispensing pharmacy facility ID | FK to DimPharmacy, format PHR### |
| 6 | PharmacyGLN | CHAR(13) | Global Location Number of pharmacy store | 13-digit GS1 identifier |
| 7 | PharmacyName | VARCHAR(60) | Trading name of pharmacy outlet | Store name |
| 8 | PharmacyType | VARCHAR(25) | Classification of pharmacy store | Chain Pharmacy, Independent Pharmacy, Hospital Pharmacy |
| 9 | HospitalID | VARCHAR(10) | Associated hospital facility identifier | Nullable (for non-hospital stores) |
| 10 | PharmacyCity | VARCHAR(40) | City location of pharmacy store | Mapped to DimLocation |
| 11 | PharmacyState | CHAR(2) | State code of pharmacy store | US 2-letter state abbreviation |
| 12 | CountryCode | CHAR(2) | Country code of transaction | US |
| 13 | PharmacyOrderID | VARCHAR(15) | Upstream wholesale purchase order ID | Format PHO-####### |
| 14 | PharmacyDeliveryID | VARCHAR(15) | Logistics delivery dispatch ID | Format PHD-####### |
| 15 | PharmacyDeliveryDate | DATE | Actual date of shipment arrival at store | ISO YYYY-MM-DD |
| 16 | DeliveryQuantityPacks | INT | Total packs in wholesale delivery shipment | Shipment pack volume |
| 17 | DeliveryOTIFFlag | CHAR(1) | On-Time In-Full logistics fulfillment flag | Y or N |
| 18 | WarehouseLotID | VARCHAR(15) | Warehouse inventory storage lot ID | Traceability key, WHLOT-####### |
| 19 | SourceWarehouseID | VARCHAR(10) | Originating regional fulfillment warehouse ID | Format WH### |
| 20 | ProductionBatchID | VARCHAR(20) | Manufacturing production batch number | Batch lineage, format B##-PLT##-###### |
| 21 | MedicineID | VARCHAR(10) | Unique natural business identifier for medicine | PK, format MED### |
| 22 | GTIN14 | CHAR(14) | Global Trade Item Number barcode | 14-digit GS1 identifier |
| 23 | DiseaseCategory | VARCHAR(50) | Clinical therapeutic indication category | Diabetes, Oncology, etc. |
| 24 | GenericName | VARCHAR(60) | International non-proprietary drug name | Active pharmaceutical ingredient |
| 25 | BatchExpiryDate | DATE | Manufacturer labeled batch expiration date | ISO YYYY-MM-DD |
| 26 | DaysToExpiryAtSale | INT | Remaining days until expiration on sales date | Cold-chain shelf life metric |
| 27 | QuantitySoldPacks | INT | Number of packs sold in transaction | Measure: must be > 0 (checked by validation) |
| 28 | UnitRetailPriceUSD | DECIMAL(10,2) | Retail selling price per pack | Unit price in USD |
| 29 | GrossSalesAmountUSD | DECIMAL(12,2) | Gross sales value before discount | Quantity * UnitPrice |
| 30 | DiscountAmountUSD | DECIMAL(10,2) | Commercial discount or voucher deduction | Measure: >= 0 |
| 31 | NetSalesAmountUSD | DECIMAL(12,2) | Actual net revenue realized after discount | Measure: must be > 0 (checked by validation) |
| 32 | SalesTaxUSD | DECIMAL(10,2) | State and local sales tax collected | Tax in USD |
| 33 | CostOfGoodsSoldUSD | DECIMAL(12,2) | Total cost of goods sold for transaction | Measure: used for gross margin calculation |
| 34 | GrossMarginUSD | DECIMAL(12,2) | Realized gross margin in USD | NetSales - CostOfGoodsSold |
| 35 | PromotionCode | VARCHAR(20) | Applied marketing promotional campaign code | E.g., PROMO10, WELCOME, or NaN |
| 36 | PrescriptionRequiredFlag | CHAR(1) | Indicates if prescription was required | Y or N |
| 37 | PrescriptionID | VARCHAR(15) | Associated medical prescription reference ID | Format RX-######### or NaN |
| 38 | CustomerSegment | VARCHAR(25) | Patient demographic classification category | Adult acute care, Chronic care, Senior care |
| 39 | PayerType | VARCHAR(20) | Primary payment reimbursement source | Insurance, Cash, Government |
| 40 | PaymentMethod | VARCHAR(20) | Financial payment tender type | Card, Cash, Insurance claim |
| 41 | EcommerceDeliveryStatus | VARCHAR(20) | Status of home delivery for online sales | Delivered, In transit, Not applicable |
| 42 | ReturnFlag | CHAR(1) | Indicates whether transaction was returned | Y or N |
| 43 | ReturnedQuantityPacks | INT | Packs returned by patient/customer | Measure: defaults to 0 |
| 44 | SaleStatus | VARCHAR(20) | Lifecycle status of retail transaction | Completed, Returned, Cancelled |
| 45 | SourceSystem | VARCHAR(30) | Originating transactional system | PHARMACY_POS, ECOMM_STORE |
 
 ---
 
## 4. Dataset: 06_hospital_demand_data (41 Columns)
**Files in folder:** 06_hospital_demand_data__R01.csv, 06_hospital_demand_data__R02.csv  
**Granularity:** 1 row = 1 Hospital facility x 1 Medicine x 1 Month  
**Oversampling Behavior:** R01 and R02 each generate exactly 756 records (full grid of 12 hospitals x 63 medicines) with stochastic Gaussian variance (~6%) on forecast, requested, and consumed quantities.

| # | Column Name | Data Type | Description | Constraints & Business Rules |
| :--- | :--- | :--- | :--- | :--- |
| 1 | HospitalDemandRecordID | VARCHAR(15) | Unique monthly hospital demand record ID | PK, format HDEM-######## |
| 2 | DemandMonth | DATE | Target operational consumption month | ISO YYYY-MM-01 |
| 3 | HospitalID | VARCHAR(10) | Associated hospital facility identifier | Nullable (for non-hospital stores) |
| 4 | HospitalGLN | CHAR(13) | Global Location Number of medical center | 13-digit GS1 identifier |
| 5 | HospitalName | VARCHAR(60) | Official facility name of healthcare center | Facility name |
| 6 | HospitalType | VARCHAR(30) | Type and scope of healthcare institution | Academic Medical Center, Community Hospital |
| 7 | HospitalPharmacyID | VARCHAR(10) | Internal institutional pharmacy dispensing ID | Format PHR### |
| 8 | City | VARCHAR(40) | City location of hospital facility | Mapped to DimLocation |
| 9 | State | CHAR(2) | Two-letter US state code of hospital | US state code |
| 10 | CountryCode | CHAR(2) | Country code of transaction | US |
| 11 | LicensedBeds | SMALLINT | Total licensed in-patient bed capacity | Bed count >= 50 |
| 12 | ICUBeds | SMALLINT | Dedicated intensive care unit bed capacity | ICU bed count >= 10 |
| 13 | AverageOccupancyRatePct | SMALLINT | Monthly average bed occupancy percentage | 0 to 100 percentage |
| 14 | TraumaLevel | VARCHAR(10) | Designated emergency trauma capability level | Level I, Level II, Level III, Not rated |
| 15 | CatchmentPopulation | INT | Estimated population served by medical facility | Demographic catchment metric |
| 16 | MedicineID | VARCHAR(10) | Unique natural business identifier for medicine | PK, format MED### |
| 17 | GTIN14 | CHAR(14) | Global Trade Item Number barcode | 14-digit GS1 identifier |
| 18 | GenericName | VARCHAR(60) | International non-proprietary drug name | Active pharmaceutical ingredient |
| 19 | DiseaseCategory | VARCHAR(50) | Clinical therapeutic indication category | Diabetes, Oncology, etc. |
| 20 | ICD10Category | CHAR(7) | International classification of disease code | Format E11, J40-J47, etc. |
| 21 | EstimatedDiseaseCases | INT | Epidemiological estimated local disease cases | Clinical demand driver metric |
| 22 | DiseaseRelatedAdmissions | INT | Actual hospital admissions for indicated disease | In-patient clinical count |
| 23 | OutpatientEncounters | INT | Outpatient clinic consultations for condition | Outpatient encounter count |
| 24 | ForecastDemandPacks | INT | Statistical forecasted demand for month | Measure: predictive baseline packs |
| 25 | RequestedQuantityPacks | INT | Total medicine quantity ordered by hospital | Measure: must be >= 0 |
| 26 | ApprovedQuantityPacks | INT | Quantity approved by central pharmacy supply | Packs approved for distribution |
| 27 | ReceivedQuantityPacks | INT | Actual packs delivered to hospital dock | Physical packs received |
| 28 | EmergencyRequestQuantityPacks | INT | Emergency expedited requisition packs | Packs requested off-cycle |
| 29 | OpeningStockPacks | INT | Beginning-of-month hospital pharmacy stock | Initial physical inventory packs |
| 30 | DispensedQuantityPacks | INT | Packs issued to clinical floors/wards | Internal clinical distribution |
| 31 | ConsumedQuantityPacks | INT | Actual medicine packs administered to patients | Measure: actual hospital consumption |
| 32 | WastageQuantityPacks | INT | Packs spoiled, expired, or cold-chain damaged | Cold chain excursion wastage packs |
| 33 | ClosingStockPacks | INT | End-of-month remaining hospital stock | Semi-additive inventory measure |
| 34 | UnfulfilledDemandPacks | INT | Unmet hospital requisition shortfall | Measure: Requested - Consumed |
| 35 | StockoutDays | SMALLINT | Number of days facility experienced stockout | Clinical stockout duration days |
| 36 | ServiceLevelPct | SMALLINT | Fulfillment percentage of requested demand | Service level performance % |
| 37 | MedicationRequestStatus | VARCHAR(20) | Procurement fulfillment completion status | Completed, Partially Filled |
| 38 | FormularyStatus | VARCHAR(25) | Institutional drug formulary inclusion status | Formulary, Restricted, Non-formulary exception |
| 39 | AverageLeadTimeDays | SMALLINT | Average vendor delivery lead time in days | Procurement lead time in days |
| 40 | DemandTrendIndex | DECIMAL(6,3) | Relative demand index compared to baseline | Trend ratio metric |
| 41 | SourceSystem | VARCHAR(30) | Originating transactional system | PHARMACY_POS, ECOMM_STORE |
 
---