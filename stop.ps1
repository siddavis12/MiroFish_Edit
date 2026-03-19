# MiroFish - 전체 서비스 종료 스크립트
# 각 창에서 Ctrl+C로 종료하지 못했을 때 이 스크립트를 실행하세요.

$ErrorActionPreference = "Continue"
$ProjectRoot = $PSScriptRoot

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

Write-Host "========================================" -ForegroundColor Yellow
Write-Host "  MiroFish 서비스 종료" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""

# ── 1. Neo4j 종료 ──────────────────────────────
$neo4jBat = Join-Path $ProjectRoot "neo4j\bin\neo4j.bat"
if (Test-Path $neo4jBat) {
  Write-Host ">> Neo4j 종료 중..." -ForegroundColor Cyan

  # JAVA_HOME 설정
  if (-not $env:JAVA_HOME) {
    $machineJavaHome = [System.Environment]::GetEnvironmentVariable("JAVA_HOME", "Machine")
    if ($machineJavaHome) { $env:JAVA_HOME = $machineJavaHome }
  }
  $env:NEO4J_HOME = Join-Path $ProjectRoot "neo4j"

  & $neo4jBat stop 2>$null | Out-Null
  Write-Host "[OK] Neo4j 종료 요청 완료" -ForegroundColor Green
} else {
  Write-Host "[건너뜀] Neo4j 미설치" -ForegroundColor Gray
}

# ── 2. 포트 5001 (백엔드 Flask) 종료 ──────────
Write-Host ">> 백엔드 (:5001) 종료 중..." -ForegroundColor Cyan
$killed = $false
try {
  $lines = netstat -ano 2>$null | Select-String ":5001\s.*LISTENING"
  foreach ($line in $lines) {
    $pid = ($line -split '\s+')[-1]
    if ($pid -match '^\d+$' -and $pid -ne '0') {
      taskkill /F /T /PID $pid 2>$null | Out-Null
      $killed = $true
    }
  }
} catch {}
if ($killed) {
  Write-Host "[OK] 백엔드 프로세스 종료" -ForegroundColor Green
} else {
  Write-Host "[건너뜀] :5001 포트 사용 중인 프로세스 없음" -ForegroundColor Gray
}

# ── 3. 포트 3000 (프론트엔드 Vite) 종료 ───────
Write-Host ">> 프론트엔드 (:3000) 종료 중..." -ForegroundColor Cyan
$killed = $false
try {
  $lines = netstat -ano 2>$null | Select-String ":3000\s.*LISTENING"
  foreach ($line in $lines) {
    $pid = ($line -split '\s+')[-1]
    if ($pid -match '^\d+$' -and $pid -ne '0') {
      taskkill /F /T /PID $pid 2>$null | Out-Null
      $killed = $true
    }
  }
} catch {}
if ($killed) {
  Write-Host "[OK] 프론트엔드 프로세스 종료" -ForegroundColor Green
} else {
  Write-Host "[건너뜀] :3000 포트 사용 중인 프로세스 없음" -ForegroundColor Gray
}

# ── 4. 고아 node 프로세스 정리 ─────────────────
Write-Host ">> 고아 node 프로세스 확인 중..." -ForegroundColor Cyan
try {
  $orphans = Get-Process -Name "node" -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowTitle -eq "" }
  if ($orphans) {
    $orphans | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] node 고아 프로세스 $($orphans.Count)개 종료" -ForegroundColor Green
  } else {
    Write-Host "[건너뜀] 고아 node 프로세스 없음" -ForegroundColor Gray
  }
} catch {}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  모든 서비스 종료 완료" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
