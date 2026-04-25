use std::{
    collections::HashMap,
    fs,
    path::{Path, PathBuf},
};

#[derive(Clone, Debug)]
pub struct AssembleOptions {
    pub input_dir: PathBuf,
    pub output_dir: PathBuf,
    pub start_date: String,
    pub end_date: String,
}

impl Default for AssembleOptions {
    fn default() -> Self {
        Self {
            input_dir: PathBuf::from("../data"),
            output_dir: PathBuf::from("data/generated"),
            start_date: "2005-01-01".to_string(),
            end_date: "2005-01-31".to_string(),
        }
    }
}

#[derive(Clone, Debug)]
struct TopologyNode {
    node_id: String,
    storage_capacity_mcm: Option<f64>,
    initial_storage_mcm: Option<f64>,
    surface_area_km2_at_full: Option<f64>,
    population_baseline: Option<f64>,
    max_production_m3_day: Option<f64>,
}

#[derive(Clone, Debug)]
struct TopologyEdge {
    from_node_id: String,
    to_node_id: String,
    flow_share: f64,
    travel_time_days: usize,
}

#[derive(Clone, Debug)]
struct ModuleRows {
    rows: Vec<(String, f64)>,
    source_note: String,
}

pub fn assemble_horizon_data_snapshot(
    options: &AssembleOptions,
) -> Result<Vec<PathBuf>, Box<dyn std::error::Error>> {
    let nodes = read_nodes(&options.input_dir.join("topology").join("nodes.csv"))?;
    let edges = read_edges(&options.input_dir.join("topology").join("edges.csv"))?;
    let dates = date_range(&options.start_date, &options.end_date)?;
    let modules_dir = options.output_dir.join("modules");
    let staging_dir = options.output_dir.join("staging");
    fs::create_dir_all(&modules_dir)?;
    fs::create_dir_all(&staging_dir)?;

    let outgoing = outgoing_edges_by_node(&edges);
    let mut outputs = Vec::new();
    let mut warnings = Vec::<String>::new();

    for node in &nodes {
        let catchment = catchment_inflow_rows(&options.input_dir, node, &dates, &mut warnings)?;
        outputs.push(write_module_csv(
            &modules_dir,
            &node.node_id,
            "catchment_inflow",
            &catchment.rows,
        )?);

        let evaporation = evaporation_rows(&options.input_dir, node, &dates, &mut warnings)?;
        outputs.push(write_module_csv(
            &modules_dir,
            &node.node_id,
            "evaporation",
            &evaporation.rows,
        )?);

        let drink_water = drink_water_rows(node, &dates);
        outputs.push(write_module_csv(
            &modules_dir,
            &node.node_id,
            "drink_water",
            &drink_water.rows,
        )?);

        let food_production = food_production_rows(&options.input_dir, node, &dates)?;
        outputs.push(write_module_csv(
            &modules_dir,
            &node.node_id,
            "food_production",
            &food_production.rows,
        )?);

        let energy = energy_rows(&options.input_dir, node, &dates)?;
        outputs.push(write_module_csv(
            &modules_dir,
            &node.node_id,
            "energy",
            &energy.rows,
        )?);

        let actions = action_rows(&dates);
        outputs.push(write_module_csv(
            &modules_dir,
            &node.node_id,
            "actions",
            &actions.rows,
        )?);

        warnings.push(format!(
            "{},{},{},{},{},{},{}",
            node.node_id,
            catchment.source_note,
            evaporation.source_note,
            drink_water.source_note,
            food_production.source_note,
            energy.source_note,
            actions.source_note
        ));
    }

    let config = render_config(&nodes, &outgoing);
    let config_path = options.output_dir.join("config.yaml");
    fs::write(&config_path, config)?;
    outputs.push(config_path);

    let warnings_path = staging_dir.join("assembly_warnings.csv");
    fs::write(
        &warnings_path,
        format!(
            "node_id,catchment_inflow,evaporation,drink_water,food_production,energy,actions\n{}\n",
            warnings.join("\n")
        ),
    )?;
    outputs.push(warnings_path);

    Ok(outputs)
}

fn read_nodes(path: &Path) -> Result<Vec<TopologyNode>, Box<dyn std::error::Error>> {
    let rows = read_csv(path)?;
    let mut nodes = Vec::with_capacity(rows.len());
    for row in rows {
        nodes.push(TopologyNode {
            node_id: required(&row, "node_id")?,
            storage_capacity_mcm: optional_f64(&row, "storage_capacity_mcm")?,
            initial_storage_mcm: optional_f64(&row, "initial_storage_mcm")?,
            surface_area_km2_at_full: optional_f64(&row, "surface_area_km2_at_full")?,
            population_baseline: optional_f64(&row, "population_baseline")?,
            max_production_m3_day: optional_f64(&row, "max_production_m3_day")?,
        });
    }
    Ok(nodes)
}

