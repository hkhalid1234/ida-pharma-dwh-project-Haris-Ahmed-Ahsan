-- Analytical query catalogue. Each query exists in two variants:
--   base : star-join over the detailed fact tables (what a naive BI tool would send)
--   opt  : same answer from the pre-aggregated summary tables (query-optimisation layer)
-- Portable SQL (DuckDB + SQLite). Query ids match the 3 "solvable queries" of the Excel (Q1-Q3) plus dashboard KPIs (K4-K6).

-- name: Q1_region_month_channel_2025 | base
SELECT l.Region, d.MonthNumber, j.SalesChannel,
       SUM(f.NetSalesAmount) AS NetSales, SUM(f.QuantitySoldPacks) AS PacksSold
FROM FactPharmacySales f
JOIN DimDate d ON d.DateKey = f.SalesDateKey
JOIN DimPharmacy p ON p.PharmacyKey = f.PharmacyKey
JOIN DimLocation l ON l.LocationKey = p.LocationKey
JOIN DimSalesJunk j ON j.SalesJunkKey = f.SalesJunkKey
WHERE d.Year = 2025
GROUP BY l.Region, d.MonthNumber, j.SalesChannel
ORDER BY l.Region, d.MonthNumber, j.SalesChannel;

-- name: Q1_region_month_channel_2025 | opt
SELECT l.Region, a.MonthNumber, a.SalesChannel,
       SUM(a.NetSales) AS NetSales, SUM(a.PacksSold) AS PacksSold
FROM AggSalesMonthly a
JOIN DimLocation l ON l.LocationKey = a.LocationKey
WHERE a.Year = 2025
GROUP BY l.Region, a.MonthNumber, a.SalesChannel
ORDER BY l.Region, a.MonthNumber, a.SalesChannel;

-- name: Q2_forecast_vs_actual_category_quarter | base
SELECT m.DiseaseCategory, d.Year, d.Quarter,
       SUM(f.ForecastDemandPacks) AS ForecastPacks, SUM(f.ConsumedQuantityPacks) AS ConsumedPacks,
       SUM(f.ConsumedQuantityPacks) * 1.0 / SUM(f.ForecastDemandPacks) AS ActualToForecastRatio
FROM FactHospitalDemand f
JOIN DimDate d ON d.DateKey = f.MonthDateKey
JOIN DimMedicine m ON m.MedicineKey = f.MedicineKey
WHERE d.Year IN (2024, 2025)
GROUP BY m.DiseaseCategory, d.Year, d.Quarter
ORDER BY m.DiseaseCategory, d.Year, d.Quarter;

-- name: Q2_forecast_vs_actual_category_quarter | opt
SELECT m.DiseaseCategory, a.Year, a.Quarter,
       SUM(a.ForecastPacks) AS ForecastPacks, SUM(a.ConsumedPacks) AS ConsumedPacks,
       SUM(a.ConsumedPacks) * 1.0 / SUM(a.ForecastPacks) AS ActualToForecastRatio
FROM AggDemandMonthly a
JOIN DimMedicine m ON m.MedicineKey = a.MedicineKey
WHERE a.Year IN (2024, 2025)
GROUP BY m.DiseaseCategory, a.Year, a.Quarter
ORDER BY m.DiseaseCategory, a.Year, a.Quarter;

-- name: Q3_unfulfilled_city_medicine_2025 | base
SELECT l.City, m.MedName, SUM(h.UnfulfilledDemandPacks) AS UnfulfilledPacks,
       (SELECT SUM(s.QuantitySoldPacks)
          FROM FactPharmacySales s
          JOIN DimDate ds ON ds.DateKey = s.SalesDateKey
          JOIN DimPharmacy sp ON sp.PharmacyKey = s.PharmacyKey
          JOIN DimMedicine sm ON sm.MedicineKey = s.MedicineKey
         WHERE ds.Year = 2025 AND sp.LocationKey = l.LocationKey AND sm.MedicineID = m.MedicineID) AS StorePacksSold
FROM FactHospitalDemand h
JOIN DimDate d ON d.DateKey = h.MonthDateKey
JOIN DimHospital ho ON ho.HospitalKey = h.HospitalKey
JOIN DimLocation l ON l.LocationKey = ho.LocationKey
JOIN DimMedicine m ON m.MedicineKey = h.MedicineKey
WHERE d.Year = 2025
GROUP BY l.City, l.LocationKey, m.MedName, m.MedicineID
ORDER BY UnfulfilledPacks DESC, l.City, m.MedName
LIMIT 20;

