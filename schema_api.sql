CREATE TABLE IF NOT EXISTS tenants (
  tenant_id VARCHAR(64) PRIMARY KEY,
  tenant_display_name VARCHAR(100) NOT NULL,
  plan ENUM('paid') NOT NULL DEFAULT 'paid',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
  user_id VARCHAR(64) PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  display_name VARCHAR(100) NOT NULL,
  user_type ENUM('free', 'paid', 'admin') NOT NULL DEFAULT 'free',
  tenant_id VARCHAR(64) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  INDEX idx_user_type (user_type),
  INDEX idx_tenant_id (tenant_id),

  CONSTRAINT fk_users_tenant
    FOREIGN KEY (tenant_id)
    REFERENCES tenants(tenant_id)
);

CREATE TABLE IF NOT EXISTS inference_requests (
  request_id VARCHAR(64) PRIMARY KEY,

  user_id VARCHAR(64) NULL,
  tenant_id VARCHAR(64) NULL,

  user_type ENUM('guest', 'free', 'paid') NOT NULL,
  plan ENUM('free', 'paid') NOT NULL,

  input_bucket VARCHAR(128) NOT NULL,
  input_key VARCHAR(512) NOT NULL,

  result_bucket VARCHAR(128) NULL,
  result_key VARCHAR(512) NULL,

  status ENUM('QUEUED', 'PROCESSING', 'SUCCEEDED', 'FAILED') NOT NULL DEFAULT 'QUEUED',

  label VARCHAR(16) NULL,
  confidence DECIMAL(10,8) NULL,
  fake_prob DECIMAL(10,8) NULL,
  real_prob DECIMAL(10,8) NULL,

  model_name VARCHAR(64) NULL,
  model_version VARCHAR(32) NULL,
  inference_time_sec DECIMAL(10,4) NULL,

  error_message TEXT NULL,

  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  completed_at DATETIME NULL,

  INDEX idx_user_id (user_id),
  INDEX idx_tenant_id (tenant_id),
  INDEX idx_user_type (user_type),
  INDEX idx_plan (plan),
  INDEX idx_status (status),
  INDEX idx_created_at (created_at)
);
