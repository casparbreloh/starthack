-- Athena external table DDL for fast-sim results
-- Reference: actual table is created via CDK (Glue CfnTable in infra/stack.py)
--
-- Prerequisites:
--   1. AWS Glue crawler or CDK deployment creates fast_sim_db database
--   2. S3 bucket fast-sim-results-{account} must exist with results/ prefix
--
-- Usage:
--   CREATE DATABASE fast_sim_db;
--   Then run this DDL in Athena to create the external table (if not using CDK Glue)

CREATE EXTERNAL TABLE IF NOT EXISTS fast_sim_db.results (
    run_id                  STRING,
    seed                    BIGINT,
    difficulty              STRING,
    final_sol               INT,
    mission_outcome         STRING,
    final_score             INT,
    survival_score          INT,
    nutrition_score         INT,
    resource_efficiency_score INT,
    crisis_mgmt_score       INT,
    crises_encountered      INT,
    crises_resolved         INT,
    crop_deaths             INT,
    crops_planted           INT,
    crops_harvested         INT,
    duration_seconds        DOUBLE,
    config_hash             STRING,
    crisis_log_json         STRING,
    crop_yields_json        STRING,
    resource_extremes_json  STRING,
    resource_averages_json  STRING,
    key_decisions_json      STRING,
    strategy_config_json    STRING
)
PARTITIONED BY (wave_id STRING)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
WITH SERDEPROPERTIES (
    'serialization.format' = '1'
)
LOCATION 's3://fast-sim-results-ACCOUNT_ID/results/'
TBLPROPERTIES (
    'projection.enabled' = 'true',
    'projection.wave_id.type' = 'injected',
    'storage.location.template' = 's3://fast-sim-results-ACCOUNT_ID/results/${wave_id}/'
);

-- Example queries:

-- Top-10 runs by score in wave-001:
-- SELECT run_id, final_score, mission_outcome, crops_planted, crises_encountered
-- FROM fast_sim_db.results
-- WHERE wave_id = 'wave-001'
-- ORDER BY final_score DESC
-- LIMIT 10;

-- Score distribution across all waves:
-- SELECT wave_id, AVG(final_score) as avg_score, MAX(final_score) as max_score,
--        COUNT(*) as n_runs
-- FROM fast_sim_db.results
-- GROUP BY wave_id
-- ORDER BY avg_score DESC;
