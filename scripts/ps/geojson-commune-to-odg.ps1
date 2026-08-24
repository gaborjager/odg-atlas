# =============================================================================
# geojson-communes-to-odg.ps1
# Telecharge le GeoJSON des communes francaises et genere un fichier ODG unique.
#
# ATTENTION : ~35 000 communes. Le GeoJSON source fait ~50 Mo.
#             La generation peut prendre plusieurs minutes.
#             Le fichier ODG resultant peut depasser 100 Mo.
#
# Usage :
#   .\geojson-communes-to-odg.ps1
#   .\geojson-communes-to-odg.ps1 -OutputFile "C:\cartes\communes.odg"
# =============================================================================
param([string]$OutputFile = "$PWD\communes-france.odg")

$ErrorActionPreference = "Stop"

# UTF-8 sans BOM -- obligatoire pour XML dans un conteneur ODF
function Write-Utf8NoBom([string]$Path, [string]$Content) {
    [System.IO.File]::WriteAllText($Path, $Content,
        (New-Object System.Text.UTF8Encoding $false))
}

$GeoJsonUrl = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/communes-version-simplifiee.geojson"

# Mise en page
$PageW = 30.0
$PageH = 25.0

# Emprise geographique France metropolitaine
$MLonMin = -5.5;  $MLonMax = 9.7
$MLatMin = 41.2;  $MLatMax = 51.2
$MLonRng = [double]($MLonMax - $MLonMin)
$MLatRng = [double]($MLatMax - $MLatMin)

# Projection equirectangulaire corrigee
$MidLat    = ($MLatMin + $MLatMax) / 2
$CosMidLat = [Math]::Cos($MidLat * [Math]::PI / 180)
$MapH = $PageH
$MapW = [Math]::Min($MapH * ($MLonRng * $CosMidLat) / $MLatRng, $PageW)
$XOff = ($PageW - $MapW) / 2

# Couleur unique bleue, trait tres fin adapte a l'echelle communale
$FillColor   = "#6AAED6"
$StrokeColor = "#1A4F7A"
$StrokeWidth = "0.004cm"

# ── Fonctions ─────────────────────────────────────────────────────────────────

function Get-BBox($geometry) {
    $lons = [System.Collections.Generic.List[double]]::new()
    $lats = [System.Collections.Generic.List[double]]::new()
    $rings = @()
    if ($geometry.type -eq "Polygon")      { $rings = $geometry.coordinates }
    if ($geometry.type -eq "MultiPolygon") { foreach ($p in $geometry.coordinates) { foreach ($r in $p) { $rings += ,$r } } }
    foreach ($ring in $rings) { foreach ($pt in $ring) { $lons.Add([double]$pt[0]); $lats.Add([double]$pt[1]) } }
    return @{
        LonMin = [double]($lons | Measure-Object -Minimum).Minimum
        LonMax = [double]($lons | Measure-Object -Maximum).Maximum
        LatMin = [double]($lats | Measure-Object -Minimum).Minimum
        LatMax = [double]($lats | Measure-Object -Maximum).Maximum
    }
}

function Get-PathData($geometry, [double]$originLon, [double]$originLatMax,
                      [double]$scaleX, [double]$scaleY) {
    $rings = @()
    if ($geometry.type -eq "Polygon")      { $rings = $geometry.coordinates }
    if ($geometry.type -eq "MultiPolygon") { foreach ($p in $geometry.coordinates) { foreach ($r in $p) { $rings += ,$r } } }
    $parts = foreach ($ring in $rings) {
        $sb = New-Object System.Text.StringBuilder
        $first = $true
        foreach ($pt in $ring) {
            $x = [Math]::Round(([double]$pt[0] - $originLon)    * $scaleX, 1)
            $y = [Math]::Round(($originLatMax - [double]$pt[1]) * $scaleY, 1)
            if ($first) { [void]$sb.Append("M $x $y"); $first = $false }
            else         { [void]$sb.Append(" L $x $y") }
        }
        [void]$sb.Append(" Z")
        $sb.ToString()
    }
    return $parts -join " "
}

