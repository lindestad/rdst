use std::{
    fs,
    path::{Path, PathBuf},
};

use nrsm_dataloader::{AssembleOptions, assemble_horizon_data_snapshot};
use nrsm_sim_core::{PreparedScenario, Scenario};
use pyo3::{exceptions::PyValueError, prelude::*};

#[pyclass(name = "PreparedScenario")]
struct PyPreparedScenario {
    inner: PreparedScenario,
}

#[pymethods]
impl PyPreparedScenario {
    #[staticmethod]
    fn from_yaml(path: PathBuf) -> PyResult<Self> {
        Self::from_config_yaml(path)
    }

    #[staticmethod]
    #[pyo3(signature = (period_path, data_dir=None, output_dir=None))]
    fn from_period(
        period_path: PathBuf,
        data_dir: Option<PathBuf>,
        output_dir: Option<PathBuf>,
    ) -> PyResult<Self> {
        let period = read_period_spec(&period_path).map_err(to_py_value_error)?;
        let nrsm_root = infer_nrsm_root(&period_path).map_err(to_py_value_error)?;
        let output_dir = output_dir.unwrap_or_else(|| default_output_dir(&nrsm_root, &period_path));
        let input_dir = data_dir.unwrap_or_else(|| default_data_dir(&nrsm_root));

        assemble_horizon_data_snapshot(&AssembleOptions {
            input_dir,
            output_dir: output_dir.clone(),
            start_date: period.start_date,
            end_date: period.end_date,
            node_ids: period.node_ids,
        })
        .map_err(to_py_value_error)?;

        Self::from_config_yaml(output_dir.join("config.yaml"))
    }

    fn node_ids(&self) -> Vec<String> {
        self.inner.node_ids().to_vec()
    }

    fn node_count(&self) -> usize {
        self.inner.node_count()
    }

    fn horizon_days(&self) -> usize {
        self.inner.horizon_days()
    }

    fn expected_action_len(&self) -> usize {
        self.inner.expected_action_len()
    }

    fn run_configured_json(&self) -> PyResult<String> {
        let result = self.inner.simulate().map_err(to_py_value_error)?;
        serde_json::to_string(&result).map_err(to_py_value_error)
    }

    fn run_actions_json(&self, actions: Vec<f64>) -> PyResult<String> {
        let result = self
            .inner
            .simulate_with_actions(&actions)
            .map_err(to_py_value_error)?;
        serde_json::to_string(&result).map_err(to_py_value_error)
    }

    fn run_actions_summary_json(&self, actions: Vec<f64>) -> PyResult<String> {
        let summary = self
            .inner
            .simulate_summary_with_actions(&actions)
            .map_err(to_py_value_error)?;
        serde_json::to_string(&summary).map_err(to_py_value_error)
    }
}

impl PyPreparedScenario {
    fn from_config_yaml(path: PathBuf) -> PyResult<Self> {
        let contents = fs::read_to_string(&path).map_err(to_py_value_error)?;
        let mut scenario: Scenario = serde_yaml::from_str(&contents).map_err(to_py_value_error)?;
        let base_dir = path
            .parent()
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("."));
        scenario
            .load_module_csvs(base_dir)
            .map_err(to_py_value_error)?;
        let inner = PreparedScenario::try_new(scenario).map_err(to_py_value_error)?;

        Ok(Self { inner })
    }
}

#[pymodule]
fn nrsm_py(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyPreparedScenario>()?;
    Ok(())
}

fn to_py_value_error(error: impl std::fmt::Display) -> PyErr {
    PyValueError::new_err(error.to_string())
}

#[derive(Debug)]
struct PeriodSpec {
    start_date: String,
    end_date: String,
    node_ids: Option<Vec<String>>,
}

fn read_period_spec(path: &Path) -> Result<PeriodSpec, Box<dyn std::error::Error>> {
    let contents = fs::read_to_string(path)?;
    let value: serde_yaml::Value = serde_yaml::from_str(&contents)?;
    let settings = value
        .get("settings")
        .ok_or("period file must contain a `settings` mapping")?;
    let start_date = required_string_setting(settings, "start_date", path)?;
    let end_date = required_string_setting(settings, "end_date", path)?;
    let node_ids = optional_string_list_setting(settings, "node_ids", path)?;

    Ok(PeriodSpec {
        start_date,
        end_date,
        node_ids,
    })
}