fn read_edges(path: &Path) -> Result<Vec<TopologyEdge>, Box<dyn std::error::Error>> {
    let rows = read_csv(path)?;
    let mut edges = Vec::with_capacity(rows.len());
    for row in rows {
        edges.push(TopologyEdge {
            from_node_id: required(&row, "from_node_id")?,
            to_node_id: required(&row, "to_node_id")?,
            flow_share: optional_f64(&row, "flow_share")?.unwrap_or(1.0),
            travel_time_days: optional_f64(&row, "travel_time_days")?
                .map(|value| value.max(0.0).round() as usize)
                .unwrap_or(0),
        });
    }
    Ok(edges)
}

fn outgoing_edges_by_node(edges: &[TopologyEdge]) -> HashMap<String, Vec<TopologyEdge>> {
    let mut outgoing = HashMap::<String, Vec<TopologyEdge>>::new();
    for edge in edges {
        outgoing
            .entry(edge.from_node_id.clone())
            .or_default()
            .push(edge.clone());
    }
    outgoing
}

fn catchment_inflow_rows(
    input_dir: &Path,
    node: &TopologyNode,
    dates: &[SimpleDate],
    _warnings: &mut Vec<String>,
) -> Result<ModuleRows, Box<dyn std::error::Error>> {
    let path = input_dir
        .join("hydmod")
        .join("daily")
        .join(format!("{}.csv", node.node_id));
    if !path.exists() {
        return Err(format!(
            "missing hydmod daily file for node `{}`: {}",
            node.node_id,
            path.display()
        )
        .into());
    }

    let values = read_date_value_map(&path, "runoff_m3_day")?;
    Ok(ModuleRows {
        rows: rows_for_dates(&values, dates, &path, "runoff_m3_day")?,
        source_note: "hydmod daily Runoff_m3s converted to m3/day".to_string(),
    })
}

fn evaporation_rows(
    input_dir: &Path,
    node: &TopologyNode,
    dates: &[SimpleDate],
    _warnings: &mut Vec<String>,
) -> Result<ModuleRows, Box<dyn std::error::Error>> {
    let Some(surface_area_km2) = node.surface_area_km2_at_full else {
        return Ok(zero_rows(
            dates,
            "zero because surface_area_km2_at_full is missing",
        ));
    };
    let path = input_dir
        .join("hydmod")
        .join("daily")
        .join(format!("{}.csv", node.node_id));
    if !path.exists() {
        return Err(format!(
            "missing hydmod daily file for node `{}`: {}",
            node.node_id,
            path.display()
        )
        .into());
    }

    let daily = read_date_value_map(&path, "actual_et_mm_day")?;
    Ok(ModuleRows {
        rows: rows_for_dates(&daily, dates, &path, "actual_et_mm_day")?
            .into_iter()
            .map(|(date, actual_et_mm_day)| {
                let daily_m3 = actual_et_mm_day * surface_area_km2 * 1_000.0;
                (date, daily_m3.max(0.0))
            })
            .collect(),
        source_note: "hydmod daily ActualET_mm_day over lake_area_km2 converted to m3/day"
            .to_string(),
    })
}

fn drink_water_rows(node: &TopologyNode, dates: &[SimpleDate]) -> ModuleRows {
    let demand = node
        .population_baseline
        .map(|population| population * 100.0 / 1_000.0)
        .unwrap_or(0.0);
    ModuleRows {
        rows: dates
            .iter()
            .map(|date| (date.to_string(), demand))
            .collect(),
        source_note: if demand > 0.0 {
            "population_baseline with 100 L/person/day assumption".to_string()
        } else {
            "zero because population_baseline is missing".to_string()
        },
    }
}

fn food_production_rows(
    input_dir: &Path,
    node: &TopologyNode,
    dates: &[SimpleDate],
) -> Result<ModuleRows, Box<dyn std::error::Error>> {
    let Some(path) = water_usage_path(input_dir, &node.node_id) else {
        return Err(format!(
            "missing agriculture water-usage file for node `{}`",
            node.node_id
        )
        .into());
    };

    let values = read_date_value_map(&path, "water_m3_day")?;
    Ok(ModuleRows {
        rows: rows_for_dates(&values, dates, &path, "water_m3_day")?,
        source_note: format!(
            "{} water_m3_day used as water-equivalent food capacity",
            path.file_name()
                .and_then(|name| name.to_str())
                .unwrap_or("water usage")
        ),
    })
}

