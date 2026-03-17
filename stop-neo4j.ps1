# MiroFish - Neo4j 종료 스크립트
# 사용법: powershell -ExecutionPolicy Bypass -File stop-neo4j.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$NEO4J_HOME = Join-Path $ProjectRoot "neo4j"
$neo4jBat = Join-Path $NEO4J_HOME "bin\neo4j.bat"

if (-not (Test-Path $neo4jBat)) {
  Write-Host "[오류] Neo4j가 설치되어 있지 않습니다." -ForegroundColor Red
  exit 1
}

$env:NEO4J_HOME = $NEO4J_HOME

Write-Host "Neo4j 종료 중..." -ForegroundColor Cyan

# Windows 서비스로 등록된 경우
try {
  & $neo4jBat stop 2>&1
  Write-Host "[OK] Neo4j 종료 완료" -ForegroundColor Green
} catch {
  # 콘솔 모드로 실행 중이면 프로세스 직접 종료
  $neoProcs = Get-Process -Name "java" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "neo4j" -or $_.MainWindowTitle -match "neo4j" }

  if ($neoProcs) {
    $neoProcs | Stop-Process -Force
    Write-Host "[OK] Neo4j 프로세스 종료 완료" -ForegroundColor Green
  } else {
    Write-Host "[OK] 실행 중인 Neo4j가 없습니다" -ForegroundColor Yellow
  }
}