fn required_string_setting(
    settings: &serde_yaml::Value,
    field: &str,
    path: &Path,
) -> Result<String, Box<dyn std::error::Error>> {
    let value = settings.get(field).ok_or_else(|| {
        format!(
            "period file `{}` must contain `settings.{field}`",
            path.display()
        )
    })?;
    if let Some(text) = value.as_str() {
        return Ok(text.to_string());
    }
    Err(format!(
        "period file `{}` setting `settings.{field}` must be a YYYY-MM-DD string",
        path.display()
    )
    .into())
}

fn optional_string_list_setting(
    settings: &serde_yaml::Value,
    field: &str,
    path: &Path,
) -> Result<Option<Vec<String>>, Box<dyn std::error::Error>> {
    let Some(value) = settings.get(field) else {
        return Ok(None);
    };
    let Some(items) = value.as_sequence() else {
        return Err(format!(
            "period file `{}` setting `settings.{field}` must be a list of node ids",
            path.display()
        )
        .into());
    };

    let mut strings = Vec::with_capacity(items.len());
    for item in items {
        let Some(text) = item.as_str() else {
            return Err(format!(
                "period file `{}` setting `settings.{field}` must contain only strings",
                path.display()
            )
            .into());
        };
        strings.push(text.to_string());
    }
    Ok(Some(strings))
}

fn infer_nrsm_root(period_path: &Path) -> Result<PathBuf, Box<dyn std::error::Error>> {
    let absolute_period_path = if period_path.is_absolute() {
        period_path.to_path_buf()
    } else {
        std::env::current_dir()?.join(period_path)
    };

    for ancestor in absolute_period_path.ancestors() {
        if ancestor
            .file_name()
            .and_then(|name| name.to_str())
            .is_some_and(|name| name == "nrsm")
            && ancestor.join("Cargo.toml").exists()
        {
            return Ok(ancestor.to_path_buf());
        }

        let nested = ancestor.join("horizon").join("nrsm");
        if nested.join("Cargo.toml").exists() {
            return Ok(nested);
        }
    }

    Ok(std::env::current_dir()?)
}

fn default_data_dir(nrsm_root: &Path) -> PathBuf {
    nrsm_root
        .parent()
        .map(|horizon_dir| horizon_dir.join("data"))
        .filter(|path| path.exists())
        .unwrap_or_else(|| PathBuf::from("../data"))
}

fn default_output_dir(nrsm_root: &Path, period_path: &Path) -> PathBuf {
    let stem = period_path
        .file_stem()
        .and_then(|stem| stem.to_str())
        .unwrap_or("period");
    nrsm_root.join("data").join("generated").join(stem)
}

#[cfg(test)]
mod tests {
    use std::{fs, path::PathBuf};

    use super::{default_output_dir, read_period_spec};

    #[test]
    fn reads_period_from_yaml_settings() {
        let dir = std::env::temp_dir().join(format!(
            "nrsm-py-period-spec-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("system time should be after epoch")
                .as_nanos()
        ));
        fs::create_dir_all(&dir).expect("temp dir should be created");
        let path = dir.join("wet-season.yaml");
        fs::write(
            &path,
            "settings:\n  start_date: 1963-09-01\n  end_date: 1963-09-30\n  node_ids:\n    - tana\n    - gerd\nnodes: []\n",
        )
        .expect("period file should be written");

        let period = read_period_spec(&path).expect("period should parse");

        assert_eq!(period.start_date, "1963-09-01");
        assert_eq!(period.end_date, "1963-09-30");
        assert_eq!(
            period.node_ids,
            Some(vec!["tana".to_string(), "gerd".to_string()])
        );

        fs::remove_dir_all(&dir).expect("temp dir should be removed");
    }

    #[test]
    fn defaults_output_under_nrsm_generated_dir() {
        let output = default_output_dir(
            &PathBuf::from("horizon/nrsm"),
            &PathBuf::from("scenarios/nile-mvp/past/1963-september-30d.yaml"),
        );

        assert_eq!(
            output,
            PathBuf::from("horizon/nrsm/data/generated/1963-september-30d")
        );
    }
}
