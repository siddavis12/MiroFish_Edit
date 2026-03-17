# MiroFish - Neo4j 시작 스크립트
# 사용법: powershell -ExecutionPolicy Bypass -File start-neo4j.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$NEO4J_HOME = Join-Path $ProjectRoot "neo4j"
$neo4jBat = Join-Path $NEO4J_HOME "bin\neo4j.bat"

if (-not (Test-Path $neo4jBat)) {
  Write-Host "[오류] Neo4j가 설치되어 있지 않습니다." -ForegroundColor Red
  Write-Host "       먼저 실행: .\setup-neo4j.ps1" -ForegroundColor Yellow
  exit 1
}

# JAVA_HOME 확인
if (-not $env:JAVA_HOME) {
  # 시스템 환경변수에서 가져오기
  $machineJavaHome = [System.Environment]::GetEnvironmentVariable("JAVA_HOME", "Machine")
  if ($machineJavaHome) {
    $env:JAVA_HOME = $machineJavaHome
  }
}

# 이미 실행 중인지 확인
try {
  $status = & $neo4jBat status 2>&1
  if ($status -match "running") {
    Write-Host "[OK] Neo4j가 이미 실행 중입니다" -ForegroundColor Green
    Write-Host "  Bolt  : bolt://localhost:7687" -ForegroundColor White
    Write-Host "  Browser: http://localhost:7474" -ForegroundColor White
    exit 0
  }
} catch {}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Neo4j 시작 중..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Bolt  : bolt://localhost:7687" -ForegroundColor Green
Write-Host "  Browser: http://localhost:7474" -ForegroundColor Green
Write-Host ""
Write-Host "  종료: Ctrl+C 또는 별도 터미널에서 .\stop-neo4j.ps1" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# NEO4J_HOME 환경변수 설정 (neo4j.bat가 필요로 함)
$env:NEO4J_HOME = $NEO4J_HOME

# 콘솔 모드로 실행 (포그라운드, Ctrl+C로 종료)
& $neo4jBat console
