-- Pre-aggregated summary tables (DuckDB has no materialised views, so we materialise explicitly
-- and rebuild them after every load). Grain is fine enough to answer Q1-Q3 and K4-K6 without touching facts.
DROP TABLE IF EXISTS AggSalesMonthly;
CREATE TABLE AggSalesMonthly AS
SELECT d.Year AS Year, d.Quarter AS Quarter, d.MonthNumber AS MonthNumber, (CAST(d.Year AS INTEGER) * 100 + d.MonthNumber) AS YearMonth,
       p.LocationKey AS LocationKey, f.MedicineKey AS MedicineKey, j.SalesChannel AS SalesChannel,
       SUM(f.NetSalesAmount) AS NetSales, SUM(f.CostOfGoodsSold) AS Cogs, SUM(f.DiscountAmount) AS Discount,
       SUM(f.QuantitySoldPacks) AS PacksSold, SUM(f.ReturnedQuantityPacks) AS PacksReturned, COUNT(*) AS Transactions
FROM FactPharmacySales f
JOIN DimDate d ON d.DateKey = f.SalesDateKey
JOIN DimPharmacy p ON p.PharmacyKey = f.PharmacyKey
JOIN DimSalesJunk j ON j.SalesJunkKey = f.SalesJunkKey
GROUP BY d.Year, d.Quarter, d.MonthNumber, p.LocationKey, f.MedicineKey, j.SalesChannel;

DROP TABLE IF EXISTS AggDemandMonthly;
CREATE TABLE AggDemandMonthly AS
SELECT d.Year AS Year, d.Quarter AS Quarter, d.MonthNumber AS MonthNumber, (CAST(d.Year AS INTEGER) * 100 + d.MonthNumber) AS YearMonth,
       f.HospitalKey AS HospitalKey, f.MedicineKey AS MedicineKey,
       SUM(f.ForecastDemandPacks) AS ForecastPacks, SUM(f.RequestedQuantityPacks) AS RequestedPacks,
       SUM(f.ConsumedQuantityPacks) AS ConsumedPacks, SUM(f.UnfulfilledDemandPacks) AS UnfulfilledPacks,
       SUM(f.ClosingStockPacks) AS ClosingStockPacks
FROM FactHospitalDemand f
JOIN DimDate d ON d.DateKey = f.MonthDateKey
GROUP BY d.Year, d.Quarter, d.MonthNumber, f.HospitalKey, f.MedicineKey;
