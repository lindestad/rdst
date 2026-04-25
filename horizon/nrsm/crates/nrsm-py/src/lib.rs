use std::{fs, path::PathBuf};

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

#[pymodule]
fn nrsm_py(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyPreparedScenario>()?;
    Ok(())
}

fn to_py_value_error(error: impl std::fmt::Display) -> PyErr {
    PyValueError::new_err(error.to_string())
}