fn energy_rows(
    input_dir: &Path,
    node: &TopologyNode,
    dates: &[SimpleDate],
) -> Result<ModuleRows, Box<dyn std::error::Error>> {
    let path = input_dir
        .join("electricity_price")
        .join(format!("{}.csv", node.node_id));
    if !path.exists() {
        return Err(format!(
            "missing electricity price file for node `{}`: {}",
            node.node_id,
            path.display()
        )
        .into());
    }

    let values = read_date_value_map(&path, "price_eur_kwh")?;
    Ok(ModuleRows {
        rows: rows_for_dates(&values, dates, &path, "price_eur_kwh")?,
        source_note: "electricity_price price_eur_kwh used as current NRSM energy value proxy"
            .to_string(),
    })
}

fn action_rows(dates: &[SimpleDate]) -> ModuleRows {
    ModuleRows {
        rows: dates.iter().map(|date| (date.to_string(), 1.0)).collect(),
        source_note: "default full-production action; override per node/day for policy runs"
            .to_string(),
    }
}

fn water_usage_path(input_dir: &Path, node_id: &str) -> Option<PathBuf> {
    let dir = input_dir.join("agriculture").join("water_usage");
    for name in water_usage_file_candidates(node_id) {
        let path = dir.join(name);
        if path.exists() {
            return Some(path);
        }
    }
    None
}

fn water_usage_file_candidates(node_id: &str) -> Vec<String> {
    let mut candidates = vec![format!("nile_{node_id}_water.csv")];

    match node_id {
        "egypt_ag" => candidates.push("nile_cairo_water.csv".to_string()),
        "gezira_irr" => candidates.push("nile_singa_water.csv".to_string()),
        _ => {}
    }

    if let Some(stem) = node_id.strip_suffix("_ag") {
        candidates.push(format!("nile_{stem}_water.csv"));
    }
    if let Some(stem) = node_id.strip_suffix("_irr") {
        candidates.push(format!("nile_{stem}_water.csv"));
    }

    candidates
}

fn zero_rows(dates: &[SimpleDate], source_note: &str) -> ModuleRows {
    ModuleRows {
        rows: dates.iter().map(|date| (date.to_string(), 0.0)).collect(),
        source_note: source_note.to_string(),
    }
}

fn render_config(nodes: &[TopologyNode], outgoing: &HashMap<String, Vec<TopologyEdge>>) -> String {
    let mut yaml = String::from("settings:\n  timestep_days: 1.0\n\nnodes:\n");

    for node in nodes {
        let max_capacity = node
            .storage_capacity_mcm
            .map(|value| value * 1_000_000.0)
            .unwrap_or(1_000_000_000_000.0);
        let initial_level = node
            .initial_storage_mcm
            .map(|value| value * 1_000_000.0)
            .unwrap_or_else(|| {
                if node.storage_capacity_mcm.is_some() {
                    max_capacity * 0.5
                } else {
                    0.0
                }
            });
        let max_production = default_max_production(node);

        yaml.push_str(&format!(
            "  - id: {}\n    reservoir:\n      initial_level: {:.3}\n      max_capacity: {:.3}\n    max_production: {:.3}\n    catchment_inflow:\n      type: csv\n      filepath: modules/{}.catchment_inflow.csv\n      column: scenario_1\n    connections:\n",
            node.node_id, initial_level, max_capacity, max_production, node.node_id
        ));

        match outgoing.get(&node.node_id) {
            Some(edges) if !edges.is_empty() => {
                let fraction_sum = edges
                    .iter()
                    .map(|edge| edge.flow_share.max(0.0))
                    .sum::<f64>();
                let normalizer = if fraction_sum > 1.0 {
                    fraction_sum
                } else {
                    1.0
                };
                for edge in edges {
                    let fraction = edge.flow_share.max(0.0) / normalizer;
                    yaml.push_str(&format!(
                        "      - node_id: {}\n        fraction: {:.6}\n        delay: {}\n",
                        edge.to_node_id, fraction, edge.travel_time_days
                    ));
                }
            }
            _ => yaml.push_str("      []\n"),
        }

        yaml.push_str(&format!(
            "    modules:\n      evaporation:\n        type: csv\n        filepath: modules/{}.evaporation.csv\n        column: scenario_1\n      drink_water:\n        type: csv\n        filepath: modules/{}.drink_water.csv\n        column: scenario_1\n      food_production:\n        type: csv\n        filepath: modules/{}.food_production.csv\n        column: scenario_1\n        water_coefficient: 1.0\n      energy:\n        type: csv\n        filepath: modules/{}.energy.csv\n        column: scenario_1\n    actions:\n      production_level:\n        type: csv\n        filepath: modules/{}.actions.csv\n        column: scenario_1\n",
            node.node_id, node.node_id, node.node_id, node.node_id, node.node_id
        ));
    }

    yaml
}

