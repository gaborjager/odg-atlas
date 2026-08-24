# =============================================================================
# geojson-cantons-to-odg.ps1
# Telecharge le GeoJSON des cantons francais et genere un fichier ODG.
#
# Usage :
#   .\geojson-cantons-to-odg.ps1
#   .\geojson-cantons-to-odg.ps1 -OutputFile "C:\cartes\cantons.odg"
# =============================================================================
param([string]$OutputFile = "$PWD\cantons-france.odg")

$ErrorActionPreference = "Stop"

# UTF-8 sans BOM -- obligatoire pour XML dans un conteneur ODF
function Write-Utf8NoBom([string]$Path, [string]$Content) {
    [System.IO.File]::WriteAllText($Path, $Content,
        (New-Object System.Text.UTF8Encoding $false))
}

$GeoJsonUrl     = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/cantons-version-simplifiee.geojson"
$GeoJsonArrUrl  = "https://geo.api.gouv.fr/communes?type=arrondissement-municipal&fields=nom,code&geometry=contour&format=geojson"
# Communes de la Metropole de Lyon (dept 69) -- zones sans cantons
$GeoJsonMetroUrl = "https://geo.api.gouv.fr/communes?codeDepartement=69&fields=nom,code&geometry=contour&format=geojson"

# ── Mise en page ──────────────────────────────────────────────────────────────
$PageW = 30.0
$PageH = 25.0

# Emprise geographique France metropolitaine
$MLonMin = -5.5;  $MLonMax = 9.7
$MLatMin = 41.2;  $MLatMax = 51.2
$MLonRng = $MLonMax - $MLonMin
$MLatRng = $MLatMax - $MLatMin

# Projection equirectangulaire corrigee (cos de la latitude moyenne)
$MidLat    = ($MLatMin + $MLatMax) / 2
$CosMidLat = [Math]::Cos($MidLat * [Math]::PI / 180)
$MapH = $PageH
$MapW = [Math]::Min($MapH * ($MLonRng * $CosMidLat) / $MLatRng, $PageW)
$XOff = ($PageW - $MapW) / 2

# Couleur unique bleue
$FillColor   = "#6AAED6"
$StrokeColor = "#1A4F7A"

# ── Fonctions ─────────────────────────────────────────────────────────────────

