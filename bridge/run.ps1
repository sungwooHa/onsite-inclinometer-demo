# run.ps1 — Windows에서 ESP32 브리지 실행 헬퍼
#
# 문제: Windows는 블루투스 SPP의 "나가는(outgoing)" COM 번호를 페어링/연결마다 다시
#       배정해서, config.yaml 에 박아둔 COM 번호가 자주 어긋난다(FileNotFoundError).
# 해결: ESP32 의 MAC(= config.yaml 의 serial.bt_address)이 박힌 outgoing COM 포트를
#       실행 직전에 매번 자동 탐지해 쓴다. COM 번호가 바뀌어도 이 스크립트만 돌리면 된다.
#
# 사용:  .\run.ps1                  # 실전(실제 POST)
#        .\run.ps1 --monitor        # 블루투스 수신만(POST 없음)
#        .\run.ps1 --check          # 저장된 계측값 확인
#        .\run.ps1 --dry-run        # 페이로드만 미리보기
#   (인자는 bridge.py 로 그대로 전달된다)
#
# 사전 준비: Windows BT 설정에서 ESP32(MIDAS_ONSITE_SENSOR) 페어링, config.yaml 작성
#            (serial.bt_address 에 ESP32 MAC). config.local.yaml 은 이 스크립트가 자동 생성.
param([Parameter(ValueFromRemainingArguments=$true)] $Extra)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# 1) config.yaml 에서 ESP32 MAC(serial.bt_address) 읽기 → 콜론 제거(장치ID 표기와 맞춤)
$cfg = Get-Content config.yaml -Raw
if ($cfg -notmatch 'bt_address:\s*"?([0-9A-Fa-f:]+)"?') {
  Write-Host "[run] config.yaml 에 serial.bt_address 가 없습니다. ESP32 MAC 을 먼저 넣어주세요." -ForegroundColor Red
  exit 1
}
$mac = ($Matches[1] -replace ':','').ToUpper()

# 2) MAC 이 박힌 outgoing 직렬포트 자동 탐지
$port = Get-CimInstance Win32_SerialPort |
  Where-Object { $_.PNPDeviceID -match $mac } |
  Select-Object -First 1 -ExpandProperty DeviceID

if (-not $port) {
  Write-Host "[run] outgoing COM 못 찾음 (MAC $mac). ESP32 전원/페어링을 확인하고 다시 실행하세요." -ForegroundColor Red
  Write-Host "[run] 현재 직렬포트 목록:"
  Get-CimInstance Win32_SerialPort | Select-Object DeviceID, Name | Format-Table -AutoSize
  exit 1
}
Write-Host "[run] outgoing COM = $port (MAC $mac)" -ForegroundColor Green

# 3) config.yaml 의 포트만 바꿔 config.local.yaml 생성(토큰 등 나머지는 config.yaml 그대로 따름)
($cfg -replace 'port:\s*".*?"', "port: `"$port`"") | Set-Content config.local.yaml -Encoding UTF8
Write-Host "[run] config.local.yaml 갱신: port = $port"

# 4) python 으로 브리지 실행(추가 인자 그대로 전달)
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $py) { Write-Host "[run] python 을 찾을 수 없습니다. Python 설치 후 PATH 확인." -ForegroundColor Red; exit 1 }
Write-Host "[run] 실행: bridge.py --config config.local.yaml $Extra" -ForegroundColor Cyan
& $py bridge.py --config config.local.yaml @Extra