fn default_max_production(node: &TopologyNode) -> f64 {
    if let Some(value) = node.max_production_m3_day {
        return value;
    }

    match node.node_id.as_str() {
        "gerd" => 45_000_000.0,
        "aswand" => 55_000_000.0,
        "merowe" => 35_000_000.0,
        _ => 1_000_000_000_000.0,
    }
}

fn write_module_csv(
    modules_dir: &Path,
    node_id: &str,
    module_name: &str,
    rows: &[(String, f64)],
) -> Result<PathBuf, std::io::Error> {
    let path = modules_dir.join(format!("{node_id}.{module_name}.csv"));
    let mut contents = String::from("date,scenario_1\n");
    for (date, value) in rows {
        contents.push_str(&format!("{date},{value:.6}\n"));
    }
    fs::write(&path, contents)?;
    Ok(path)
}

fn read_date_value_map(
    path: &Path,
    value_column: &str,
) -> Result<HashMap<String, f64>, Box<dyn std::error::Error>> {
    let rows = read_csv(path)?;
    let mut values = HashMap::new();
    for row in rows {
        let date = required(&row, "date").or_else(|_| required(&row, "month"))?;
        let value = optional_f64(&row, value_column)?.unwrap_or(0.0);
        values.insert(date, value);
    }
    Ok(values)
}

fn rows_for_dates(
    values: &HashMap<String, f64>,
    dates: &[SimpleDate],
    path: &Path,
    value_column: &str,
) -> Result<Vec<(String, f64)>, Box<dyn std::error::Error>> {
    dates
        .iter()
        .map(|date| {
            let key = date.to_string();
            let Some(value) = values.get(&key).copied() else {
                return Err(format!(
                    "{} is missing `{}` for date {}",
                    path.display(),
                    value_column,
                    key
                )
                .into());
            };
            Ok((key, value))
        })
        .collect()
}

fn read_csv(path: &Path) -> Result<Vec<HashMap<String, String>>, Box<dyn std::error::Error>> {
    let contents = fs::read_to_string(path)?;
    let mut lines = contents.lines().filter(|line| !line.trim().is_empty());
    let Some(header) = lines.next() else {
        return Ok(vec![]);
    };
    let headers = split_csv_line(header);
    let mut rows = Vec::new();
    for line in lines {
        let fields = split_csv_line(line);
        let mut row = HashMap::new();
        for (index, header) in headers.iter().enumerate() {
            row.insert(
                header.clone(),
                fields.get(index).cloned().unwrap_or_default(),
            );
        }
        rows.push(row);
    }
    Ok(rows)
}

fn split_csv_line(line: &str) -> Vec<String> {
    let mut fields = Vec::new();
    let mut field = String::new();
    let mut chars = line.chars().peekable();
    let mut in_quotes = false;
    while let Some(ch) = chars.next() {
        match ch {
            '"' if in_quotes && chars.peek() == Some(&'"') => {
                field.push('"');
                chars.next();
            }
            '"' => in_quotes = !in_quotes,
            ',' if !in_quotes => {
                fields.push(field.trim().to_string());
                field.clear();
            }
            _ => field.push(ch),
        }
    }
    fields.push(field.trim().to_string());
    fields
}

fn required(
    row: &HashMap<String, String>,
    key: &str,
) -> Result<String, Box<dyn std::error::Error>> {
    let value = row.get(key).cloned().unwrap_or_default();
    if value.trim().is_empty() {
        return Err(format!("missing required CSV column value `{key}`").into());
    }
    Ok(value)
}

fn optional(row: &HashMap<String, String>, key: &str) -> Option<String> {
    row.get(key)
        .cloned()
        .filter(|value| !value.trim().is_empty())
}

