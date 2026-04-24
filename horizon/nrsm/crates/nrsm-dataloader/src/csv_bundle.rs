use std::{
    fs,
    path::{Path, PathBuf},
};

pub trait CsvSerializable {
    fn header() -> &'static [&'static str];
    fn row(&self) -> Vec<String>;
}

#[derive(Debug, Default)]
pub struct CsvBundleWriter;

impl CsvBundleWriter {
    pub fn write_csv<T>(path: impl AsRef<Path>, rows: &[T]) -> Result<PathBuf, std::io::Error>
    where
        T: CsvSerializable,
    {
        let path = path.as_ref();
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }

        let mut contents = String::new();
        contents.push_str(&join_record(T::header().iter().copied().map(str::to_owned)));
        contents.push('\n');

        for row in rows {
            contents.push_str(&join_record(row.row()));
            contents.push('\n');
        }

        fs::write(path, contents)?;
        Ok(path.to_path_buf())
    }
}

fn join_record(fields: impl IntoIterator<Item = String>) -> String {
    fields
        .into_iter()
        .map(|field| escape_csv_field(&field))
        .collect::<Vec<_>>()
        .join(",")
}

fn escape_csv_field(field: &str) -> String {
    let requires_quotes =
        field.contains(',') || field.contains('"') || field.contains('\n') || field.contains('\r');

    if !requires_quotes {
        return field.to_string();
    }

    let escaped = field.replace('"', "\"\"");
    format!("\"{escaped}\"")
}

#[cfg(test)]
mod tests {
    use super::{CsvBundleWriter, CsvSerializable};

    #[derive(Clone)]
    struct FakeRow {
        id: &'static str,
        note: &'static str,
    }

    impl CsvSerializable for FakeRow {
        fn header() -> &'static [&'static str] {
            &["id", "note"]
        }

        fn row(&self) -> Vec<String> {
            vec![self.id.to_string(), self.note.to_string()]
        }
    }

    #[test]
    fn writes_csv_and_escapes_fields() {
        let unique = format!(
            "nrsm-dataloader-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("system time should be after epoch")
                .as_nanos()
        );
        let dir = std::env::temp_dir().join(unique);
        let path = dir.join("bundle.csv");

        let rows = vec![FakeRow {
            id: "gerd",
            note: "contains,comma and \"quotes\"",
        }];

        CsvBundleWriter::write_csv(&path, &rows).expect("write should succeed");
        let written = std::fs::read_to_string(&path).expect("csv should be readable");

        assert!(written.starts_with("id,note\n"));
        assert!(written.contains("\"contains,comma and \"\"quotes\"\"\""));

        std::fs::remove_dir_all(&dir).expect("temporary directory should be removed");
    }
}
