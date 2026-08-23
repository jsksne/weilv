[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$fileSystem = New-Object -ComObject Scripting.FileSystemObject
$shortProjectRoot = $fileSystem.GetFolder($projectRoot).ShortPath
$elasticsearchHome = Join-Path $shortProjectRoot '.runtime\elasticsearch-8.19.18'
$elasticsearchBat = Join-Path $elasticsearchHome 'bin\elasticsearch.bat'
$dataPath = Join-Path $shortProjectRoot '.runtime\es-data'

if (-not (Test-Path -LiteralPath $elasticsearchBat)) {
    throw "Elasticsearch 8.19.18 was not found: $elasticsearchBat"
}

$env:ES_JAVA_OPTS = '-Xms512m -Xmx512m'

Write-Host 'Starting the local Weilv Elasticsearch POC...'
Write-Host 'URL: http://127.0.0.1:9200'
Write-Warning 'Authentication, TLS, ML, and disk watermarks are disabled for this local POC only.'

$arguments = @(
    '-Ediscovery.type=single-node'
    '-Expack.security.enabled=false'
    '-Expack.ml.enabled=false'
    '-Ecluster.routing.allocation.disk.threshold_enabled=false'
    '-Enetwork.host=127.0.0.1'
    '-Ehttp.port=9200'
    "-Epath.data=$dataPath"
)

& $elasticsearchBat $arguments

if ($LASTEXITCODE -ne 0) {
    throw "Elasticsearch exited unexpectedly with code $LASTEXITCODE"
}
