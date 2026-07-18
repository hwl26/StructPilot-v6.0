param(
    [string]$Version = "5.1"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$DistRoot = Join-Path $Root "dist"
$PackageName = "StructPilot_v$Version"
$PackageDir = Join-Path $DistRoot $PackageName
$ZipPath = Join-Path $DistRoot "$PackageName.zip"
$HashPath = "$ZipPath.sha256"

$ExcludedDirs = @(
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "runtime",
    "dist",
    "logs",
    ".reasonix",
    ".claude"
)

$ExcludedFiles = @(
    ".env",
    "config/llm_config.json",
    "config/ui_settings.json",
    "streamlit.log"
)

$ExcludedExtensions = @(
    ".log",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pyc",
    ".tmp",
    ".temp"
)

function Test-IsExcludedPath {
    param([string]$RelativePath)

    $normalized = $RelativePath.Replace("\", "/")
    foreach ($dir in $ExcludedDirs) {
        if ($normalized -eq $dir -or $normalized.StartsWith("$dir/")) {
            return $true
        }
    }
    foreach ($file in $ExcludedFiles) {
        if ($normalized -eq $file) {
            return $true
        }
    }
    $ext = [System.IO.Path]::GetExtension($normalized)
    return $ExcludedExtensions -contains $ext
}

New-Item -ItemType Directory -Force -Path $DistRoot | Out-Null
if (Test-Path $PackageDir) {
    Remove-Item -LiteralPath $PackageDir -Recurse -Force
}
if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
if (Test-Path $HashPath) {
    Remove-Item -LiteralPath $HashPath -Force
}
New-Item -ItemType Directory -Force -Path $PackageDir | Out-Null

$rootFull = (Resolve-Path $Root).Path
Get-ChildItem -LiteralPath $Root -Recurse -File | ForEach-Object {
    $relative = $_.FullName.Substring($rootFull.Length).TrimStart("\", "/")
    if (-not (Test-IsExcludedPath $relative)) {
        $target = Join-Path $PackageDir $relative
        $targetDir = Split-Path -Parent $target
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $target -Force
    }
}

Compress-Archive -LiteralPath $PackageDir -DestinationPath $ZipPath -Force
$hash = Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256
"$($hash.Hash)  $([System.IO.Path]::GetFileName($ZipPath))" | Set-Content -LiteralPath $HashPath -Encoding ASCII

Write-Host "Release package created:"
Write-Host "  $ZipPath"
Write-Host "  $HashPath"
