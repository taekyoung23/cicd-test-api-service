CREATE TABLE tenants (
  tenant_id VARCHAR(64) PRIMARY KEY,
  tenant_display_name VARCHAR(100) NOT NULL,
  plan ENUM('paid') NOT NULL DEFAULT 'paid',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
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

ALTER TABLE inference_requests
ADD COLUMN tenant_id VARCHAR(64) NULL AFTER user_id,
ADD INDEX idx_tenant_id (tenant_id);
