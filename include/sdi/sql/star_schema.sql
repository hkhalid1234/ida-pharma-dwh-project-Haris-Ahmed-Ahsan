-- SDI data mart (Fact Constellation, Phase 1) - DDL follows the Excel design (Dim.Tables / Fact.Table sheets).
-- Portable SQL: runs on DuckDB (production) and SQLite (unit tests).
CREATE TABLE IF NOT EXISTS DimDate (
  DateKey INT, FullDate DATE, Year SMALLINT, Quarter CHAR(2), MonthNumber TINYINT, MonthName VARCHAR(10),
  Day TINYINT, DayName VARCHAR(10), IsWeekend CHAR(1), Season VARCHAR(6));
CREATE TABLE IF NOT EXISTS DimLocation (
  LocationKey INT, City VARCHAR(40), StateCode CHAR(2), StateName VARCHAR(30), Region VARCHAR(15), Country VARCHAR(20));
CREATE TABLE IF NOT EXISTS DimMedicine (
  MedicineKey INT, MedicineID VARCHAR(10), InternalSKU VARCHAR(15), GTIN14 CHAR(14), MedName VARCHAR(60),
  BrandName VARCHAR(60), DiseaseCategory VARCHAR(50), ICD10Category CHAR(3), TherapeuticClass VARCHAR(50),
  DoseFormStrength VARCHAR(40), Route VARCHAR(20), PackSize SMALLINT, PrescriptionClass VARCHAR(20),
  ControlledFlag VARCHAR(15), ColdStorageFlag VARCHAR(15), ProductStatus VARCHAR(15),
  EffectiveFromDate DATE, EffectiveToDate DATE, IsCurrent CHAR(1));
CREATE TABLE IF NOT EXISTS DimPharmacy (
  PharmacyKey INT, PharmacyID VARCHAR(10), PharmacyGLN CHAR(13), PharmacyName VARCHAR(40), PharmacyType VARCHAR(15),
  HospitalID VARCHAR(10), LocationKey INT, EffectiveFromDate DATE, EffectiveToDate DATE, IsCurrent CHAR(1));
CREATE TABLE IF NOT EXISTS DimHospital (
  HospitalKey INT, HospitalID VARCHAR(10), HospitalGLN CHAR(13), HospitalName VARCHAR(60), HospitalType VARCHAR(30),
  HospitalPharmacyID VARCHAR(10), TraumaLevel VARCHAR(10), LicensedBeds SMALLINT, BedSizeBand VARCHAR(10),
  ICUBeds SMALLINT, OccupancyPct DECIMAL(5,2), CatchmentPopulation INT, LocationKey INT,
  EffectiveFromDate DATE, EffectiveToDate DATE, IsCurrent CHAR(1));
CREATE TABLE IF NOT EXISTS DimSalesJunk (
  SalesJunkKey INT, SalesChannel VARCHAR(15), CustomerSegment VARCHAR(25), PayerType VARCHAR(20),
  PaymentMethod VARCHAR(20), PromotionCode VARCHAR(12), RxRequired VARCHAR(15), ReturnFlag VARCHAR(15),
  SaleStatus VARCHAR(20), OnlineDeliveryStatus VARCHAR(20), ExpiryBand VARCHAR(20));
CREATE TABLE IF NOT EXISTS DimDemandJunk (
  DemandJunkKey INT, RequestStatus VARCHAR(20), ListStatus VARCHAR(25));
CREATE TABLE IF NOT EXISTS FactPharmacySales (
  SalesKey BIGINT, SalesDateKey INT, DeliveryDateKey INT, MedicineKey INT, PharmacyKey INT, SalesJunkKey INT,
  SalesTransactionID VARCHAR(20), PharmacyOrderID VARCHAR(15), PharmacyDeliveryID VARCHAR(15),
  PrescriptionID VARCHAR(15), WarehouseLotID VARCHAR(15), ProductionBatchID VARCHAR(20),
  QuantitySoldPacks INT, NetSalesAmount DECIMAL(12,2), DiscountAmount DECIMAL(12,2),
  CostOfGoodsSold DECIMAL(12,2), ReturnedQuantityPacks INT, BatchID VARCHAR(10));
CREATE TABLE IF NOT EXISTS FactHospitalDemand (
  DemandKey BIGINT, MonthDateKey INT, HospitalKey INT, MedicineKey INT, DemandJunkKey INT,
  HospitalDemandRecordID VARCHAR(15), ForecastDemandPacks INT, RequestedQuantityPacks INT,
  ConsumedQuantityPacks INT, UnfulfilledDemandPacks INT, ClosingStockPacks INT, BatchID VARCHAR(10));
CREATE TABLE IF NOT EXISTS EtlBatchLog (
  BatchID VARCHAR(10), LoadedAt VARCHAR(25), SalesRowsLoaded INT, DemandRowsLoaded INT,
  MedicineVersionsAdded INT, SalesRowsOrphaned INT, DemandRowsOrphaned INT);
