#!/bin/sh
set -eu
# psql quoted variables protect identifiers/literals; no SQL string concatenation.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=account_password="$ACCOUNT_DB_PASSWORD" \
  --set=job_password="$JOB_DB_PASSWORD" \
  --set=application_password="$APPLICATION_DB_PASSWORD" <<'SQL'
CREATE USER account_user PASSWORD :'account_password';
CREATE USER job_user PASSWORD :'job_password';
CREATE USER application_user PASSWORD :'application_password';
CREATE DATABASE account_db OWNER account_user;
CREATE DATABASE job_db OWNER job_user;
CREATE DATABASE application_db OWNER application_user;
REVOKE CONNECT ON DATABASE account_db FROM PUBLIC;
REVOKE CONNECT ON DATABASE job_db FROM PUBLIC;
REVOKE CONNECT ON DATABASE application_db FROM PUBLIC;
GRANT CONNECT ON DATABASE account_db TO account_user;
GRANT CONNECT ON DATABASE job_db TO job_user;
GRANT CONNECT ON DATABASE application_db TO application_user;
SQL
