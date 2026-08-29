CREATE DATABASE medivision;
USE medivision;
CREATE TABLE patients (
    patient_id INT AUTO_INCREMENT PRIMARY KEY,
    age INT NOT NULL,
    gender VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE vitals (
    vital_id INT AUTO_INCREMENT PRIMARY KEY,

    patient_id INT NOT NULL,

    spo2 FLOAT,
    heart_rate FLOAT,
    systolic_bp FLOAT,
    diastolic_bp FLOAT,

    triage_level INT,

    FOREIGN KEY (patient_id)
        REFERENCES patients(patient_id)
);
CREATE TABLE diagnostic_reports (
    report_id INT AUTO_INCREMENT PRIMARY KEY,

    patient_id INT NOT NULL,

    report_text TEXT,

    disease_label VARCHAR(50),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (patient_id)
        REFERENCES patients(patient_id)
);
CREATE TABLE xgboost_training (
    id INT AUTO_INCREMENT PRIMARY KEY,

    age INT NOT NULL,

    spo2 FLOAT NOT NULL,

    heart_rate FLOAT NOT NULL,

    systolic_bp FLOAT NOT NULL,

    diastolic_bp FLOAT NOT NULL,

    triage_level INT NOT NULL
);

CREATE TABLE nlp_training (
    id INT AUTO_INCREMENT PRIMARY KEY,

    report_text TEXT NOT NULL,

    disease_label VARCHAR(50) NOT NULL
);

USE medivision;

DROP TABLE IF EXISTS xgboost_training;

CREATE TABLE xgboost_training (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    subject_id BIGINT NOT NULL,
    hadm_id BIGINT NOT NULL,
    stay_id BIGINT NOT NULL,

    age FLOAT,

    spo2 FLOAT,
    heart_rate FLOAT,
    resp_rate FLOAT,

    sys_bp FLOAT,
    dias_bp FLOAT,

    temp FLOAT,
    pain_score FLOAT,

    hist_asthma TINYINT,
    hist_diabetes TINYINT,
    hist_hypertension TINYINT,
    hist_cad TINYINT,
    hist_stroke TINYINT,

    hospital_expire_flag TINYINT,

    INDEX idx_subject_id (subject_id),
    INDEX idx_hadm_id (hadm_id),
    INDEX idx_stay_id (stay_id)
);

DESCRIBE xgboost_training;
SELECT COUNT(*)
FROM xgboost_training;

SELECT *
FROM xgboost_training
LIMIT 10;

SELECT
    hospital_expire_flag,
    COUNT(*) AS number_of_records

FROM xgboost_training

GROUP BY hospital_expire_flag;

USE medvision;

TRUNCATE TABLE xgboost_training;

USE medivision;

CREATE TABLE patient_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    age FLOAT,
    spo2 FLOAT,
    heart_rate FLOAT,
    resp_rate FLOAT,

    sys_bp FLOAT,
    dias_bp FLOAT,

    temp FLOAT,
    pain_score FLOAT,

    hist_asthma TINYINT,
    hist_diabetes TINYINT,
    hist_hypertension TINYINT,
    hist_cad TINYINT,
    hist_stroke TINYINT,

    target_triage_acuity INT
);

DESCRIBE patient_records;

USE medivision;

SELECT COUNT(*) AS total_records
FROM patient_records;

USE medivision;

SELECT COUNT(*) FROM patient_records;

DESCRIBE patient_records;

USE medivision;

DROP TABLE IF EXISTS patient_records;

CREATE TABLE patient_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    subject_id BIGINT NOT NULL,
    hadm_id BIGINT NOT NULL,
    stay_id BIGINT,

    age FLOAT,
    spo2 FLOAT,
    heart_rate FLOAT,
    resp_rate FLOAT,
    sys_bp FLOAT,
    dias_bp FLOAT,
    temp FLOAT,
    pain_score FLOAT,

    hist_asthma TINYINT,
    hist_diabetes TINYINT,
    hist_hypertension TINYINT,
    hist_cad TINYINT,
    hist_stroke TINYINT,

    hospital_expire_flag TINYINT NOT NULL,

    INDEX idx_subject_id (subject_id),
    INDEX idx_hadm_id (hadm_id),
    INDEX idx_stay_id (stay_id)
);

Use medivision;
SHOW TABLES;
DESCRIBE patient_records;
SELECT COUNT(*) AS total_records
FROM patient_records;
