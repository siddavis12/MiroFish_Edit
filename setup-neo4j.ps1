# MiroFish - Neo4j Community Edition 자동 설정 스크립트
# Java 17/21 체크 → 없으면 winget으로 설치 → Neo4j ZIP 다운로드/설치 → 초기 설정
#
# 사용법: powershell -ExecutionPolicy Bypass -File setup-neo4j.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

# ============== 설정 ==============
$NEO4J_VERSION = "5.26.2"
$NEO4J_DIR_NAME = "neo4j-community-$NEO4J_VERSION"
$NEO4J_HOME = Join-Path $ProjectRoot "neo4j"
$NEO4J_PASSWORD = "mirofish"
$MIN_JAVA_VERSION = 17

# Neo4j 다운로드 URL (Community Edition Windows ZIP)
$NEO4J_ZIP_URL = "https://dist.neo4j.org/neo4j-community-$NEO4J_VERSION-windows.zip"
$NEO4J_ZIP_FILE = Join-Path $ProjectRoot "neo4j-community-$NEO4J_VERSION-windows.zip"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MiroFish - Neo4j 자동 설정" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ============== 1. Java 확인 및 설치 ==============

function Find-JavaHome {
  # 1. 환경변수 JAVA_HOME
  $jh = [System.Environment]::GetEnvironmentVariable("JAVA_HOME", "Machine")
  if ($jh -and (Test-Path "$jh\bin\java.exe")) { return $jh }

  # 2. Adoptium 기본 경로 탐색
  $adoptDir = "C:\Program Files\Eclipse Adoptium"
  if (Test-Path $adoptDir) {
    $jdk = Get-ChildItem $adoptDir -Directory -ErrorAction SilentlyContinue |
      Sort-Object Name -Descending | Select-Object -First 1
    if ($jdk -and (Test-Path "$($jdk.FullName)\bin\java.exe")) { return $jdk.FullName }
  }

  # 3. PATH에서 java 찾기
  $javaCmd = Get-Command java -ErrorAction SilentlyContinue
  if ($javaCmd) { return (Split-Path (Split-Path $javaCmd.Source)) }

  return $null
}

function Get-JavaVersion {
  param([string]$JavaHome)
  try {
    $javaBin = if ($JavaHome) { "$JavaHome\bin\java.exe" } else { "java.exe" }
    if (-not (Test-Path $javaBin)) { return 0 }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $javaBin
    $psi.Arguments = "-version"
    $psi.RedirectStandardError = $true
    $psi.RedirectStandardOutput = $true
    $psi.UseShellExecute = $false
    $p = [System.Diagnostics.Process]::Start($psi)
    $stderr = $p.StandardError.ReadToEnd()
    $p.WaitForExit()
    if ($stderr -match 'version "(\d+)') {
      return [int]$Matches[1]
    }
  } catch {}
  return 0
}

$javaHome = Find-JavaHome
if ($javaHome) {
  $env:JAVA_HOME = $javaHome
  $env:Path = "$javaHome\bin;$($env:Path)"
}
$javaVer = Get-JavaVersion -JavaHome $javaHome

if ($javaVer -ge $MIN_JAVA_VERSION) {
  Write-Host "[OK] Java $javaVer 감지됨" -ForegroundColor Green
} else {
  $currentJava = if ($javaVer -eq 0) { "미설치" } else { "$javaVer" }
  Write-Host "[주의] Java $MIN_JAVA_VERSION 이상이 필요합니다 (현재: $currentJava)" -ForegroundColor Yellow
  Write-Host ""

  # winget 확인
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "[오류] winget이 설치되어 있지 않습니다." -ForegroundColor Red
    Write-Host "       수동으로 JDK 21을 설치해주세요: https://adoptium.net/temurin/releases/" -ForegroundColor Red
    exit 1
  }

  Write-Host ">> winget으로 Eclipse Temurin JDK 21 설치 중..." -ForegroundColor Cyan
  Write-Host "   (관리자 권한 요청이 발생할 수 있습니다)" -ForegroundColor Gray
  Write-Host ""

  winget install -e --id EclipseAdoptium.Temurin.21.JDK --accept-source-agreements --accept-package-agreements

  # 설치 후 Find-JavaHome으로 재탐색
  $javaHome = Find-JavaHome
  if ($javaHome) {
    $env:JAVA_HOME = $javaHome
    $env:Path = "$javaHome\bin;$($env:Path)"
  }
  $javaVer = Get-JavaVersion -JavaHome $javaHome
  if ($javaVer -ge $MIN_JAVA_VERSION) {
    Write-Host "[OK] Java $javaVer 설치 완료" -ForegroundColor Green
  } else {
    Write-Host "[경고] Java 설치 후 터미널을 재시작해야 할 수 있습니다." -ForegroundColor Yellow
    Write-Host "       터미널을 닫고 다시 열어서 이 스크립트를 재실행하세요." -ForegroundColor Yellow
    exit 1
  }
}

Write-Host ""

# ============== 2. Neo4j 다운로드 및 설치 ==============

# 이미 설치되어 있는지 확인
$neo4jBin = Join-Path $NEO4J_HOME "bin\neo4j.bat"

