$ErrorActionPreference = "Stop"
$pgroot = Join-Path $env:LOCALAPPDATA "bgm-postgres"
$bin = Join-Path $pgroot "pgsql\bin\pg_ctl.exe"
$data = Join-Path $pgroot "data"
$log = Join-Path $pgroot "postgres.log"

if (-not (Test-Path $bin)) {
    throw "Local PostgreSQL is missing at $pgroot. Ask the agent to restore the portable server."
}

$status = & $bin -D $data status 2>&1 | Out-String
if ($status -match "server is running") {
    Write-Output "PostgreSQL is already running on 127.0.0.1:5432"
    exit 0
}

& $bin -D $data -l $log start
if ($LASTEXITCODE -ne 0) { throw "pg_ctl start failed" }
Write-Output "PostgreSQL started on 127.0.0.1:5432"
