use std::{
    f64::consts::PI,
    fs,
    path::{Path, PathBuf},
};

use crate::{
    catalog::{SourceRecord, seed_source_catalog},
    csv_bundle::{CsvBundleWriter, CsvSerializable},
};

#[derive(Clone, Debug)]
pub struct SnapshotOptions {
    pub start_date: String,
    pub end_date: String,
    pub n_scenarios: usize,
}

impl Default for SnapshotOptions {
    fn default() -> Self {
        Self {
            start_date: "2020-01-01".to_string(),
            end_date: "2020-01-31".to_string(),
            n_scenarios: 3,
        }
    }
}

#[derive(Clone, Debug)]
struct GeneratedNode {
    id: &'static str,
    name: &'static str,
    country_code: &'static str,
    role: &'static str,
    lat: f64,
    lon: f64,
    reservoir_initial_m3: f64,
    reservoir_capacity_m3: f64,
    max_production_m3_day: f64,
    evaporation_m3_day: f64,
    drinking_m3_day: f64,
    food_water_coefficient: f64,
    food_units_day: f64,
    energy_price: f64,
    inflow_m3_day: f64,
    inflow_source_id: &'static str,
    evaporation_source_id: &'static str,
    demand_source_id: &'static str,
    reservoir_source_id: &'static str,
    connections: &'static [GeneratedConnection],
}

#[derive(Clone, Copy, Debug)]
struct GeneratedConnection {
    node_id: &'static str,
    fraction: f64,
    delay: u32,
}

#[derive(Clone, Debug)]
struct NodeSourceRecord {
    node_id: String,
    name: String,
    node_role: String,
    latitude: f64,
    longitude: f64,
    country_code: String,
    primary_discharge_source: String,
    primary_evaporation_source: String,
    primary_demand_source: String,
    primary_reservoir_source: String,
    confidence: String,
    notes: String,
}

impl CsvSerializable for NodeSourceRecord {
    fn header() -> &'static [&'static str] {
        &[
            "node_id",
            "name",
            "node_role",
            "latitude",
            "longitude",
            "country_code",
            "primary_discharge_source",
            "primary_evaporation_source",
            "primary_demand_source",
            "primary_reservoir_source",
            "confidence",
            "notes",
        ]
    }

    fn row(&self) -> Vec<String> {
        vec![
            self.node_id.clone(),
            self.name.clone(),
            self.node_role.clone(),
            self.latitude.to_string(),
            self.longitude.to_string(),
            self.country_code.clone(),
            self.primary_discharge_source.clone(),
            self.primary_evaporation_source.clone(),
            self.primary_demand_source.clone(),
            self.primary_reservoir_source.clone(),
            self.confidence.clone(),
            self.notes.clone(),
        ]
    }
}

pub fn write_seed_snapshot(
    output_dir: impl AsRef<Path>,
    options: &SnapshotOptions,
) -> Result<Vec<PathBuf>, Box<dyn std::error::Error>> {
    if options.n_scenarios == 0 {
        return Err("n_scenarios must be at least 1".into());
    }

    let dates = date_range(&options.start_date, &options.end_date)?;
    let output_dir = output_dir.as_ref();
    let modules_dir = output_dir.join("modules");
    let staging_dir = output_dir.join("staging");
    fs::create_dir_all(&modules_dir)?;
    fs::create_dir_all(&staging_dir)?;

    let nodes = seed_nodes();
    let mut outputs = vec![
        CsvBundleWriter::write_csv(
            staging_dir.join("source_catalog.csv"),
            &seed_source_catalog(),
        )?,
        CsvBundleWriter::write_csv(staging_dir.join("source_manifest.csv"), &source_manifest())?,
        CsvBundleWriter::write_csv(
            staging_dir.join("node_sources.csv"),
            &node_source_records(&nodes),
        )?,
        CsvBundleWriter::write_csv(
            staging_dir.join("galileo_gnss_archive_urls.csv"),
            &galileo_archive_url_records(&dates),
        )?,
    ];

    for node in &nodes {
        outputs.push(write_module_csv(
            &modules_dir,
            node.id,
            "catchment_inflow",
            node.inflow_m3_day,
            &dates,
            options.n_scenarios,
            SeasonalShape::WetSeason,
        )?);
        outputs.push(write_module_csv(
            &modules_dir,
            node.id,
            "evaporation",
            node.evaporation_m3_day,
            &dates,
            options.n_scenarios,
            SeasonalShape::DrySeason,
        )?);
        outputs.push(write_module_csv(
            &modules_dir,
            node.id,
            "drink_water",
            node.drinking_m3_day,
            &dates,
            options.n_scenarios,
            SeasonalShape::Flat,
        )?);
        outputs.push(write_module_csv(
            &modules_dir,
            node.id,
            "food_production",
            node.food_units_day,
            &dates,
            options.n_scenarios,
            SeasonalShape::CropSeason,
        )?);
        outputs.push(write_module_csv(
            &modules_dir,
            node.id,
            "energy",
            node.energy_price,
            &dates,
            options.n_scenarios,
            SeasonalShape::Flat,
        )?);
    }

    let config_path = output_dir.join("config.yaml");
    fs::write(&config_path, render_config(&nodes))?;
    outputs.push(config_path);

    Ok(outputs)
}

