use crate::csv_bundle::CsvSerializable;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SourceRecord {
    pub source_id: String,
    pub source_family: String,
    pub provider: String,
    pub source_url: String,
    pub access_pattern: String,
    pub license_or_access_note: Option<String>,
    pub normalized_outputs: String,
    pub status: String,
    pub notes: Option<String>,
}

impl CsvSerializable for SourceRecord {
    fn header() -> &'static [&'static str] {
        &[
            "source_id",
            "source_family",
            "provider",
            "source_url",
            "access_pattern",
            "license_or_access_note",
            "normalized_outputs",
            "status",
            "notes",
        ]
    }

    fn row(&self) -> Vec<String> {
        vec![
            self.source_id.clone(),
            self.source_family.clone(),
            self.provider.clone(),
            self.source_url.clone(),
            self.access_pattern.clone(),
            self.license_or_access_note.clone().unwrap_or_default(),
            self.normalized_outputs.clone(),
            self.status.clone(),
            self.notes.clone().unwrap_or_default(),
        ]
    }
}

pub fn seed_source_catalog() -> Vec<SourceRecord> {
    vec![
        source(
            "cassini_space_for_water",
            "cassini_context",
            "EUSPA",
            "https://www.euspa.europa.eu/newsroom-events/events/cassini-hackathon-space-water",
            "manual",
            "public landing page",
            "source_manifest.csv",
            "reachable",
            "Hackathon programme context for EU Space for Water.",
        ),
        source(
            "copernicus_glofas_historical",
            "copernicus",
            "Copernicus Emergency Management Service",
            "https://ewds.climate.copernicus.eu/datasets/cems-glofas-historical",
            "cds_api_or_manual_download",
            "CDS/EWDS account may be required",
            "catchment_inflow module CSV",
            "planned",
            "Primary river discharge baseline for Nile river and reservoir nodes.",
        ),
        source(
            "era5_land",
            "copernicus",
            "Copernicus Climate Data Store",
            "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land-timeseries",
            "cds_api_or_manual_download",
            "CDS account and API credentials may be required",
            "catchment_inflow and evaporation module CSV",
            "planned",
            "Fallback hydrometeorology for runoff, precipitation, temperature, and evaporation.",
        ),
        source(
            "clms_evapotranspiration",
            "copernicus",
            "Copernicus Land Monitoring Service",
            "https://land.copernicus.eu/en/products/evapotranspiration",
            "cdse_or_manual_download",
            "public catalog; product access path to confirm",
            "evaporation and food_production module CSV",
            "planned",
            "Agricultural and reservoir evaporation proxy.",
        ),
        source(
            "clms_dynamic_land_cover",
            "copernicus",
            "Copernicus Land Monitoring Service",
            "https://land.copernicus.eu/en/products/global-dynamic-land-cover",
            "cdse_or_manual_download",
            "public catalog; product access path to confirm",
            "node_sources.csv and food_production module CSV",
            "planned",
            "Farmland masks and land-cover fractions for irrigation demand nodes.",
        ),
        source(
            "clms_water_bodies",
            "copernicus",
            "Copernicus Land Monitoring Service",
            "https://land.copernicus.eu/en/products/water-bodies",
            "cdse_or_manual_download",
            "public catalog; product access path to confirm",
            "reservoir_sources.csv",
            "planned",
            "Surface-water and reservoir extent sanity checks.",
        ),
        source(
            "fao_wapor",
            "supplemental",
            "FAO",
            "https://www.fao.org/in-action/remote-sensing-for-water-productivity/wapor-data/",
            "api_or_manual_download",
            "public service; API details to wire later",
            "food_production module CSV",
            "planned",
            "Crop water productivity and ET validation over Africa and Near East.",
        ),
        source(
            "fao_aquastat",
            "supplemental",
            "FAO",
            "https://www.fao.org/aquastat/en/overview/methodology/water-use/index.html",
            "manual_or_bulk_download",
            "public",
            "drink_water and food_production module CSV",
            "planned",
            "Country-level water withdrawals and irrigation calibration.",
        ),
        source(
            "nile_basin_information_systems",
            "supplemental",
            "Nile Basin Initiative",
            "https://nilebasin.org/nile-basin-information-systems",
            "manual",
            "public landing page; specific datasets may vary",
            "config.yaml reservoir and connection fields",
            "planned",
            "Nile-specific dams, water-quality, and basin reports.",
        ),
        source(
            "galileo_rinex_navigation",
            "galileo_gnss",
            "European GNSS Service Centre",
            "https://www.gsc-europa.eu/gsc-products/galileo-rinex-navigation-parameters",
            "manual_or_archive_download",
            "public documentation; archive path to wire later",
            "source_manifest.csv",
            "planned",
            "Galileo navigation parameter provenance.",
        ),
        source(
            "igs_mgex",
            "galileo_gnss",
            "International GNSS Service",
            "https://igs.org/mgex/data-products/",
            "archive_dry_run",
            "some archives may require Earthdata/CDDIS login",
            "station_sources.csv and source_manifest.csv",
            "planned",
            "Multi-GNSS observations including Galileo signals.",
        ),
        source(
            "cddis_gnss_daily",
            "galileo_gnss",
            "NASA CDDIS",
            "https://www.earthdata.nasa.gov/data/space-geodesy-techniques/gnss/daily-30-second-data-collection",
            "earthdata_authenticated_download",
            "Earthdata login likely required",
            "station_sources.csv and optional GNSS water-vapor staging",
            "planned",
            "Daily GNSS RINEX and possible tropospheric product access.",
        ),
    ]
}

fn source(
    source_id: &str,
    source_family: &str,
    provider: &str,
    source_url: &str,
    access_pattern: &str,
    license_or_access_note: &str,
    normalized_outputs: &str,
    status: &str,
    notes: &str,
) -> SourceRecord {
    SourceRecord {
        source_id: source_id.to_string(),
        source_family: source_family.to_string(),
        provider: provider.to_string(),
        source_url: source_url.to_string(),
        access_pattern: access_pattern.to_string(),
        license_or_access_note: Some(license_or_access_note.to_string()),
        normalized_outputs: normalized_outputs.to_string(),
        status: status.to_string(),
        notes: Some(notes.to_string()),
    }
}

#[cfg(test)]
mod tests {
    use super::seed_source_catalog;

    #[test]
    fn seed_catalog_contains_copernicus_and_galileo_sources() {
        let catalog = seed_source_catalog();
        assert!(
            catalog
                .iter()
                .any(|source| source.source_id == "copernicus_glofas_historical")
        );
        assert!(
            catalog
                .iter()
                .any(|source| source.source_family == "galileo_gnss")
        );
    }
}