if (Test-Path $neo4jBin) {
  Write-Host "[OK] Neo4j 이미 설치됨: $NEO4J_HOME" -ForegroundColor Green
} else {
  Write-Host ">> Neo4j Community $NEO4J_VERSION 다운로드 중..." -ForegroundColor Cyan

  # 다운로드
  if (-not (Test-Path $NEO4J_ZIP_FILE)) {
    try {
      # TLS 1.2 강제 (일부 Windows에서 필요)
      [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

      Write-Host "   URL: $NEO4J_ZIP_URL" -ForegroundColor Gray
      Invoke-WebRequest -Uri $NEO4J_ZIP_URL -OutFile $NEO4J_ZIP_FILE -UseBasicParsing
      Write-Host "[OK] 다운로드 완료" -ForegroundColor Green
    } catch {
      Write-Host "[오류] 다운로드 실패: $_" -ForegroundColor Red
      Write-Host "" -ForegroundColor Red
      Write-Host "수동 다운로드:" -ForegroundColor Yellow
      Write-Host "  1. https://neo4j.com/deployment-center/ 접속" -ForegroundColor Yellow
      Write-Host "  2. Neo4j Community Edition $NEO4J_VERSION 선택" -ForegroundColor Yellow
      Write-Host "  3. Windows ZIP 다운로드" -ForegroundColor Yellow
      Write-Host "  4. $NEO4J_HOME 에 압축 해제" -ForegroundColor Yellow
      exit 1
    }
  } else {
    Write-Host "[OK] ZIP 파일 이미 존재: $NEO4J_ZIP_FILE" -ForegroundColor Green
  }

  # 압축 해제
  Write-Host ">> 압축 해제 중..." -ForegroundColor Cyan
  $extractDir = Join-Path $ProjectRoot "_neo4j_extract"

  if (Test-Path $extractDir) {
    Remove-Item -Recurse -Force $extractDir
  }

  Expand-Archive -Path $NEO4J_ZIP_FILE -DestinationPath $extractDir

  # 압축 해제된 폴더를 neo4j로 이동
  $extractedFolder = Get-ChildItem -Path $extractDir -Directory | Select-Object -First 1
  if ($extractedFolder) {
    if (Test-Path $NEO4J_HOME) {
      Remove-Item -Recurse -Force $NEO4J_HOME
    }
    Move-Item -Path $extractedFolder.FullName -Destination $NEO4J_HOME
    Remove-Item -Recurse -Force $extractDir
    Write-Host "[OK] Neo4j 설치 완료: $NEO4J_HOME" -ForegroundColor Green
  } else {
    Write-Host "[오류] 압축 해제 실패" -ForegroundColor Red
    exit 1
  }

  # ZIP 파일 정리
  Remove-Item -Force $NEO4J_ZIP_FILE -ErrorAction SilentlyContinue
}

Write-Host ""

# ============== 3. Neo4j 초기 설정 ==============

# 초기 비밀번호 설정
$passwordFile = Join-Path $NEO4J_HOME "data\dbms\auth.ini"
if (-not (Test-Path $passwordFile)) {
  Write-Host ">> 초기 비밀번호 설정 중 ($NEO4J_PASSWORD)..." -ForegroundColor Cyan

  $adminBat = Join-Path $NEO4J_HOME "bin\neo4j-admin.bat"
  & $adminBat dbms set-initial-password $NEO4J_PASSWORD 2>&1 | Out-Null

  if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] 비밀번호 설정 완료 (neo4j / $NEO4J_PASSWORD)" -ForegroundColor Green
  } else {
    Write-Host "[경고] 비밀번호 설정 실패 - 첫 로그인 시 수동 변경 필요" -ForegroundColor Yellow
  }
} else {
  Write-Host "[OK] 비밀번호 이미 설정됨" -ForegroundColor Green
}

# neo4j.conf에서 Bolt/HTTP 포트 확인 (기본값 유지)
$confFile = Join-Path $NEO4J_HOME "conf\neo4j.conf"
if (Test-Path $confFile) {
  Write-Host "[OK] 설정 파일: $confFile" -ForegroundColor Green
}

Write-Host ""

# ============== 4. .gitignore 업데이트 ==============

$gitignore = Join-Path $ProjectRoot ".gitignore"
if (Test-Path $gitignore) {
  $content = Get-Content $gitignore -Raw
  if ($content -notmatch "(?m)^neo4j/") {
    Write-Host ">> .gitignore에 neo4j/ 추가 중..." -ForegroundColor Cyan
    Add-Content $gitignore "`n# Neo4j Community Edition (로컬 설치)`nneo4j/"
    Write-Host "[OK] .gitignore 업데이트 완료" -ForegroundColor Green
  }
}

Write-Host ""

# ============== 5. 완료 안내 ==============

Write-Host "========================================" -ForegroundColor Green
Write-Host "  Neo4j 설정 완료!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  설치 경로 : $NEO4J_HOME" -ForegroundColor White
Write-Host "  Bolt 포트  : bolt://localhost:7687" -ForegroundColor White
Write-Host "  HTTP 포트  : http://localhost:7474 (Browser)" -ForegroundColor White
Write-Host "  인증 정보  : neo4j / $NEO4J_PASSWORD" -ForegroundColor White
Write-Host ""
Write-Host "  시작: .\start-neo4j.ps1" -ForegroundColor Cyan
Write-Host "  종료: .\stop-neo4j.ps1" -ForegroundColor Cyan
Write-Host ""
