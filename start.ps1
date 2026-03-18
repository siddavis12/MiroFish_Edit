# MiroFish 프론트엔드 + 백엔드 실행 스크립트
# 사전 요구사항: Node.js >= 18, Python 3.11~3.12, uv

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

# 콘솔 인코딩을 UTF-8로 설정 (한국어 깨짐 방지)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
chcp 65001 | Out-Null

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MiroFish 실행 스크립트" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 사전 요구사항 확인
$missing = @()

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  $missing += "Node.js (>= 18)"
} else {
  $nodeVer = (node -v)
  Write-Host "[OK] Node.js $nodeVer" -ForegroundColor Green
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  $missing += "Python (3.11 ~ 3.12)"
} else {
  $pyVer = (python --version)
  Write-Host "[OK] $pyVer" -ForegroundColor Green
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  $missing += "uv (Python 패키지 관리자)"
} else {
  $uvVer = (uv --version)
  Write-Host "[OK] $uvVer" -ForegroundColor Green
}

if ($missing.Count -gt 0) {
  Write-Host ""
  Write-Host "[오류] 다음 도구가 설치되어 있지 않습니다:" -ForegroundColor Red
  $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
  exit 1
}

# Neo4j 실행 여부 확인 및 자동 시작
$neo4jBat = Join-Path $ProjectRoot "neo4j\bin\neo4j.bat"
if (Test-Path $neo4jBat) {
  $neo4jRunning = $false
  try {
    $conn = New-Object System.Net.Sockets.TcpClient
    $conn.Connect("localhost", 7687)
    $conn.Close()
    $neo4jRunning = $true
  } catch {}

  if ($neo4jRunning) {
    Write-Host "[OK] Neo4j (bolt://localhost:7687)" -ForegroundColor Green
  } else {
    Write-Host ">> Neo4j 시작 중..." -ForegroundColor Cyan

    # JAVA_HOME 확인
    if (-not $env:JAVA_HOME) {
      $machineJavaHome = [System.Environment]::GetEnvironmentVariable("JAVA_HOME", "Machine")
      if ($machineJavaHome) { $env:JAVA_HOME = $machineJavaHome }
    }

    # 백그라운드 프로세스로 Neo4j console 모드 시작 (PID 추적)
    $env:NEO4J_HOME = Join-Path $ProjectRoot "neo4j"
    $neo4jProc = Start-Process powershell -ArgumentList "-WindowStyle Hidden -Command `"& '$neo4jBat' console`"" -WindowStyle Hidden -PassThru
    $neo4jPid = $neo4jProc.Id

    # 연결 대기 (최대 30초)
    $waited = 0
    $maxWait = 30
    while ($waited -lt $maxWait) {
      Start-Sleep -Seconds 2
      $waited += 2
      try {
        $conn = New-Object System.Net.Sockets.TcpClient
        $conn.Connect("localhost", 7687)
        $conn.Close()
        $neo4jRunning = $true
        break
      } catch {}
      Write-Host "  Neo4j 대기 중... ($waited/$maxWait 초)" -ForegroundColor Gray
    }

    if ($neo4jRunning) {
      Write-Host "[OK] Neo4j 시작 완료 (bolt://localhost:7687)" -ForegroundColor Green
    } else {
      Write-Host "[경고] Neo4j 시작 시간 초과 — 수동 확인 필요: .\start-neo4j.ps1" -ForegroundColor Yellow
    }
  }
} else {
  Write-Host "[경고] Neo4j 미설치 — 설정: .\setup-neo4j.ps1" -ForegroundColor Yellow
}

# .env 파일 확인
$envFile = Join-Path $ProjectRoot ".env"
$envExample = Join-Path $ProjectRoot ".env.example"

if (-not (Test-Path $envFile)) {
  if (Test-Path $envExample) {
    Write-Host ""
    Write-Host "[경고] .env 파일이 없습니다. .env.example에서 복사합니다." -ForegroundColor Yellow
    Copy-Item $envExample $envFile
    Write-Host "[안내] $envFile 에 LLM_API_KEY를 설정한 후 다시 실행하세요." -ForegroundColor Yellow
    exit 1
  } else {
    Write-Host ""
    Write-Host "[경고] .env 파일이 없습니다. 백엔드 실행 시 환경변수 오류가 발생할 수 있습니다." -ForegroundColor Yellow
  }
}

# 의존성 설치
Write-Host ""
Write-Host ">> 의존성 설치 중..." -ForegroundColor Cyan

# 루트 node_modules
if (-not (Test-Path (Join-Path $ProjectRoot "node_modules"))) {
  Write-Host "  루트 npm install..." -ForegroundColor Gray
  Push-Location $ProjectRoot
  $ErrorActionPreference = "Continue"
  $null = & npm install --legacy-peer-deps 2>&1
  $ErrorActionPreference = "Stop"
  Pop-Location
}

# 프론트엔드 node_modules
$frontendDir = Join-Path $ProjectRoot "frontend"
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
  Write-Host "  프론트엔드 npm install..." -ForegroundColor Gray
  Push-Location $frontendDir
  $ErrorActionPreference = "Continue"
  $null = & npm install --legacy-peer-deps 2>&1
  $ErrorActionPreference = "Stop"
  Pop-Location
}

# 백엔드 Python 의존성
Write-Host "  백엔드 uv sync..." -ForegroundColor Gray
Push-Location (Join-Path $ProjectRoot "backend")
$ErrorActionPreference = "Continue"
$uvOutput = & uv sync 2>&1
$uvExit = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($uvExit -ne 0) {
  Write-Host "[오류] uv sync 실패:" -ForegroundColor Red
  $uvOutput | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
  Pop-Location
  exit 1
}
Pop-Location

Write-Host "[OK] 의존성 설치 완료" -ForegroundColor Green

# 프론트엔드 & 백엔드 동시 실행
Write-Host ""
Write-Host ">> 서버 시작 중..." -ForegroundColor Cyan
Write-Host "  백엔드:    http://localhost:5001" -ForegroundColor Green
Write-Host "  프론트엔드: http://localhost:3000" -ForegroundColor Green
Write-Host ""
Write-Host "종료하려면 Ctrl+C를 누르세요." -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

# 프로세스 정리 함수
function Stop-AllDevProcesses {
  Write-Host ""
  Write-Host ">> 프로세스 정리 중..." -ForegroundColor Yellow

  # 백엔드 Flask 프로세스 정리 (포트 5001 점유 프로세스)
  try {
    $flaskPids = (netstat -ano 2>$null | Select-String ":5001\s.*LISTENING" |
      ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique)
    foreach ($pid in $flaskPids) {
      if ($pid -and $pid -ne '0') {
        taskkill /F /T /PID $pid 2>$null | Out-Null
      }
    }
  } catch {}

  # 프론트엔드 Vite 프로세스 정리 (포트 3000 점유 프로세스)
  try {
    $vitePids = (netstat -ano 2>$null | Select-String ":3000\s.*LISTENING" |
      ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique)
    foreach ($pid in $vitePids) {
      if ($pid -and $pid -ne '0') {
        taskkill /F /T /PID $pid 2>$null | Out-Null
      }
    }
  } catch {}

  # node 자식 프로세스 정리 (concurrently가 남긴 고아 프로세스)
  try {
    Get-Process -Name "node" -ErrorAction SilentlyContinue |
      Where-Object { $_.MainWindowTitle -eq "" } |
      Stop-Process -Force -ErrorAction SilentlyContinue
  } catch {}

  # Neo4j 정리 — neo4j.bat stop 우선, 실패 시 PID 강제 종료
  if (Test-Path $neo4jBat) {
    Write-Host "  Neo4j 종료 중..." -ForegroundColor Gray
    & $neo4jBat stop 2>$null
    if ($neo4jPid) {
      try { taskkill /F /T /PID $neo4jPid 2>$null | Out-Null } catch {}
    }
  }

  Write-Host "[OK] 모든 프로세스 정리 완료" -ForegroundColor Green
}

# concurrently로 프론트엔드 + 백엔드 동시 실행
Push-Location $ProjectRoot
try {
  npm run dev
} finally {
  Pop-Location
  Stop-AllDevProcesses
}
