-- OLAP indexing strategy (matches Fact.Table sheet of the Excel). Rebuilt after every load.
CREATE INDEX IF NOT EXISTS ix_fps_date     ON FactPharmacySales (SalesDateKey);
CREATE INDEX IF NOT EXISTS ix_fps_medicine ON FactPharmacySales (MedicineKey);
CREATE INDEX IF NOT EXISTS ix_fps_pharmacy ON FactPharmacySales (PharmacyKey);
CREATE INDEX IF NOT EXISTS ix_fps_junk     ON FactPharmacySales (SalesJunkKey);
CREATE INDEX IF NOT EXISTS ix_fps_txn      ON FactPharmacySales (SalesTransactionID);
CREATE INDEX IF NOT EXISTS ix_fhd_month    ON FactHospitalDemand (MonthDateKey, HospitalKey, MedicineKey);
CREATE INDEX IF NOT EXISTS ix_fhd_hospital ON FactHospitalDemand (HospitalKey);
CREATE INDEX IF NOT EXISTS ix_fhd_medicine ON FactHospitalDemand (MedicineKey);
CREATE INDEX IF NOT EXISTS ix_dd_year      ON DimDate (Year, Quarter, MonthNumber);
CREATE INDEX IF NOT EXISTS ix_aggs_year    ON AggSalesMonthly (Year, LocationKey);
CREATE INDEX IF NOT EXISTS ix_aggd_year    ON AggDemandMonthly (Year, HospitalKey);