function Get-BBox($geometry) {
    $lons = [System.Collections.Generic.List[double]]::new()
    $lats = [System.Collections.Generic.List[double]]::new()
    $rings = @()
    if ($geometry.type -eq "Polygon")      { $rings = $geometry.coordinates }
    if ($geometry.type -eq "MultiPolygon") { foreach ($p in $geometry.coordinates) { foreach ($r in $p) { $rings += ,$r } } }
    foreach ($ring in $rings) { foreach ($pt in $ring) { $lons.Add($pt[0]); $lats.Add($pt[1]) } }
    return @{
        LonMin = ($lons | Measure-Object -Minimum).Minimum
        LonMax = ($lons | Measure-Object -Maximum).Maximum
        LatMin = ($lats | Measure-Object -Minimum).Minimum
        LatMax = ($lats | Measure-Object -Maximum).Maximum
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
            $x = [Math]::Round(($pt[0] - $originLon)    * $scaleX, 1)
            $y = [Math]::Round(($originLatMax - $pt[1]) * $scaleY, 1)
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
Write-Host "=== GeoJSON -> ODG : Cantons de France ===" -ForegroundColor Cyan

Write-Host "[1/4] Telechargement des GeoJSON..." -ForegroundColor Yellow
$GeoJson      = Invoke-RestMethod -Uri $GeoJsonUrl
$GeoJsonArr   = Invoke-RestMethod -Uri $GeoJsonArrUrl
$GeoJsonMetro = Invoke-RestMethod -Uri $GeoJsonMetroUrl
Write-Host "      -> $($GeoJson.features.Count) cantons + $($GeoJsonArr.features.Count) arrondissements + $($GeoJsonMetro.features.Count) communes (Rhone) charges." -ForegroundColor Green

Write-Host "[2/4] Conversion des geometries..." -ForegroundColor Yellow

$sbStyles = New-Object System.Text.StringBuilder
$sbShapes = New-Object System.Text.StringBuilder
$i = 0

# ── Communes du Rhone (69) en fond ───────────────────────────────────────────
# La Metropole de Lyon n'a pas de cantons dans le GeoJSON source.
# On dessine toutes les communes du dept 69 sans bordure visible pour boucher
# les trous, avant que les cantons reels viennent les recouvrir.
foreach ($feat in $GeoJsonMetro.features) {
    $code = $feat.properties.code
    $nom  = Escape-Xml $feat.properties.nom

    $b      = Get-BBox $feat.geometry
    $lonRng = [Math]::Max([double]($b.LonMax - $b.LonMin), [double]0.001)
    $latRng = [Math]::Max([double]($b.LatMax - $b.LatMin), [double]0.001)

    $xCm = [Math]::Round($XOff + ($b.LonMin - $MLonMin) / $MLonRng * $MapW, 4)
    $yCm = [Math]::Round(($MLatMax - $b.LatMax) / $MLatRng * $MapH, 4)
    $wCm = [Math]::Round($lonRng / $MLonRng * $MapW, 4)
    $hCm = [Math]::Round($latRng / $MLatRng * $MapH, 4)

    $vbW = [Math]::Max(1, [long]($wCm * 1000))
    $vbH = [Math]::Max(1, [long]($hCm * 1000))
    $sX  = [double]$vbW / $lonRng
    $sY  = [double]$vbH / $latRng

    $pathData  = Get-PathData $feat.geometry $b.LonMin $b.LatMax $sX $sY
    $styleName = "m$i"

    [void]$sbStyles.AppendLine(
        "    <style:style style:name=`"$styleName`" style:family=`"graphic`" " +
        "style:parent-style-name=`"base`"><style:graphic-properties " +
        "draw:fill=`"solid`" draw:fill-color=`"$FillColor`" draw:stroke=`"solid`" " +
        "svg:stroke-color=`"$StrokeColor`" svg:stroke-width=`"0.018cm`" " +
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
}

# ── Arrondissements municipaux (Paris, Lyon, Marseille) ──────────────────────
# Dessines apres les departements mais avant les cantons : meme style que les
# cantons, ils bouchent les trous avec un decoupage visible.
foreach ($feat in $GeoJsonArr.features) {
    $code = $feat.properties.code
    $nom  = Escape-Xml $feat.properties.nom

    $b      = Get-BBox $feat.geometry
    $lonRng = [Math]::Max([double]($b.LonMax - $b.LonMin), [double]0.001)
    $latRng = [Math]::Max([double]($b.LatMax - $b.LatMin), [double]0.001)

    $xCm = [Math]::Round($XOff + ($b.LonMin - $MLonMin) / $MLonRng * $MapW, 4)
    $yCm = [Math]::Round(($MLatMax - $b.LatMax) / $MLatRng * $MapH, 4)
    $wCm = [Math]::Round($lonRng / $MLonRng * $MapW, 4)
    $hCm = [Math]::Round($latRng / $MLatRng * $MapH, 4)

    $vbW = [Math]::Max(1, [long]($wCm * 1000))
    $vbH = [Math]::Max(1, [long]($hCm * 1000))
    $sX  = [double]$vbW / $lonRng
    $sY  = [double]$vbH / $latRng

    $pathData  = Get-PathData $feat.geometry $b.LonMin $b.LatMax $sX $sY
    $styleName = "a$i"

    [void]$sbStyles.AppendLine(
        "    <style:style style:name=`"$styleName`" style:family=`"graphic`" " +
        "style:parent-style-name=`"base`"><style:graphic-properties " +
        "draw:fill=`"solid`" draw:fill-color=`"$FillColor`" draw:stroke=`"solid`" " +
        "svg:stroke-color=`"$StrokeColor`" svg:stroke-width=`"0.018cm`" " +
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
}

# ── Cantons par-dessus ────────────────────────────────────────────────────────
foreach ($feat in $GeoJson.features) {
    $code = $feat.properties.code
    $nom  = Escape-Xml $feat.properties.nom

    $b      = Get-BBox $feat.geometry
    $lonRng = [Math]::Max([double]($b.LonMax - $b.LonMin), [double]0.001)
    $latRng = [Math]::Max([double]($b.LatMax - $b.LatMin), [double]0.001)

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
        "svg:stroke-color=`"$StrokeColor`" svg:stroke-width=`"0.018cm`" " +
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
    if ($i % 25 -eq 0) { Write-Host "      $i traites..." -ForegroundColor DarkGray }
}

Write-Host "      -> $i cantons." -ForegroundColor Green

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
      <draw:page draw:name="Cantons de France"
                 draw:master-page-name="Default">
$($sbShapes.ToString())
      </draw:page>
    </office:drawing>
  </office:body>
</office:document-content>
"@

# 4. Empaquetage ZIP -> .odg
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

$size = [Math]::Round((Get-Item $OutputFile).Length / 1KB, 1)
Write-Host ""
Write-Host "=== Termine ===" -ForegroundColor Cyan
Write-Host "Fichier : $OutputFile  (${size} Ko)" -ForegroundColor Green
Write-Host "Page    : ${PageW} cm x ${PageH} cm  |  $i cantons" -ForegroundColor Green
Write-Host "Ouvrez avec LibreOffice Draw." -ForegroundColor DarkGray