fn optional_f64(
    row: &HashMap<String, String>,
    key: &str,
) -> Result<Option<f64>, Box<dyn std::error::Error>> {
    let Some(value) = optional(row, key) else {
        return Ok(None);
    };
    Ok(Some(value.parse()?))
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
        let date = Self {
            year: parts[0]
                .parse::<i32>()
                .map_err(|_| format!("invalid year in `{value}`"))?,
            month: parts[1]
                .parse::<u32>()
                .map_err(|_| format!("invalid month in `{value}`"))?,
            day: parts[2]
                .parse::<u32>()
                .map_err(|_| format!("invalid day in `{value}`"))?,
        };
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
    use super::{AssembleOptions, assemble_horizon_data_snapshot};
    use nrsm_sim_core::{Scenario, simulate};
    use std::{fs, path::Path};

    #[test]
    fn assembles_horizon_data_snapshot_that_simulates() {
        let unique = format!(
            "nrsm-horizon-data-assemble-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("system time should be after epoch")
                .as_nanos()
        );
        let dir = std::env::temp_dir().join(unique);
        let input = dir.join("horizon_data");
        write_fixture_data(&input);
        let output = dir.join("generated");

        let outputs = assemble_horizon_data_snapshot(&AssembleOptions {
            input_dir: input,
            output_dir: output.clone(),
            start_date: "2005-01-01".to_string(),
            end_date: "2005-01-02".to_string(),
        })
        .expect("snapshot should assemble");

        assert!(outputs.iter().any(|path| path.ends_with("config.yaml")));
        assert!(
            output
                .join("modules")
                .join("src.catchment_inflow.csv")
                .exists()
        );
        let config = fs::read_to_string(output.join("config.yaml"))
            .expect("generated config should be readable");
        assert!(config.contains("fraction: 0.500000"));

        let food = fs::read_to_string(
            output
                .join("modules")
                .join("gezira_irr.food_production.csv"),
        )
        .expect("food module csv should be readable");
        assert!(food.contains("2005-01-01,42.000000"));
        assert!(
            output
                .join("staging")
                .join("assembly_warnings.csv")
                .exists()
        );

        let mut scenario: Scenario =
            serde_yaml::from_str(&config).expect("generated config should parse");
        scenario
            .load_module_csvs(&output)
            .expect("generated module CSVs should load");
        let result = simulate(&scenario).expect("generated snapshot should simulate");
        assert_eq!(result.periods.len(), 2);
        assert!(result.summary.total_inflow > 0.0);
        assert!(result.summary.total_food_produced > 0.0);

        fs::remove_dir_all(&dir).expect("temporary directory should be removed");
    }

    fn write_fixture_data(root: &Path) {
        fs::create_dir_all(root.join("topology")).expect("topology dir");
        fs::create_dir_all(root.join("hydmod").join("daily")).expect("hydmod dir");
        fs::create_dir_all(root.join("agriculture").join("water_usage")).expect("ag dir");
        fs::create_dir_all(root.join("electricity_price")).expect("electricity dir");
        fs::write(
            root.join("topology").join("nodes.csv"),
            concat!(
                "node_id,name,node_type,country,latitude,longitude,upstream,downstream,catchment_area_km2,storage_capacity_mcm,surface_area_km2_at_full,area_ha_baseline,population_baseline\n",
                "src,Source,source,XX,0,0,,res,100,,,,\n",
                "res,Reservoir,reservoir,XX,0,1,src,, ,10,2,,1000\n",
                "gezira_irr,Gezira,demand_irrigation,XX,0,2,src,, ,,,, \n",
            ),
        )
        .expect("nodes csv");
        fs::write(
            root.join("topology").join("edges.csv"),
            concat!(
                "edge_id,from_node_id,to_node_id,flow_share,travel_time_days,travel_time_months,muskingum_k,muskingum_x\n",
                "src__res,src,res,1.0,1,,,\n",
                "src__gezira_irr,src,gezira_irr,1.0,0,,,\n",
            ),
        )
        .expect("edges csv");
        for node_id in ["src", "res", "gezira_irr"] {
            fs::write(
                root.join("hydmod")
                    .join("daily")
                    .join(format!("{node_id}.csv")),
                "date,precip_mm_day,air_temp_c,soil_moisture_mm,actual_et_mm_day,runoff_mm_day,runoff_m3s,runoff_m3_day\n2005-01-01,1,20,75,1,1,10,864000\n2005-01-02,1,20,75,1,1,11,950400\n",
            )
            .expect("hydmod csv");
            fs::write(
                root.join("agriculture")
                    .join("water_usage")
                    .join(format!("nile_{node_id}_water.csv")),
                "date,et0_mm_day,kc,water_m3_day\n2005-01-01,1,1,42\n2005-01-02,1,1,43\n",
            )
            .expect("water usage csv");
            fs::write(
                root.join("electricity_price")
                    .join(format!("{node_id}.csv")),
                "date,price_eur_kwh\n2005-01-01,0.01\n2005-01-02,0.02\n",
            )
            .expect("electricity csv");
        }
    }
}
