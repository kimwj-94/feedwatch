$ErrorActionPreference = "Stop"

$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$packageName = "FeedWatch_v1.0_Setup"
$distDir = Join-Path $root "dist"
$packageDir = Join-Path $distDir $packageName
$exePath = Join-Path $distDir "FeedWatch.exe"

if (-not (Test-Path -LiteralPath $exePath)) {
  Write-Host "FeedWatch.exe not found. Building first..."
  powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "build_exe.ps1")
}

if (Test-Path -LiteralPath $packageDir) {
  Remove-Item -LiteralPath $packageDir -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $packageDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $packageDir "data") | Out-Null

Copy-Item -LiteralPath $exePath -Destination (Join-Path $packageDir "FeedWatch.exe")
Copy-Item -LiteralPath (Join-Path $root ".env.example") -Destination (Join-Path $packageDir ".env.example")
Copy-Item -LiteralPath (Join-Path $root "firebase_config.example.json") -Destination (Join-Path $packageDir "firebase_config.example.json")
Copy-Item -LiteralPath (Join-Path $root "README.md") -Destination (Join-Path $packageDir "README.md")
Copy-Item -LiteralPath (Join-Path $root "OPERATIONS_CHECKLIST.md") -Destination (Join-Path $packageDir "OPERATIONS_CHECKLIST.md")
Copy-Item -LiteralPath (Join-Path $root "firestore.rules") -Destination (Join-Path $packageDir "firestore.rules")

@"
# FeedWatch 가족 PC 설치 안내

1. 이 폴더를 가족 PC의 원하는 위치로 복사합니다. 예: C:\FeedWatch
2. .env.example을 .env로 복사하고 필요한 값을 채웁니다.
3. firebase_config.example.json을 firebase_config.json으로 복사하고 Firebase client 설정을 채웁니다.
4. FeedWatch.exe를 실행합니다.
5. 처음에는 로컬 모드로 들어갈 수 있고, Firebase/Google 로그인은 설정 완료 후 사용합니다.
6. 운영 전 OPERATIONS_CHECKLIST.md를 순서대로 확인합니다.

주의:
- service_account.json, client_secret.json, token.json 같은 민감 파일은 GitHub에 올리지 마세요.
- 로그인 필요 사이트를 등록하려면 .env의 FEEDWATCH_ENCRYPTION_KEY가 필요합니다.
"@ | Set-Content -LiteralPath (Join-Path $packageDir "INSTALL.md") -Encoding UTF8

Compress-Archive -LiteralPath $packageDir -DestinationPath (Join-Path $distDir "$packageName.zip") -Force
Write-Host "Package complete: $packageDir"
Write-Host "Zip complete: $(Join-Path $distDir "$packageName.zip")"
