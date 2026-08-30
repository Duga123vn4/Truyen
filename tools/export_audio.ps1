param(
    [string]$InputFile,
    [string]$OutputFile
)

if (-not $InputFile -or -not (Test-Path $InputFile)) {
    Write-Host "Loi: Khong tim thay file: $InputFile" -ForegroundColor Red
    exit 1
}

$item = Get-Item $InputFile
$baseName = $item.BaseName

if (-not $OutputFile) {
    $rootDir = Join-Path $PSScriptRoot ".."
    $audioDir = Join-Path $rootDir "Chu_Thuat_Su_Dung_Gia\audio"
    if (-not (Test-Path $audioDir)) {
        $audioDir = Join-Path $rootDir "audio"
        if (-not (Test-Path $audioDir)) { New-Item -ItemType Directory -Path $audioDir -Force | Out-Null }
    }
    $OutputFile = Join-Path $audioDir "$baseName.mp3"
}

Write-Host "=== Dang chuyen doi van ban sang MP3 Audio ===" -ForegroundColor Cyan
Write-Host "File nguon: $InputFile"
Write-Host "File dau ra: $OutputFile"

$rawText = [System.IO.File]::ReadAllText($InputFile, [System.Text.Encoding]::UTF8)

# Loai bo cac ky tu markdown
$cleanText = $rawText -replace '(?m)^#+.*$', '' -replace '---+', '' -replace '\*\*|\*|`|\[|\]', '' -replace '『|』|“|”', ' '

$lines = $cleanText -split "`r?\n"
$chunks = New-Object System.Collections.Generic.List[string]

foreach ($line in $lines) {
    $t = $line.Trim()
    if ($t.Length -eq 0) { continue }
    
    while ($t.Length -gt 170) {
        $cutIdx = $t.LastIndexOf(' ', 170)
        if ($cutIdx -le 0) { $cutIdx = 170 }
        $sub = $t.Substring(0, $cutIdx).Trim()
        if ($sub.Length -gt 0) { $chunks.Add($sub) }
        $t = $t.Substring($cutIdx).Trim()
    }
    if ($t.Length -gt 0) {
        $chunks.Add($t)
    }
}

$total = $chunks.Count
Write-Host "Tong so doan cau can chuyen doi: $total" -ForegroundColor Yellow

$outBytes = New-Object System.Collections.Generic.List[byte]
$client = New-Object System.Net.WebClient
$client.Headers.Add("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")

$i = 0
foreach ($chunk in $chunks) {
    $i++
    $percent = [math]::Round(($i / $total) * 100)
    Write-Host "Progress $percent%: Doan $i/$total..." -ForegroundColor Green
    
    $encoded = [System.Uri]::EscapeDataString($chunk)
    $url = "https://translate.google.com/translate_tts?ie=UTF-8&q=$encoded&tl=vi&client=tw-ob"
    
    $success = $false
    $retry = 0
    while (-not $success -and $retry -lt 3) {
        try {
            $bytes = $client.DownloadData($url)
            $outBytes.AddRange($bytes)
            $success = $true
        } catch {
            $retry++
            Start-Sleep -Milliseconds 300
        }
    }
    Start-Sleep -Milliseconds 60
}

[System.IO.File]::WriteAllBytes($OutputFile, $outBytes.ToArray())
$fileSize = (Get-Item $OutputFile).Length
$fileSizeMB = [math]::Round($fileSize / 1MB, 2)
Write-Host "HOAN TAT! File Audio MP3 da tao tai: $OutputFile ($fileSizeMB MB)" -ForegroundColor Cyan
