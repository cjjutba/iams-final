param(
    [Parameter(Mandatory = $true)]
    [string]$ModuleId,

    [Parameter(Mandatory = $true)]
    [string]$ModuleName,

    [string]$ModulesRoot = "docs/modules"
)

$ErrorActionPreference = "Stop"

function Convert-ToSlug {
    param([string]$Value)
    $slug = $Value.ToLower() -replace "[^a-z0-9]+", "-" -replace "^-|-$", ""
    return $slug
}

$templatePath = Join-Path $ModulesRoot "TEMPLATE-MODULE-PACK"
if (-not (Test-Path $templatePath)) {
    throw "Template folder not found: $templatePath"
}

$slug = Convert-ToSlug -Value $ModuleName
$targetPath = Join-Path $ModulesRoot ("{0}-{1}" -f $ModuleId, $slug)

if (Test-Path $targetPath) {
    throw "Target module folder already exists: $targetPath"
}

Copy-Item -Path $templatePath -Destination $targetPath -Recurse

# remove helper script from generated pack
$generatedScript = Join-Path $targetPath "create-module.ps1"
if (Test-Path $generatedScript) {
    Remove-Item $generatedScript -Force
}

$files = Get-ChildItem -Path $targetPath -Recurse -File
foreach ($file in $files) {
    $content = Get-Content -Path $file.FullName -Raw
    $content = $content.Replace("<MOD-ID>", $ModuleId)
    $content = $content.Replace("<MODULE-NAME>", $ModuleName)
    Set-Content -Path $file.FullName -Value $content -Encoding UTF8
}

Write-Output "Created module pack: $targetPath"