function Escape-Xml([string]$s) {
    $s -replace '&','&amp;' -replace '<','&lt;' -replace '>','&gt;' `
       -replace '"','&quot;' -replace "'","&apos;"
}

# =============================================================================
Write-Host ""
Write-Host "=== GeoJSON -> ODG : Communes de France ===" -ForegroundColor Cyan
Write-Host "    (fichier source ~50 Mo, generation de plusieurs minutes)" -ForegroundColor DarkYellow

Write-Host "[1/4] Telechargement du GeoJSON..." -ForegroundColor Yellow
$GeoJson = Invoke-RestMethod -Uri $GeoJsonUrl
Write-Host "      -> $($GeoJson.features.Count) communes chargees." -ForegroundColor Green

Write-Host "[2/4] Conversion des geometries..." -ForegroundColor Yellow

$sbStyles = New-Object System.Text.StringBuilder
$sbShapes = New-Object System.Text.StringBuilder
$i = 0

foreach ($feat in $GeoJson.features) {
    $code = $feat.properties.code
    $nom  = Escape-Xml $feat.properties.nom

    $b      = Get-BBox $feat.geometry
    $lonRng = [Math]::Max([double]($b.LonMax - $b.LonMin), [double]0.0001)
    $latRng = [Math]::Max([double]($b.LatMax - $b.LatMin), [double]0.0001)

    $xCm = [Math]::Round($XOff + ($b.LonMin - $MLonMin) / $MLonRng * $MapW, 4)
    $yCm = [Math]::Round(($MLatMax - $b.LatMax) / $MLatRng * $MapH, 4)
    $wCm = [Math]::Round($lonRng / $MLonRng * $MapW, 4)
    $hCm = [Math]::Round($latRng / $MLatRng * $MapH, 4)

    $vbW = [Math]::Max(1, [long]($wCm * 1000))
    $vbH = [Math]::Max(1, [long]($hCm * 1000))
    $sX  = [double]$vbW / $lonRng
    $sY  = [double]$vbH / $latRng

    $pathData  = Get-PathData $feat.geometry $b.LonMin $b.LatMax $sX $sY
    $styleName = "s$i"

    [void]$sbStyles.AppendLine(
        "    <style:style style:name=`"$styleName`" style:family=`"graphic`" " +
        "style:parent-style-name=`"base`"><style:graphic-properties " +
        "draw:fill=`"solid`" draw:fill-color=`"$FillColor`" draw:stroke=`"solid`" " +
        "svg:stroke-color=`"$StrokeColor`" svg:stroke-width=`"$StrokeWidth`" " +
        "draw:shadow=`"hidden`" fo:padding=`"0cm`"/></style:style>"
    )
    [void]$sbShapes.AppendLine(
        "      <draw:path draw:style-name=`"$styleName`" draw:name=`"$code`"" +
        " draw:layer=`"layout`"" +
        " svg:x=`"${xCm}cm`" svg:y=`"${yCm}cm`"" +
        " svg:width=`"${wCm}cm`" svg:height=`"${hCm}cm`"" +
        " svg:viewBox=`"0 0 $vbW $vbH`"" +
        " svg:d=`"$pathData`">" +
        "<svg:desc>$code - $nom</svg:desc></draw:path>"
    )
    $i++
    if ($i % 1000 -eq 0) { Write-Host "      $i / $($GeoJson.features.Count) traites..." -ForegroundColor DarkGray }
}

Write-Host "      -> $i communes." -ForegroundColor Green

Write-Host "[3/4] Generation de l'archive ODG..." -ForegroundColor Yellow

$TempDir = Join-Path $env:TEMP "odg_$(Get-Random)"
New-Item -ItemType Directory -Force -Path "$TempDir\META-INF" | Out-Null

[System.IO.File]::WriteAllText(
    "$TempDir\mimetype",
    "application/vnd.oasis.opendocument.graphics",
    [System.Text.Encoding]::ASCII)

Write-Utf8NoBom "$TempDir\META-INF\manifest.xml" @'
<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"
                   manifest:version="1.3">
  <manifest:file-entry manifest:full-path="/"
                       manifest:version="1.3"
                       manifest:media-type="application/vnd.oasis.opendocument.graphics"/>
  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
  <manifest:file-entry manifest:full-path="styles.xml"  manifest:media-type="text/xml"/>
</manifest:manifest>
'@

Write-Utf8NoBom "$TempDir\styles.xml" @"
<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
  xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
  xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
  office:version="1.3">
  <office:styles>
    <style:style style:name="base" style:family="graphic">
      <style:graphic-properties draw:fill="solid" draw:fill-color="#CCCCCC"
        draw:stroke="solid" svg:stroke-color="#000000" svg:stroke-width="0.02cm"
        draw:shadow="hidden"
        xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"/>
    </style:style>
  </office:styles>
  <office:automatic-styles>
    <style:page-layout style:name="PM1">
      <style:page-layout-properties
        fo:page-width="${PageW}cm" fo:page-height="${PageH}cm"
        fo:margin-top="0cm" fo:margin-bottom="0cm"
        fo:margin-left="0cm" fo:margin-right="0cm"
        style:print-orientation="landscape"/>
    </style:page-layout>
  </office:automatic-styles>
  <office:master-styles>
    <style:master-page style:name="Default" style:page-layout-name="PM1"/>
  </office:master-styles>
</office:document-styles>
"@

Write-Host "[4/4] Ecriture du fichier ODG..." -ForegroundColor Yellow

Write-Utf8NoBom "$TempDir\content.xml" @"
<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
  xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
  xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
  xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
  office:version="1.3">
  <office:automatic-styles>
$($sbStyles.ToString())
  </office:automatic-styles>
  <office:body>
    <office:drawing>
      <draw:page draw:name="Communes de France"
                 draw:master-page-name="Default">
$($sbShapes.ToString())
      </draw:page>
    </office:drawing>
  </office:body>
</office:document-content>
"@

if (Test-Path $OutputFile) { Remove-Item $OutputFile -Force }

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::Open($OutputFile, 'Create')
try {
    $mimeEntry  = $zip.CreateEntry("mimetype", [System.IO.Compression.CompressionLevel]::NoCompression)
    $mimeStream = $mimeEntry.Open()
    $mimeBytes  = [System.Text.Encoding]::ASCII.GetBytes("application/vnd.oasis.opendocument.graphics")
    $mimeStream.Write($mimeBytes, 0, $mimeBytes.Length)
    $mimeStream.Close()

    foreach ($f in (Get-ChildItem -Recurse -File $TempDir | Where-Object { $_.Name -ne "mimetype" })) {
        $entryName = $f.FullName.Substring($TempDir.Length + 1).Replace('\', '/')
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $zip, $f.FullName, $entryName,
            [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
    }
}
finally { $zip.Dispose() }

Remove-Item -Recurse -Force $TempDir

$size = [Math]::Round((Get-Item $OutputFile).Length / 1MB, 1)
Write-Host ""
Write-Host "=== Termine ===" -ForegroundColor Cyan
Write-Host "Fichier : $OutputFile  (${size} Mo)" -ForegroundColor Green
Write-Host "Page    : ${PageW} cm x ${PageH} cm  |  $i communes" -ForegroundColor Green
Write-Host "Ouvrez avec LibreOffice Draw." -ForegroundColor DarkGray