-- name: Q3_unfulfilled_city_medicine_2025 | opt
SELECT l.City, m.MedName, SUM(u.UnfulfilledPacks) AS UnfulfilledPacks,
       (SELECT SUM(a.PacksSold) FROM AggSalesMonthly a
          JOIN DimMedicine sm ON sm.MedicineKey = a.MedicineKey
         WHERE a.Year = 2025 AND a.LocationKey = l.LocationKey AND sm.MedicineID = m.MedicineID) AS StorePacksSold
FROM AggDemandMonthly u
JOIN DimHospital ho ON ho.HospitalKey = u.HospitalKey
JOIN DimLocation l ON l.LocationKey = ho.LocationKey
JOIN DimMedicine m ON m.MedicineKey = u.MedicineKey
WHERE u.Year = 2025
GROUP BY l.City, l.LocationKey, m.MedName, m.MedicineID
ORDER BY UnfulfilledPacks DESC, l.City, m.MedName
LIMIT 20;

-- name: K4_channel_revenue_margin | base
SELECT j.SalesChannel, SUM(f.NetSalesAmount) AS NetSales,
       SUM(f.NetSalesAmount - f.CostOfGoodsSold) AS GrossMargin,
       (SUM(f.NetSalesAmount - f.CostOfGoodsSold) * 100.0) / SUM(f.NetSalesAmount) AS GrossMarginPct
FROM FactPharmacySales f JOIN DimSalesJunk j ON j.SalesJunkKey = f.SalesJunkKey
GROUP BY j.SalesChannel ORDER BY NetSales DESC;

-- name: K4_channel_revenue_margin | opt
SELECT a.SalesChannel, SUM(a.NetSales) AS NetSales,
       SUM(a.NetSales - a.Cogs) AS GrossMargin,
       (SUM(a.NetSales - a.Cogs) * 100.0) / SUM(a.NetSales) AS GrossMarginPct
FROM AggSalesMonthly a GROUP BY a.SalesChannel ORDER BY NetSales DESC;

-- name: K5_top_movers_by_class | base
SELECT m.TherapeuticClass, m.MedName, SUM(f.QuantitySoldPacks) AS PacksSold
FROM FactPharmacySales f JOIN DimMedicine m ON m.MedicineKey = f.MedicineKey
GROUP BY m.TherapeuticClass, m.MedName
ORDER BY PacksSold DESC, m.MedName LIMIT 10;

-- name: K5_top_movers_by_class | opt
SELECT m.TherapeuticClass, m.MedName, SUM(a.PacksSold) AS PacksSold
FROM AggSalesMonthly a JOIN DimMedicine m ON m.MedicineKey = a.MedicineKey
GROUP BY m.TherapeuticClass, m.MedName
ORDER BY PacksSold DESC, m.MedName LIMIT 10;

-- name: K6_service_level_by_hospital | base
SELECT ho.HospitalName, SUM(f.RequestedQuantityPacks) AS Requested, SUM(f.UnfulfilledDemandPacks) AS Unfulfilled,
       ((SUM(f.RequestedQuantityPacks) - SUM(f.UnfulfilledDemandPacks)) * 100.0) / SUM(f.RequestedQuantityPacks) AS ServiceLevelPct
FROM FactHospitalDemand f JOIN DimHospital ho ON ho.HospitalKey = f.HospitalKey
GROUP BY ho.HospitalName ORDER BY ServiceLevelPct, ho.HospitalName;

-- name: K6_service_level_by_hospital | opt
SELECT ho.HospitalName, SUM(a.RequestedPacks) AS Requested, SUM(a.UnfulfilledPacks) AS Unfulfilled,
       ((SUM(a.RequestedPacks) - SUM(a.UnfulfilledPacks)) * 100.0) / SUM(a.RequestedPacks) AS ServiceLevelPct
FROM AggDemandMonthly a JOIN DimHospital ho ON ho.HospitalKey = a.HospitalKey
GROUP BY ho.HospitalName ORDER BY ServiceLevelPct, ho.HospitalName;