fn source_manifest() -> Vec<SourceRecord> {
    seed_source_catalog()
        .into_iter()
        .map(|mut source| {
            if source.status == "planned" {
                source.status = "dry_run".to_string();
            }
            source
        })
        .collect()
}

fn node_source_records(nodes: &[GeneratedNode]) -> Vec<NodeSourceRecord> {
    nodes
        .iter()
        .map(|node| NodeSourceRecord {
            node_id: node.id.to_string(),
            name: node.name.to_string(),
            node_role: node.role.to_string(),
            latitude: node.lat,
            longitude: node.lon,
            country_code: node.country_code.to_string(),
            primary_discharge_source: node.inflow_source_id.to_string(),
            primary_evaporation_source: node.evaporation_source_id.to_string(),
            primary_demand_source: node.demand_source_id.to_string(),
            primary_reservoir_source: node.reservoir_source_id.to_string(),
            confidence: "seed_assumption".to_string(),
            notes: "Curated hackathon seed; replace module CSVs source-by-source.".to_string(),
        })
        .collect()
}

#[derive(Clone, Debug)]
struct GalileoArchiveUrlRecord {
    date: String,
    source_id: String,
    product: String,
    url: String,
    access_note: String,
    status: String,
}

impl CsvSerializable for GalileoArchiveUrlRecord {
    fn header() -> &'static [&'static str] {
        &[
            "date",
            "source_id",
            "product",
            "url",
            "access_note",
            "status",
        ]
    }

    fn row(&self) -> Vec<String> {
        vec![
            self.date.clone(),
            self.source_id.clone(),
            self.product.clone(),
            self.url.clone(),
            self.access_note.clone(),
            self.status.clone(),
        ]
    }
}

fn galileo_archive_url_records(dates: &[SimpleDate]) -> Vec<GalileoArchiveUrlRecord> {
    let mut records = Vec::with_capacity(dates.len() * 2);

    for date in dates {
        records.push(GalileoArchiveUrlRecord {
            date: date.to_string(),
            source_id: "cddis_gnss_daily".to_string(),
            product: "brdc_merged_rinex3_navigation".to_string(),
            url: brdc_navigation_url(*date),
            access_note: "Dry-run URL. CDDIS downloads usually require Earthdata login."
                .to_string(),
            status: "planned".to_string(),
        });
        records.push(GalileoArchiveUrlRecord {
            date: date.to_string(),
            source_id: "igs_mgex".to_string(),
            product: "troposphere_zpd_directory".to_string(),
            url: format!(
                "https://cddis.nasa.gov/archive/gnss/products/troposphere/zpd/{}/",
                date.year
            ),
            access_note:
                "Dry-run directory. Normalize ZPD after station/product availability is confirmed."
                    .to_string(),
            status: "planned".to_string(),
        });
    }

    records
}

