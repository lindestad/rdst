use std::{error::Error, fmt};

#[derive(Debug)]
pub enum SimulationError {
    Validation(String),
}

impl fmt::Display for SimulationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Validation(message) => write!(f, "scenario validation failed: {message}"),
        }
    }
}

impl Error for SimulationError {}
