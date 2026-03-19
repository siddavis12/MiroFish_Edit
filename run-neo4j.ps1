# MiroFish - Neo4j 실행 창
# start.ps1에 의해 별도 터미널로 열림. 직접 실행도 가능.

param(
  [string]$ProjectRoot = $PSScriptRoot
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$host.UI.RawUI.WindowTitle = "MiroFish | Neo4j"

$neo4jBat = Join-Path $ProjectRoot "neo4j\bin\neo4j.bat"
$neo4jHome = Join-Path $ProjectRoot "neo4j"

if (-not (Test-Path $neo4jBat)) {
  Write-Host "[오류] Neo4j 미설치. .\setup-neo4j.ps1 을 먼저 실행하세요." -ForegroundColor Red
  Read-Host "Enter 키를 눌러 닫기"
  exit 1
}

# JAVA_HOME 설정
if (-not $env:JAVA_HOME) {
  $machineJavaHome = [System.Environment]::GetEnvironmentVariable("JAVA_HOME", "Machine")
  if ($machineJavaHome) { $env:JAVA_HOME = $machineJavaHome }
}
$env:NEO4J_HOME = $neo4jHome

Write-Host "========================================" -ForegroundColor Magenta
Write-Host "  MiroFish | Neo4j" -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Magenta
Write-Host "  Bolt : bolt://localhost:7687" -ForegroundColor Gray
Write-Host "  HTTP : http://localhost:7474" -ForegroundColor Gray
Write-Host "  종료 : Ctrl+C  (또는 stop.ps1)" -ForegroundColor Gray
Write-Host ""

try {
  & $neo4jBat console
} finally {
  # Ctrl+C 또는 비정상 종료 시 반드시 실행
  Write-Host ""
  Write-Host ">> Neo4j 종료 중..." -ForegroundColor Yellow
  try {
    & $neo4jBat stop 2>$null | Out-Null
  } catch {}
  Write-Host "[OK] Neo4j 종료 완료" -ForegroundColor Green
  Write-Host "이 창을 닫으세요." -ForegroundColor Gray
}