fn brdc_navigation_url(date: SimpleDate) -> String {
    let year = date.year;
    let day_of_year = date.day_of_year();
    let short_year = year.rem_euclid(100);
    format!(
        "https://cddis.nasa.gov/archive/gnss/data/daily/{year}/{day_of_year:03}/{short_year:02}p/BRDC00IGS_R_{year}{day_of_year:03}0000_01D_MN.rnx.gz"
    )
}

fn render_config(nodes: &[GeneratedNode]) -> String {
    let mut yaml = String::from("settings:\n  timestep_days: 1.0\n\nnodes:\n");

    for node in nodes {
        yaml.push_str(&format!(
            "  - id: {}\n    reservoir:\n      initial_level: {:.3}\n      max_capacity: {:.3}\n    max_production: {:.3}\n    catchment_inflow:\n      type: csv\n      filepath: modules/{}.catchment_inflow.csv\n      column: scenario_1\n    connections:\n",
            node.id,
            node.reservoir_initial_m3,
            node.reservoir_capacity_m3,
            node.max_production_m3_day,
            node.id
        ));

        if node.connections.is_empty() {
            yaml.push_str("      []\n");
        } else {
            for connection in node.connections {
                yaml.push_str(&format!(
                    "      - node_id: {}\n        fraction: {:.3}\n        delay: {}\n",
                    connection.node_id, connection.fraction, connection.delay
                ));
            }
        }

        yaml.push_str(&format!(
            "    modules:\n      evaporation:\n        type: csv\n        filepath: modules/{}.evaporation.csv\n        column: scenario_1\n      drink_water:\n        type: csv\n        filepath: modules/{}.drink_water.csv\n        column: scenario_1\n      food_production:\n        type: csv\n        filepath: modules/{}.food_production.csv\n        column: scenario_1\n        water_coefficient: {:.6}\n      energy:\n        type: csv\n        filepath: modules/{}.energy.csv\n        column: scenario_1\n",
            node.id, node.id, node.id, node.food_water_coefficient, node.id
        ));
    }

    yaml
}

#[derive(Clone, Copy, Debug)]
enum SeasonalShape {
    CropSeason,
    DrySeason,
    Flat,
    WetSeason,
}

fn write_module_csv(
    modules_dir: &Path,
    node_id: &str,
    module_name: &str,
    baseline: f64,
    dates: &[SimpleDate],
    n_scenarios: usize,
    shape: SeasonalShape,
) -> Result<PathBuf, std::io::Error> {
    let path = modules_dir.join(format!("{node_id}.{module_name}.csv"));
    let mut contents = String::from("date");
    for scenario_index in 1..=n_scenarios {
        contents.push_str(&format!(",scenario_{scenario_index}"));
    }
    contents.push('\n');

    for (day_index, date) in dates.iter().enumerate() {
        contents.push_str(&date.to_string());
        let seasonal = seasonal_multiplier(day_index, shape);
        for scenario_index in 0..n_scenarios {
            let scenario_multiplier = match scenario_index {
                0 => 1.0,
                1 => 0.82,
                2 => 1.18,
                extra => 1.0 + ((extra as f64 - 1.0) * 0.05),
            };
            contents.push_str(&format!(
                ",{:.6}",
                (baseline * seasonal * scenario_multiplier).max(0.0)
            ));
        }
        contents.push('\n');
    }

    fs::write(&path, contents)?;
    Ok(path)
}

fn seasonal_multiplier(day_index: usize, shape: SeasonalShape) -> f64 {
    let phase = (day_index as f64 / 365.0) * 2.0 * PI;
    match shape {
        SeasonalShape::CropSeason => 0.75 + 0.25 * (phase - 0.7).sin().max(0.0),
        SeasonalShape::DrySeason => 0.85 + 0.25 * (phase + 1.2).sin().max(0.0),
        SeasonalShape::Flat => 1.0,
        SeasonalShape::WetSeason => 0.8 + 0.35 * phase.sin().max(0.0),
    }
}

