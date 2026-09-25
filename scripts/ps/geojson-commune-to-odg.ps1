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

# Emprise de la France metropolitaine (Corse incluse) en Lambert-93, en metres,
# avec une petite marge. Identique pour toutes les cartes -> superposables.
$MXMin = 80000.0;    $MXMax = 1260000.0
$MYMin = 6030000.0;  $MYMax = 7130000.0

# Echelle unique (cm par metre) pour X et Y : pas de deformation du ratio.
$Scale = [Math]::Min($PageW / ($MXMax - $MXMin), $PageH / ($MYMax - $MYMin))
$XOff  = ($PageW - ($MXMax - $MXMin) * $Scale) / 2
$YOff  = ($PageH - ($MYMax - $MYMin) * $Scale) / 2

# Projection Lambert-93 (EPSG:2154) -- conique conforme secante, ellipsoide GRS80
# Formules IGN (NTG_71). Identique a scripts/generate_odg.py.
$Deg     = [Math]::PI / 180
$L93A    = 6378137.0
$L93F    = 1.0 / 298.257222101
$L93E    = [Math]::Sqrt(2 * $L93F - $L93F * $L93F)
$L93Lon0 = 3.0 * $Deg
$L93X0   = 700000.0
$L93Y0   = 6600000.0

function Get-L93M([double]$phi) {
    [Math]::Cos($phi) / [Math]::Sqrt(1 - [Math]::Pow($L93E * [Math]::Sin($phi), 2))
}
function Get-L93T([double]$phi) {
    $es = $L93E * [Math]::Sin($phi)
    [Math]::Tan([Math]::PI / 4 - $phi / 2) / [Math]::Pow((1 - $es) / (1 + $es), $L93E / 2)
}

$L93N    = ([Math]::Log((Get-L93M (44.0 * $Deg))) - [Math]::Log((Get-L93M (49.0 * $Deg)))) / ([Math]::Log((Get-L93T (44.0 * $Deg))) - [Math]::Log((Get-L93T (49.0 * $Deg))))
$L93AF   = $L93A * (Get-L93M (44.0 * $Deg)) / ($L93N * [Math]::Pow((Get-L93T (44.0 * $Deg)), $L93N))
$L93Rho0 = $L93AF * [Math]::Pow((Get-L93T (46.5 * $Deg)), $L93N)

# Couleur unique bleue, trait tres fin adapte a l'echelle communale
$FillColor   = "#6AAED6"
$StrokeColor = "#1A4F7A"
$StrokeWidth = "0.004cm"

# ── Fonctions ─────────────────────────────────────────────────────────────────

# Anneaux projetes en Lambert-93 : liste d'anneaux, chaque anneau = liste de [x, y] en metres.
function Get-ProjectedRings($geometry) {
    $rings = @()
    if ($geometry.type -eq "Polygon")      { $rings = $geometry.coordinates }
    if ($geometry.type -eq "MultiPolygon") { foreach ($p in $geometry.coordinates) { foreach ($r in $p) { $rings += ,$r } } }
    $out = [System.Collections.Generic.List[object]]::new()
    foreach ($ring in $rings) {
        $pts = [System.Collections.Generic.List[double[]]]::new()
        foreach ($pt in $ring) {
            # Calcul Lambert-93 en ligne (evite un appel de fonction par point)
            $phi   = [double]$pt[1] * $Deg
            $es    = $L93E * [Math]::Sin($phi)
            $t     = [Math]::Tan([Math]::PI / 4 - $phi / 2) / [Math]::Pow((1 - $es) / (1 + $es), $L93E / 2)
            $rho   = $L93AF * [Math]::Pow($t, $L93N)
            $theta = $L93N * ([double]$pt[0] * $Deg - $L93Lon0)
            $pts.Add([double[]]@(($L93X0 + $rho * [Math]::Sin($theta)),
                                 ($L93Y0 + $L93Rho0 - $rho * [Math]::Cos($theta))))
        }
        $out.Add($pts)
    }
    return ,$out
}

function Get-BBox($rings) {
    $xMin = [double]::MaxValue; $xMax = [double]::MinValue
    $yMin = [double]::MaxValue; $yMax = [double]::MinValue
    foreach ($ring in $rings) {
        foreach ($pt in $ring) {
            if ($pt[0] -lt $xMin) { $xMin = $pt[0] }
            if ($pt[0] -gt $xMax) { $xMax = $pt[0] }
            if ($pt[1] -lt $yMin) { $yMin = $pt[1] }
            if ($pt[1] -gt $yMax) { $yMax = $pt[1] }
        }
    }
    return @{ XMin = $xMin; XMax = $xMax; YMin = $yMin; YMax = $yMax }
}

function Get-PathData($rings, [double]$originX, [double]$originYMax,
                      [double]$scaleX, [double]$scaleY) {
    $parts = foreach ($ring in $rings) {
        $sb = New-Object System.Text.StringBuilder
        $first = $true
        foreach ($pt in $ring) {
            $x = [Math]::Round(($pt[0] - $originX)    * $scaleX, 1)
            $y = [Math]::Round(($originYMax - $pt[1]) * $scaleY, 1)
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

    $rings  = Get-ProjectedRings $feat.geometry
    if ($rings.Count -eq 0) { continue }   # geometry null : entite ignoree
    $b      = Get-BBox $rings
    $xRng   = [Math]::Max($b.XMax - $b.XMin, 1.0)
    $yRng   = [Math]::Max($b.YMax - $b.YMin, 1.0)

    $xCm = [Math]::Round($XOff + ($b.XMin - $MXMin) * $Scale, 4)
    $yCm = [Math]::Round($YOff + ($MYMax - $b.YMax) * $Scale, 4)
    $wCm = [Math]::Round($xRng * $Scale, 4)
    $hCm = [Math]::Round($yRng * $Scale, 4)

    $vbW = [Math]::Max(1, [long]($wCm * 1000))
    $vbH = [Math]::Max(1, [long]($hCm * 1000))
    $sX  = [double]$vbW / $xRng
    $sY  = [double]$vbH / $yRng

    $pathData  = Get-PathData $rings $b.XMin $b.YMax $sX $sY
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
