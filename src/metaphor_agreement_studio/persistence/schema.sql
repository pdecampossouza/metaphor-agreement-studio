PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS project (
  project_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  app_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_files (
  file_id TEXT PRIMARY KEY,
  original_name TEXT NOT NULL,
  stored_relpath TEXT NOT NULL UNIQUE,
  sha256 TEXT NOT NULL UNIQUE,
  byte_length INTEGER NOT NULL,
  imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS imports (
  import_id TEXT PRIMARY KEY,
  file_id TEXT NOT NULL REFERENCES source_files(file_id),
  inspected_at TEXT NOT NULL,
  validation_status TEXT NOT NULL,
  raw_payload_json TEXT NOT NULL,
  detection_summary_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
  source_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  source_type TEXT NOT NULL,
  parent_source_id TEXT REFERENCES sources(source_id),
  is_aggregate INTEGER NOT NULL CHECK (is_aggregate IN (0, 1))
);

CREATE TABLE IF NOT EXISTS raters (
  rater_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  source_file_id TEXT REFERENCES source_files(file_id),
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS lexical_units (
  unit_id TEXT PRIMARY KEY,
  lexical_unit TEXT NOT NULL,
  grammatical_category TEXT NOT NULL,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  occurrence_index INTEGER NOT NULL,
  song TEXT,
  artist TEXT,
  verse TEXT,
  context TEXT,
  timestamp TEXT,
  source_metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS raw_annotations (
  annotation_id TEXT PRIMARY KEY,
  unit_id TEXT NOT NULL REFERENCES lexical_units(unit_id),
  rater_id TEXT NOT NULL REFERENCES raters(rater_id),
  import_id TEXT NOT NULL REFERENCES imports(import_id),
  original_sheet TEXT NOT NULL,
  original_cell TEXT NOT NULL,
  original_raw_value_json TEXT NOT NULL,
  original_style_json TEXT NOT NULL,
  detection_method TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS validation_decisions (
  decision_id TEXT PRIMARY KEY,
  decision_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  original_value TEXT,
  validated_value TEXT,
  reason TEXT NOT NULL,
  decided_at TEXT NOT NULL,
  actor TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS validated_annotations (
  annotation_id TEXT PRIMARY KEY REFERENCES raw_annotations(annotation_id),
  classification TEXT NOT NULL CHECK (classification IN ('METAPHOR','NON_METAPHOR','MISSING')),
  validated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dataset_versions (
  version_id TEXT PRIMARY KEY,
  ordinal INTEGER NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  reason TEXT NOT NULL,
  content_hash TEXT NOT NULL UNIQUE,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_versions (
  analysis_id TEXT PRIMARY KEY,
  ordinal INTEGER NOT NULL UNIQUE,
  dataset_version_id TEXT NOT NULL REFERENCES dataset_versions(version_id),
  created_at TEXT NOT NULL,
  config_json TEXT NOT NULL,
  config_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
  event_id TEXT PRIMARY KEY,
  occurred_at TEXT NOT NULL,
  event_type TEXT NOT NULL,
  summary TEXT NOT NULL,
  details_json TEXT NOT NULL,
  dataset_version_id TEXT REFERENCES dataset_versions(version_id),
  analysis_id TEXT REFERENCES analysis_versions(analysis_id)
);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  stored_relpath TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL,
  dataset_version_id TEXT NOT NULL REFERENCES dataset_versions(version_id),
  analysis_id TEXT REFERENCES analysis_versions(analysis_id),
  metadata_json TEXT NOT NULL
);

PRAGMA user_version = 1;