fn seed_nodes() -> Vec<GeneratedNode> {
    const VICTORIA_CONNECTIONS: &[GeneratedConnection] = &[GeneratedConnection {
        node_id: "sudd_wetland",
        fraction: 1.0,
        delay: 7,
    }];
    const SUDD_CONNECTIONS: &[GeneratedConnection] = &[GeneratedConnection {
        node_id: "khartoum",
        fraction: 0.55,
        delay: 14,
    }];
    const GERD_CONNECTIONS: &[GeneratedConnection] = &[GeneratedConnection {
        node_id: "khartoum",
        fraction: 1.0,
        delay: 5,
    }];
    const KHARTOUM_CONNECTIONS: &[GeneratedConnection] = &[GeneratedConnection {
        node_id: "aswan",
        fraction: 1.0,
        delay: 10,
    }];
    const ASWAN_CONNECTIONS: &[GeneratedConnection] = &[GeneratedConnection {
        node_id: "nile_delta",
        fraction: 1.0,
        delay: 4,
    }];
    const DELTA_CONNECTIONS: &[GeneratedConnection] = &[];

    vec![
        GeneratedNode {
            id: "lake_victoria_outlet",
            name: "Lake Victoria Outlet",
            country_code: "UGA",
            role: "source_reservoir",
            lat: 0.42,
            lon: 33.19,
            reservoir_initial_m3: 30_000_000_000.0,
            reservoir_capacity_m3: 70_000_000_000.0,
            max_production_m3_day: 12_000_000.0,
            evaporation_m3_day: 1_500_000.0,
            drinking_m3_day: 120_000.0,
            food_water_coefficient: 1_200.0,
            food_units_day: 1_000.0,
            energy_price: 0.02,
            inflow_m3_day: 8_500_000.0,
            inflow_source_id: "copernicus_glofas_historical",
            evaporation_source_id: "era5_land",
            demand_source_id: "fao_aquastat",
            reservoir_source_id: "nile_basin_information_systems",
            connections: VICTORIA_CONNECTIONS,
        },
        GeneratedNode {
            id: "sudd_wetland",
            name: "Sudd Wetland",
            country_code: "SSD",
            role: "wetland_reach",
            lat: 7.5,
            lon: 30.5,
            reservoir_initial_m3: 5_000_000_000.0,
            reservoir_capacity_m3: 20_000_000_000.0,
            max_production_m3_day: 9_000_000.0,
            evaporation_m3_day: 4_000_000.0,
            drinking_m3_day: 80_000.0,
            food_water_coefficient: 1_400.0,
            food_units_day: 800.0,
            energy_price: 0.0,
            inflow_m3_day: 1_500_000.0,
            inflow_source_id: "era5_land",
            evaporation_source_id: "clms_evapotranspiration",
            demand_source_id: "fao_aquastat",
            reservoir_source_id: "clms_water_bodies",
            connections: SUDD_CONNECTIONS,
        },
        GeneratedNode {
            id: "gerd",
            name: "Grand Ethiopian Renaissance Dam",
            country_code: "ETH",
            role: "reservoir_hydropower",
            lat: 11.22,
            lon: 35.09,
            reservoir_initial_m3: 30_000_000_000.0,
            reservoir_capacity_m3: 74_000_000_000.0,
            max_production_m3_day: 45_000_000.0,
            evaporation_m3_day: 2_700_000.0,
            drinking_m3_day: 100_000.0,
            food_water_coefficient: 1_100.0,
            food_units_day: 1_200.0,
            energy_price: 0.045,
            inflow_m3_day: 14_500_000.0,
            inflow_source_id: "copernicus_glofas_historical",
            evaporation_source_id: "era5_land",
            demand_source_id: "fao_aquastat",
            reservoir_source_id: "nile_basin_information_systems",
            connections: GERD_CONNECTIONS,
        },
        GeneratedNode {
            id: "khartoum",
            name: "Khartoum Demand and Confluence",
            country_code: "SDN",
            role: "city_irrigation_confluence",
            lat: 15.60,
            lon: 32.53,
            reservoir_initial_m3: 1_000_000_000.0,
            reservoir_capacity_m3: 5_000_000_000.0,
            max_production_m3_day: 20_000_000.0,
            evaporation_m3_day: 650_000.0,
            drinking_m3_day: 900_000.0,
            food_water_coefficient: 950.0,
            food_units_day: 18_000.0,
            energy_price: 0.01,
            inflow_m3_day: 1_000_000.0,
            inflow_source_id: "era5_land",
            evaporation_source_id: "clms_evapotranspiration",
            demand_source_id: "fao_aquastat",
            reservoir_source_id: "nile_basin_information_systems",
            connections: KHARTOUM_CONNECTIONS,
        },
        GeneratedNode {
            id: "aswan",
            name: "Aswan High Dam / Lake Nasser",
            country_code: "EGY",
            role: "reservoir_hydropower",
            lat: 23.97,
            lon: 32.88,
            reservoir_initial_m3: 100_000_000_000.0,
            reservoir_capacity_m3: 162_000_000_000.0,
            max_production_m3_day: 55_000_000.0,
            evaporation_m3_day: 7_000_000.0,
            drinking_m3_day: 300_000.0,
            food_water_coefficient: 850.0,
            food_units_day: 35_000.0,
            energy_price: 0.040,
            inflow_m3_day: 500_000.0,
            inflow_source_id: "copernicus_glofas_historical",
            evaporation_source_id: "era5_land",
            demand_source_id: "fao_aquastat",
            reservoir_source_id: "nile_basin_information_systems",
            connections: ASWAN_CONNECTIONS,
        },
        GeneratedNode {
            id: "nile_delta",
            name: "Nile Delta Agriculture and Municipal Demand",
            country_code: "EGY",
            role: "delta_demand_sink",
            lat: 31.5,
            lon: 31.5,
            reservoir_initial_m3: 500_000_000.0,
            reservoir_capacity_m3: 3_000_000_000.0,
            max_production_m3_day: 15_000_000.0,
            evaporation_m3_day: 450_000.0,
            drinking_m3_day: 4_000_000.0,
            food_water_coefficient: 780.0,
            food_units_day: 65_000.0,
            energy_price: 0.0,
            inflow_m3_day: 250_000.0,
            inflow_source_id: "era5_land",
            evaporation_source_id: "clms_evapotranspiration",
            demand_source_id: "fao_aquastat",
            reservoir_source_id: "clms_water_bodies",
            connections: DELTA_CONNECTIONS,
        },
    ]
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct SimpleDate {
    year: i32,
    month: u32,
    day: u32,
}

impl SimpleDate {
    fn parse(value: &str) -> Result<Self, String> {
        let parts = value.split('-').collect::<Vec<_>>();
        if parts.len() != 3 {
            return Err(format!("invalid date `{value}`, expected YYYY-MM-DD"));
        }
        let year = parts[0]
            .parse::<i32>()
            .map_err(|_| format!("invalid year in `{value}`"))?;
        let month = parts[1]
            .parse::<u32>()
            .map_err(|_| format!("invalid month in `{value}`"))?;
        let day = parts[2]
            .parse::<u32>()
            .map_err(|_| format!("invalid day in `{value}`"))?;
        let date = Self { year, month, day };
        if !date.is_valid() {
            return Err(format!("invalid calendar date `{value}`"));
        }
        Ok(date)
    }

    fn is_valid(&self) -> bool {
        self.month >= 1 && self.month <= 12 && self.day >= 1 && self.day <= days_in_month(*self)
    }

    fn next_day(self) -> Self {
        if self.day < days_in_month(self) {
            return Self {
                day: self.day + 1,
                ..self
            };
        }
        if self.month < 12 {
            return Self {
                month: self.month + 1,
                day: 1,
                ..self
            };
        }
        Self {
            year: self.year + 1,
            month: 1,
            day: 1,
        }
    }

    fn day_of_year(&self) -> u32 {
        (1..self.month)
            .map(|month| {
                days_in_month(Self {
                    year: self.year,
                    month,
                    day: 1,
                })
            })
            .sum::<u32>()
            + self.day
    }
}

impl std::fmt::Display for SimpleDate {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            formatter,
            "{:04}-{:02}-{:02}",
            self.year, self.month, self.day
        )
    }
}

