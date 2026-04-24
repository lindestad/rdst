use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::csv_bundle::{CsvBundleWriter, CsvSerializable};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NodeKind {
    River,
    Reservoir,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EntityType {
    Node,
    Edge,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct NodeRecord {
    pub scenario_id: String,
    pub node_id: String,
    pub name: String,
    pub node_kind: NodeKind,
    pub latitude: Option<f64>,
    pub longitude: Option<f64>,
    pub country_code: Option<String>,
    pub subbasin_id: Option<String>,
    pub reservoir_capacity_million_m3: Option<f64>,
    pub reservoir_min_storage_million_m3: Option<f64>,
    pub initial_storage_million_m3: Option<f64>,
    pub food_per_unit_water: Option<f64>,
    pub energy_per_unit_water: Option<f64>,
    pub notes: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct EdgeRecord {
    pub scenario_id: String,
    pub edge_id: String,
    pub from_node_id: String,
    pub to_node_id: String,
    pub flow_share: f64,
    pub default_loss_fraction: f64,
    pub travel_time_days: Option<f64>,
    pub notes: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct TimeSeriesRecord {
    pub scenario_id: String,
    pub entity_type: EntityType,
    pub entity_id: String,
    pub metric: String,
    pub interval_start: String,
    pub interval_end: String,
    pub value: f64,
    pub unit: String,
    pub source_name: String,
    pub source_url: Option<String>,
    pub transform: Option<String>,
    pub quality_flag: Option<String>,
}

#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct NormalizedDataset {
    pub nodes: Vec<NodeRecord>,
    pub edges: Vec<EdgeRecord>,
    pub time_series: Vec<TimeSeriesRecord>,
}

impl NormalizedDataset {
    pub fn write_csv_bundle(
        &self,
        output_dir: impl AsRef<Path>,
    ) -> Result<Vec<PathBuf>, std::io::Error> {
        let output_dir = output_dir.as_ref();
        let nodes = CsvBundleWriter::write_csv(output_dir.join("nodes.csv"), &self.nodes)?;
        let edges = CsvBundleWriter::write_csv(output_dir.join("edges.csv"), &self.edges)?;
        let time_series =
            CsvBundleWriter::write_csv(output_dir.join("time_series.csv"), &self.time_series)?;

        Ok(vec![nodes, edges, time_series])
    }
}

impl CsvSerializable for NodeRecord {
    fn header() -> &'static [&'static str] {
        &[
            "scenario_id",
            "node_id",
            "name",
            "node_kind",
            "latitude",
            "longitude",
            "country_code",
            "subbasin_id",
            "reservoir_capacity_million_m3",
            "reservoir_min_storage_million_m3",
            "initial_storage_million_m3",
            "food_per_unit_water",
            "energy_per_unit_water",
            "notes",
        ]
    }

    fn row(&self) -> Vec<String> {
        vec![
            self.scenario_id.clone(),
            self.node_id.clone(),
            self.name.clone(),
            match self.node_kind {
                NodeKind::River => "river".to_string(),
                NodeKind::Reservoir => "reservoir".to_string(),
            },
            optional_f64(self.latitude),
            optional_f64(self.longitude),
            optional_string(&self.country_code),
            optional_string(&self.subbasin_id),
            optional_f64(self.reservoir_capacity_million_m3),
            optional_f64(self.reservoir_min_storage_million_m3),
            optional_f64(self.initial_storage_million_m3),
            optional_f64(self.food_per_unit_water),
            optional_f64(self.energy_per_unit_water),
            optional_string(&self.notes),
        ]
    }
}

impl CsvSerializable for EdgeRecord {
    fn header() -> &'static [&'static str] {
        &[
            "scenario_id",
            "edge_id",
            "from_node_id",
            "to_node_id",
            "flow_share",
            "default_loss_fraction",
            "travel_time_days",
            "notes",
        ]
    }

    fn row(&self) -> Vec<String> {
        vec![
            self.scenario_id.clone(),
            self.edge_id.clone(),
            self.from_node_id.clone(),
            self.to_node_id.clone(),
            self.flow_share.to_string(),
            self.default_loss_fraction.to_string(),
            optional_f64(self.travel_time_days),
            optional_string(&self.notes),
        ]
    }
}

impl CsvSerializable for TimeSeriesRecord {
    fn header() -> &'static [&'static str] {
        &[
            "scenario_id",
            "entity_type",
            "entity_id",
            "metric",
            "interval_start",
            "interval_end",
            "value",
            "unit",
            "source_name",
            "source_url",
            "transform",
            "quality_flag",
        ]
    }

    fn row(&self) -> Vec<String> {
        vec![
            self.scenario_id.clone(),
            match self.entity_type {
                EntityType::Node => "node".to_string(),
                EntityType::Edge => "edge".to_string(),
            },
            self.entity_id.clone(),
            self.metric.clone(),
            self.interval_start.clone(),
            self.interval_end.clone(),
            self.value.to_string(),
            self.unit.clone(),
            self.source_name.clone(),
            optional_string(&self.source_url),
            optional_string(&self.transform),
            optional_string(&self.quality_flag),
        ]
    }
}

fn optional_string(value: &Option<String>) -> String {
    value.clone().unwrap_or_default()
}

fn optional_f64(value: Option<f64>) -> String {
    value.map(|value| value.to_string()).unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::{EntityType, NodeKind, NodeRecord, NormalizedDataset, TimeSeriesRecord};

    #[test]
    fn bundle_writer_creates_expected_files() {
        let unique = format!(
            "nrsm-normalized-dataset-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("system time should be after epoch")
                .as_nanos()
        );
        let dir = std::env::temp_dir().join(unique);

        let dataset = NormalizedDataset {
            nodes: vec![NodeRecord {
                scenario_id: "nile-mvp".to_string(),
                node_id: "gerd".to_string(),
                name: "GERD".to_string(),
                node_kind: NodeKind::Reservoir,
                latitude: Some(11.21),
                longitude: Some(35.09),
                country_code: Some("ETH".to_string()),
                subbasin_id: Some("nile_blue_01".to_string()),
                reservoir_capacity_million_m3: Some(74000.0),
                reservoir_min_storage_million_m3: Some(10000.0),
                initial_storage_million_m3: Some(30000.0),
                food_per_unit_water: None,
                energy_per_unit_water: Some(0.62),
                notes: Some("seed assumptions".to_string()),
            }],
            edges: vec![],
            time_series: vec![TimeSeriesRecord {
                scenario_id: "nile-mvp".to_string(),
                entity_type: EntityType::Node,
                entity_id: "gerd".to_string(),
                metric: "local_inflow_million_m3_per_day".to_string(),
                interval_start: "2025-01-01".to_string(),
                interval_end: "2025-01-02".to_string(),
                value: 240.0,
                unit: "million_m3_per_day".to_string(),
                source_name: "glofas_v4".to_string(),
                source_url: None,
                transform: Some("daily mean aggregated to node".to_string()),
                quality_flag: Some("baseline".to_string()),
            }],
        };

        let outputs = dataset
            .write_csv_bundle(&dir)
            .expect("bundle should be written");

        assert_eq!(outputs.len(), 3);
        assert!(dir.join("nodes.csv").exists());
        assert!(dir.join("edges.csv").exists());
        assert!(dir.join("time_series.csv").exists());

        std::fs::remove_dir_all(&dir).expect("temporary directory should be removed");
    }
}