fn date_range(start: &str, end: &str) -> Result<Vec<SimpleDate>, Box<dyn std::error::Error>> {
    let start = SimpleDate::parse(start)?;
    let end = SimpleDate::parse(end)?;
    if date_key(start) > date_key(end) {
        return Err("start_date must be before or equal to end_date".into());
    }

    let mut dates = Vec::new();
    let mut current = start;
    while date_key(current) <= date_key(end) {
        dates.push(current);
        current = current.next_day();
    }
    Ok(dates)
}

fn date_key(date: SimpleDate) -> i32 {
    date.year * 10_000 + date.month as i32 * 100 + date.day as i32
}

fn days_in_month(date: SimpleDate) -> u32 {
    match date.month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 if is_leap_year(date.year) => 29,
        2 => 28,
        _ => 0,
    }
}

fn is_leap_year(year: i32) -> bool {
    (year % 4 == 0 && year % 100 != 0) || year % 400 == 0
}

#[cfg(test)]
mod tests {
    use super::{SnapshotOptions, write_seed_snapshot};
    use nrsm_sim_core::{Scenario, simulate};

    #[test]
    fn writes_seed_snapshot_for_markdown_simulator_contract() {
        let unique = format!(
            "nrsm-node-snapshot-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("system time should be after epoch")
                .as_nanos()
        );
        let dir = std::env::temp_dir().join(unique);
        let outputs = write_seed_snapshot(
            &dir,
            &SnapshotOptions {
                start_date: "2020-02-28".to_string(),
                end_date: "2020-03-01".to_string(),
                n_scenarios: 3,
            },
        )
        .expect("snapshot should be written");

        assert!(outputs.iter().any(|path| path.ends_with("config.yaml")));
        assert!(dir.join("config.yaml").exists());
        assert!(
            dir.join("modules")
                .join("gerd.catchment_inflow.csv")
                .exists()
        );
        assert!(dir.join("staging").join("source_catalog.csv").exists());
        let galileo_urls =
            std::fs::read_to_string(dir.join("staging").join("galileo_gnss_archive_urls.csv"))
                .expect("galileo archive URL staging should be readable");
        assert!(galileo_urls.contains("BRDC00IGS_R_20200590000_01D_MN.rnx.gz"));
        let inflow = std::fs::read_to_string(dir.join("modules").join("gerd.catchment_inflow.csv"))
            .expect("inflow csv should be readable");
        assert!(inflow.starts_with("date,scenario_1,scenario_2,scenario_3\n"));
        assert!(inflow.contains("2020-02-29"));

        std::fs::remove_dir_all(&dir).expect("temporary directory should be removed");
    }

    #[test]
    fn generated_seed_snapshot_simulates_without_manual_fixes() {
        let unique = format!(
            "nrsm-node-snapshot-sim-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("system time should be after epoch")
                .as_nanos()
        );
        let dir = std::env::temp_dir().join(unique);
        write_seed_snapshot(
            &dir,
            &SnapshotOptions {
                start_date: "2020-01-01".to_string(),
                end_date: "2020-01-03".to_string(),
                n_scenarios: 2,
            },
        )
        .expect("snapshot should be written");

        let config = std::fs::read_to_string(dir.join("config.yaml"))
            .expect("generated config should be readable");
        let mut scenario: Scenario =
            serde_yaml::from_str(&config).expect("generated config should parse");
        scenario
            .load_module_csvs(&dir)
            .expect("generated module CSVs should load");

        let result = simulate(&scenario).expect("generated snapshot should simulate");

        assert_eq!(result.periods.len(), 3);
        assert_eq!(result.periods[0].node_results.len(), scenario.nodes.len());
        assert!(result.summary.total_inflow > 0.0);
        assert!(result.summary.total_production_release > 0.0);

        std::fs::remove_dir_all(&dir).expect("temporary directory should be removed");
    }
}
