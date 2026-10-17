# pbp_probe.ps1 - Probe fuer Beta 16 auf dem Werkstatt-PC (nur ASCII).
# Phasen: base | get <url> <name> | seed | verify <label> [<name>] | mcp [<entry.json>] | check
#         | komp (Komponenten-Status) | ocr <pdf> (Scan hochladen, OCR-Antwort lesen)
#         | linie <Besitzer/Repository> (Quelle der Update-Pruefung umlenken, "neue Linie" lesen; nur auf der Testinstallation 1.7.x)
param(
  [Parameter(Mandatory = $true)][string]$Phase,
  [string]$A1 = '',
  [string]$A2 = '',
  [string]$W = 'D:\Downloads\pbp_probe',
  [string]$Rechner = 'WERKSTATT',
  [string]$LA = $env:LOCALAPPDATA,
  [string]$RA = $env:APPDATA,
  [int]$Port = 8200
)
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
if (-not (Test-Path -LiteralPath $W)) { New-Item -ItemType Directory -Force -Path $W | Out-Null }
$BASE = Join-Path $LA 'BewerbungsAssistent'
$APP = Join-Path $BASE 'app'
$DATA = Join-Path $BASE 'data'
$PWR = Join-Path $LA 'ms-playwright'
$PIP = Join-Path $LA 'pip'
$LNK = Join-Path ([Environment]::GetFolderPath('Desktop')) 'PBP Bewerbungs-Portal.lnk'
$REG = 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\PBP'
$API = 'http://127.0.0.1:' + $Port

function Say($t) { Write-Host $t }
function NurWerkstatt { if ($env:COMPUTERNAME -ne $Rechner) { throw ('Abbruch: laeuft nur auf ' + $Rechner + ' (hier: ' + $env:COMPUTERNAME + ')') } }
function Sha($p) { if ($p -and (Test-Path -LiteralPath $p -PathType Leaf)) { (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.Substring(0, 12) } else { '-' } }
function Mb($p) { if (Test-Path -LiteralPath $p) { [int]((Get-ChildItem -LiteralPath $p -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB) } else { -1 } }
function Kurz($t, $n) { if ($t -and $t.Length -gt $n) { $t.Substring(0, $n) + '..' } else { $t } }
function Hash6($text) { $h = [Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($text)); return (-join ($h[0..5] | ForEach-Object { $_.ToString('x2') })) }

function ConfigPfade {
  $l = New-Object System.Collections.ArrayList
  [void]$l.Add((Join-Path $RA 'Claude\claude_desktop_config.json'))
  $pk = Join-Path $LA 'Packages'
  if (Test-Path -LiteralPath $pk) {
    Get-ChildItem -LiteralPath $pk -Filter 'Claude_*' -Directory -ErrorAction SilentlyContinue | ForEach-Object { [void]$l.Add((Join-Path $_.FullName 'LocalCache\Roaming\Claude\claude_desktop_config.json')) }
  }
  # #1245: die neuere Store-Fassung von Claude liest ihre Konfiguration aus Claude-Data (nicht mehr aus Roaming oder Packages)
  $cd = Join-Path $LA 'Claude-Data'
  if (Test-Path -LiteralPath $cd) {
    Get-ChildItem -LiteralPath $cd -Directory -ErrorAction SilentlyContinue | ForEach-Object { [void]$l.Add((Join-Path $_.FullName 'claude_desktop_config.json')) }
  }
  $l
}

function Fremd($pfad) {
  try {
    $o = Get-Content -LiteralPath $pfad -Raw -Encoding UTF8 | ConvertFrom-Json
    $teile = New-Object System.Collections.ArrayList
    foreach ($p in $o.PSObject.Properties) {
      if ($p.Name -eq 'mcpServers') {
        foreach ($s in $p.Value.PSObject.Properties) {
          if ($s.Name -ne 'bewerbungs-assistent') { [void]$teile.Add('S:' + $s.Name + '=' + ($s.Value | ConvertTo-Json -Depth 10 -Compress)) }
        }
      } else { [void]$teile.Add('K:' + $p.Name + '=' + ($p.Value | ConvertTo-Json -Depth 10 -Compress)) }
    }
    return (Hash6 (($teile | Sort-Object) -join "`n"))
  } catch { return 'unlesbar' }
}

function PbpProzesse {
  $r = @()
  Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    if (($_.CommandLine -match 'bewerbungs_assistent|start_dashboard|uvicorn|fastmcp') -or ($_.ExecutablePath -match 'BewerbungsAssistent')) { $r += ('pid ' + $_.ProcessId + ': ' + (Kurz $_.CommandLine 95)) }
  }
  return $r
}

function Api($m, $p, $body) {
  if ($null -ne $body) {
    $b = [Text.Encoding]::UTF8.GetBytes((ConvertTo-Json -InputObject $body -Depth 6 -Compress))
    return Invoke-RestMethod -Method $m -Uri ($API + $p) -ContentType 'application/json; charset=utf-8' -Body $b -TimeoutSec 90
  }
  return Invoke-RestMethod -Method $m -Uri ($API + $p) -TimeoutSec 90
}

function Liste($x, $name) {
  if ($null -eq $x) { return @() }
  if ($name -and ($x.PSObject.Properties.Name -contains $name)) { return @($x.$name) }
  if ($x -is [array]) { return @($x) }
  foreach ($p in $x.PSObject.Properties) { if ($p.Value -is [array]) { return @($p.Value) } }
  return @($x)
}

function Abdruck {
  $a = @(Liste (Api 'GET' '/api/applications?include_archived=true&limit=500' $null) 'applications')
  $c = @(Liste (Api 'GET' '/api/contacts' $null) 'contacts')
  $t = @(Liste (Api 'GET' '/api/tasks' $null) 'tasks')
  $rows = New-Object System.Collections.ArrayList
  foreach ($x in $a) { [void]$rows.Add('A|' + $x.company + '|' + $x.title + '|' + $x.status + '|' + $x.applied_at) }
  foreach ($x in $c) { [void]$rows.Add('C|' + $x.full_name + '|' + $x.email + '|' + $x.company) }
  foreach ($x in $t) { [void]$rows.Add('T|' + $x.titel + '|' + $x.status) }
  $sorted = @($rows | Sort-Object)
  return @{ apps = $a.Count; kontakte = $c.Count; aufgaben = $t.Count; hash = (Hash6 ($sorted -join "`n")); zeilen = $sorted }
}

$DBPY = @'
import sqlite3, sys, json
p = sys.argv[1].replace('\\', '/')
c = sqlite3.connect('file:' + p + '?mode=ro', uri=True)
sv = c.execute("select value from settings where key='schema_version'").fetchone()
t = {}
for (n,) in c.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name").fetchall():
    t[n] = c.execute('select count(*) from "%s"' % n).fetchone()[0]
print(json.dumps({'schema': sv[0] if sv else None, 'integrity': c.execute('pragma integrity_check').fetchone()[0], 'tabellen': len(t),
                  'apps': t.get('applications'), 'jobs': t.get('jobs'), 'kontakte': t.get('contacts'), 'aufgaben': t.get('tasks'),
                  'firmen': t.get('companies'), 'notizen_events': t.get('application_events')}))
'@

function DbPruefen($pfad) {
  $py = Join-Path $APP 'python\python.exe'
  if (-not (Test-Path -LiteralPath $py)) { $py = (Get-Command python -ErrorAction SilentlyContinue).Source }
  if (-not $py) { return 'kein Python fuer die DB-Pruefung' }
  $f = Join-Path $W 'dbcheck.py'
  Set-Content -LiteralPath $f -Value $DBPY -Encoding ASCII
  $o = & $py $f $pfad 2>&1
  return (($o | ForEach-Object { [string]$_ }) -join ' ')
}

function Phase-base {
  $B = @{}
  $L = @('=== BASELINE ' + (Get-Date -Format 's') + ' rechner=' + $env:COMPUTERNAME + ' benutzer=' + $env:USERNAME)
  $cfgs = @(); $i = 0
  foreach ($c in (ConfigPfade)) {
    $i++
    $ex = Test-Path -LiteralPath $c
    $fr = '-'; $by = 0
    if ($ex) { $fr = Fremd $c; $by = (Get-Item -LiteralPath $c).Length; Copy-Item -LiteralPath $c -Destination (Join-Path $W ('orig_config' + $i + '.json')) -Force }
    $cfgs += @{ pfad = $c; vorhanden = $ex; sha = (Sha $c); fremd = $fr; bytes = $by; kopie = ('orig_config' + $i + '.json') }
    $L += ('config' + $i + ': vorhanden=' + $ex + ' sha=' + (Sha $c) + ' fremd=' + $fr + ' bytes=' + $by)
    $L += ('   ' + (Kurz $c 95))
  }
  $B.configs = $cfgs
  $B.base_mb = Mb $BASE; $B.pw_mb = Mb $PWR; $B.pip_mb = Mb $PIP
  $B.lnk = Test-Path -LiteralPath $LNK
  $B.reg = Test-Path $REG
  $B.temp_dein = @(Get-ChildItem -LiteralPath $env:TEMP -Filter 'PBP-Deinstaller-*' -ErrorAction SilentlyContinue).Count
  $B.port = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue).Count
  $B.claude_prozesse = @(Get-Process -Name 'claude' -ErrorAction SilentlyContinue).Count
  $L += ('PBP-Ordner MB=' + $B.base_mb + ' | ms-playwright MB=' + $B.pw_mb + ' | pip MB=' + $B.pip_mb + ' (-1 = nicht da)')
  $L += ('Verknuepfung=' + $B.lnk + ' | Registry=' + $B.reg + ' | Temp-Deinstaller=' + $B.temp_dein + ' | Port ' + $Port + ' belegt=' + $B.port)
  $L += ('Claude-Prozesse=' + $B.claude_prozesse + ' | PowerShell ' + $PSVersionTable.PSVersion)
  $d = Get-PSDrive -Name D -ErrorAction SilentlyContinue
  $c2 = Get-PSDrive -Name C -ErrorAction SilentlyContinue
  if ($d) { $L += ('frei D: ' + [int]($d.Free / 1GB) + ' GB') }
  if ($c2) { $L += ('frei C: ' + [int]($c2.Free / 1GB) + ' GB') }
  $pyim = Get-Command python -ErrorAction SilentlyContinue
  $L += ('python im PATH: ' + $(if ($pyim) { $pyim.Source } else { 'nein' }))
  $B | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $W 'baseline.json') -Encoding UTF8
  $L | Set-Content -LiteralPath (Join-Path $W 'baseline.txt') -Encoding UTF8
  $L | ForEach-Object { Say $_ }
}

function Phase-get {
  if (-not $A1 -or -not $A2) { throw 'get <url> <name>' }
  $zip = Join-Path $W ($A2 + '.zip'); $dir = Join-Path $W $A2
  Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
  $t0 = Get-Date
  Invoke-WebRequest -Uri $A1 -OutFile $zip -UseBasicParsing
  Expand-Archive -LiteralPath $zip -DestinationPath $dir -Force
  $sek = [int](((Get-Date) - $t0).TotalSeconds)
  $inner = Get-ChildItem -LiteralPath $dir -Directory | Select-Object -First 1
  $n = @(Get-ChildItem -LiteralPath $inner.FullName -Recurse -File).Count
  $v = (Select-String -LiteralPath (Join-Path $inner.FullName 'src\bewerbungs_assistent\__init__.py') -Pattern '__version__' | Select-Object -First 1).Line.Trim()
  Say ('ZIP ' + [int]((Get-Item -LiteralPath $zip).Length / 1KB) + ' KB, ' + $sek + ' s; Dateien ' + $n + '; ' + $v)
  Say ('Ordner: ' + $inner.FullName)
  Set-Content -LiteralPath (Join-Path $W ($A2 + '.pfad')) -Value $inner.FullName -Encoding UTF8
}

function Phase-seed {
  NurWerkstatt
  $u = [string][char]0xFC; $o = [string][char]0xF6; $a = [string][char]0xE4; $ss = [string][char]0xDF
  $ok = $false
  for ($i = 0; $i -lt 60; $i++) { try { $null = Invoke-RestMethod -Uri ($API + '/api/health') -TimeoutSec 5; $ok = $true; break } catch { Start-Sleep -Seconds 2 } }
  if (-not $ok) { throw 'Dashboard antwortet nicht' }
  $st = Api 'GET' '/api/status' $null
  Say ('vorher: version=' + $st.version + ' profil=' + $st.has_profile + ' bewerbungen=' + $st.applications)
  if ($st.has_profile) { throw 'Abbruch: es gibt schon ein Profil - nicht auf fremde Daten seeden' }
  $null = Api 'POST' '/api/profile' @{ name = 'Erika Beispiel'; email = 'erika@example.com'; city = 'Hamburg'; plz = '20095'; summary = ('Sachbearbeiterin im Einkauf, Gr' + $o + $ss + 'e und Fl' + $a + 'che') }
  $firmen = @('Beispiel Firma 0 GmbH', ('M' + $u + 'ller & S' + $o + 'hne GmbH'), 'Testwerk AG', ('K' + $o + 'nig Logistik KG'), 'Muster Handel GmbH', 'Nord Technik GmbH')
  $ziel = @('beworben', 'interview', 'abgelehnt', 'beworben', 'zurueckgezogen', 'interview')
  $ids = @()
  for ($i = 0; $i -lt 6; $i++) {
    $r = Api 'POST' '/api/applications' @{ title = ('Sachbearbeiter ' + $i); company = $firmen[$i]; url = ('https://example.com/b/' + $i); status = 'beworben'; applied_at = ('2026-09-' + (10 + $i)); notes = 'QA'; ansprechpartner = ('Frau Muster' + $i); kontakt_email = ('muster' + $i + '@example.com') }
    $ids += $r.id
    if ($ziel[$i] -ne 'beworben') { $null = Api 'PUT' ('/api/applications/' + $r.id + '/status') @{ status = $ziel[$i]; notes = 'QA' } }
  }
  $null = Api 'POST' ('/api/applications/' + $ids[0] + '/notes') @{ text = 'Notiz zur Bewerbung' }
  $null = Api 'POST' ('/api/applications/' + $ids[1] + '/notes') @{ text = ('Gespr' + $a + 'ch gut gelaufen') }
  $c = Api 'POST' '/api/contacts' @{ full_name = ('Max M' + $u + 'ller'); email = 'max@example.com'; company = $firmen[0]; position = 'Recruiter'; tags = @('recruiter') }
  try { $null = Api 'POST' ('/api/contacts/' + $c.id + '/links') @{ target_kind = 'application'; target_id = $ids[0] } } catch { Say ('Kontakt-Verknuepfung: ' + $_.Exception.Message) }
  $null = Api 'POST' '/api/tasks' @{ titel = 'QA-Aufgabe zur Bewerbung'; application_id = $ids[1]; typ = 'custom' }
  $null = Api 'POST' '/api/tasks' @{ titel = ('Suchkriterien nachsch' + $a + 'rfen'); typ = 'custom' }
  $ab = Abdruck
  ($ab | ConvertTo-Json -Depth 4) | Set-Content -LiteralPath (Join-Path $W 'snap_pre.json') -Encoding UTF8
  Say ('angelegt: bewerbungen=' + $ab.apps + ' kontakte=' + $ab.kontakte + ' aufgaben=' + $ab.aufgaben + ' hash=' + $ab.hash)
}

function Phase-verify {
  $L = New-Object System.Collections.ArrayList
  $label = $(if ($A1) { $A1 } else { 'x' })
  [void]$L.Add('=== VERIFY ' + $label + ' ' + (Get-Date -Format 's'))
  try {
    $h = Invoke-RestMethod -Uri ($API + '/api/health') -TimeoutSec 20
    [void]$L.Add('health: version=' + $h.pbp_version + ' python=' + $h.python_version + ' data=' + (Kurz $h.data_dir 60))
  } catch { [void]$L.Add('health: NICHT ERREICHBAR ' + $_.Exception.Message) }
  try {
    $ab = Abdruck
    [void]$L.Add('daten: bewerbungen=' + $ab.apps + ' kontakte=' + $ab.kontakte + ' aufgaben=' + $ab.aufgaben + ' hash=' + $ab.hash)
    $pre = Join-Path $W 'snap_pre.json'
    if ((Test-Path -LiteralPath $pre) -and $label -ne 'pre') {
      $s = Get-Content -LiteralPath $pre -Raw -Encoding UTF8 | ConvertFrom-Json
      $gleich = ($s.hash -eq $ab.hash) -and ($s.apps -eq $ab.apps) -and ($s.kontakte -eq $ab.kontakte) -and ($s.aufgaben -eq $ab.aufgaben)
      [void]$L.Add('vergleich mit vorher: ' + $(if ($gleich) { 'GLEICH' } else { 'ABWEICHUNG (vorher hash=' + $s.hash + ' apps=' + $s.apps + ')' }))
      if (-not $gleich) {
        $vorz = @($s.zeilen); $jetzt = @($ab.zeilen)
        foreach ($z in (Compare-Object $vorz $jetzt | Select-Object -First 6)) { [void]$L.Add('   ' + $z.SideIndicator + ' ' + (Kurz $z.InputObject 90)) }
      }
    }
  } catch { [void]$L.Add('daten: FEHLER ' + $_.Exception.Message) }
  [void]$L.Add('db: ' + (DbPruefen (Join-Path $DATA 'pbp.db')))
  $bk = Join-Path $DATA 'backups'
  if (Test-Path -LiteralPath $bk) {
    $fl = @(Get-ChildItem -LiteralPath $bk -File -Filter '*.db' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime)
    [void]$L.Add('sicherungen (.db): ' + $fl.Count + ' | ' + (($fl | ForEach-Object { $_.Name + ' ' + [int]($_.Length / 1KB) + 'KB' }) -join '; '))
    if ($fl.Count -gt 0) { [void]$L.Add('neueste Sicherung: ' + (DbPruefen $fl[-1].FullName)) }
  } else { [void]$L.Add('sicherungen: Ordner fehlt') }
  [void]$L.Add('aktuell.txt: ' + $(if (Test-Path -LiteralPath (Join-Path $APP 'aktuell.txt')) { (Get-Content -LiteralPath (Join-Path $APP 'aktuell.txt') -Raw).Trim() } else { '-' }))
  $vs = @(Get-ChildItem -LiteralPath (Join-Path $APP 'versions') -Directory -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
  [void]$L.Add('versions: ' + ($vs -join ',') + ' | boot: ' + (Test-Path -LiteralPath (Join-Path $APP 'boot\bewerbungs_assistent_boot\__init__.py')) + ' | altes src: ' + (Test-Path -LiteralPath (Join-Path $APP 'src')))
  $pth = Get-ChildItem -LiteralPath (Join-Path $APP 'python') -Filter 'python*._pth' -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($pth) { [void]$L.Add('._pth: ' + ((Get-Content -LiteralPath $pth.FullName | Where-Object { $_ -and -not $_.StartsWith('#') }) -join ' | ')) }
  $bj = Join-Path $W 'baseline.json'
  $base = $null
  if (Test-Path -LiteralPath $bj) { $base = Get-Content -LiteralPath $bj -Raw -Encoding UTF8 | ConvertFrom-Json }
  $i = 0
  foreach ($c in (ConfigPfade)) {
    $i++
    if (-not (Test-Path -LiteralPath $c)) { [void]$L.Add('config' + $i + ': fehlt'); continue }
    try {
      $o = Get-Content -LiteralPath $c -Raw -Encoding UTF8 | ConvertFrom-Json
      $e = $o.mcpServers.'bewerbungs-assistent'
      $fr = Fremd $c
      $bfr = $(if ($base) { @($base.configs)[$i - 1].fremd } else { '?' })
      if ($e) {
        [void]$L.Add('config' + $i + ': PBP-Eintrag: ' + (Kurz ([string]$e.command) 70) + ' ' + (@($e.args) -join ' '))
        [void]$L.Add('   env: PYTHONPATH=' + (Kurz ([string]$e.env.PYTHONPATH) 70) + ' | BA_DATA_DIR=' + (Kurz ([string]$e.env.BA_DATA_DIR) 60))
      } else { [void]$L.Add('config' + $i + ': KEIN PBP-Eintrag') }
      [void]$L.Add('   fremde Server und Einstellungen: ' + $(if ($fr -eq $bfr) { 'UNVERAENDERT' } else { 'GEAENDERT (jetzt ' + $fr + ', vorher ' + $bfr + ')' }))
    } catch { [void]$L.Add('config' + $i + ': nicht lesbar ' + $_.Exception.Message) }
  }
  if (Test-Path -LiteralPath $LNK) {
    $sc = (New-Object -ComObject WScript.Shell).CreateShortcut($LNK)
    [void]$L.Add('verknuepfung: ' + (Kurz $sc.TargetPath 70) + ' ' + (Kurz $sc.Arguments 60))
  } else { [void]$L.Add('verknuepfung: fehlt') }
  if (Test-Path $REG) { $r = Get-ItemProperty $REG; [void]$L.Add('registry: ' + $r.DisplayName + ' ' + $r.DisplayVersion) } else { [void]$L.Add('registry: fehlt') }
  $own = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  [void]$L.Add('port ' + $Port + ': ' + $(if ($own) { 'belegt von pid ' + $own.OwningProcess } else { 'frei' }))
  foreach ($p in (PbpProzesse)) { [void]$L.Add('   ' + $p) }
  $ep = @('/api/status', '/api/profile', '/api/applications', '/api/jobs', '/api/contacts', '/api/emails', '/api/documents', '/api/meetings', '/api/tasks', '/api/statistics', '/api/sources', '/api/components', '/api/plugins', '/api/update-check', '/api/auto-update', '/api/speicher', '/api/firmen', '/api/mail-quelle')
  $codes = @()
  foreach ($e in $ep) {
    $code = 0
    try { $r = Invoke-WebRequest -Uri ($API + $e) -UseBasicParsing -TimeoutSec 60; $code = [int]$r.StatusCode } catch { try { $code = [int]$_.Exception.Response.StatusCode.value__ } catch { $code = -1 } }
    $codes += ($e.Replace('/api/', '') + '=' + $code)
  }
  [void]$L.Add('rest: ' + ($codes -join ' '))
  if ($A2) {
    $pf = Join-Path $W ($A2 + '.pfad')
    if (Test-Path -LiteralPath $pf) {
      $lg = Join-Path ((Get-Content -LiteralPath $pf -Raw).Trim()) 'install_log.txt'
      if (Test-Path -LiteralPath $lg) {
        $tx = @(Get-Content -LiteralPath $lg -ErrorAction SilentlyContinue)
        $bad = @($tx | Where-Object { $_ -match '\[FEHLER\]|\[WARN|\[WARNUNG\]' })
        [void]$L.Add('install_log: ' + $tx.Count + ' Zeilen, Warnungen/Fehler: ' + $bad.Count)
        foreach ($z in ($bad | Select-Object -First 6)) { [void]$L.Add('   ' + (Kurz $z 100)) }
      } else { [void]$L.Add('install_log: nicht gefunden') }
    }
  }
  $L | Set-Content -LiteralPath (Join-Path $W ('verify_' + $label + '.txt')) -Encoding UTF8
  $L | ForEach-Object { Say $_ }
}

function Phase-mcp {
  $entry = $null
  if ($A1) { $entry = Get-Content -LiteralPath $A1 -Raw -Encoding UTF8 | ConvertFrom-Json }
  else {
    foreach ($c in (ConfigPfade)) {
      if ((-not $entry) -and (Test-Path -LiteralPath $c)) {
        $o = Get-Content -LiteralPath $c -Raw -Encoding UTF8 | ConvertFrom-Json
        $e = $o.mcpServers.'bewerbungs-assistent'
        if ($e) { $entry = $e; Say ('Eintrag aus ' + (Kurz $c 80)) }
      }
    }
  }
  if (-not $entry) { throw 'kein Eintrag bewerbungs-assistent gefunden' }
  Say ('start: ' + (Kurz ([string]$entry.command) 60) + ' ' + (@($entry.args) -join ' '))
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = [string]$entry.command
  $psi.Arguments = (@($entry.args) -join ' ')
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true
  $psi.RedirectStandardInput = $true
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.StandardOutputEncoding = [Text.Encoding]::UTF8
  if ($entry.env) { foreach ($p in $entry.env.PSObject.Properties) { $psi.EnvironmentVariables[$p.Name] = [string]$p.Value } }
  $proc = New-Object System.Diagnostics.Process
  $proc.StartInfo = $psi
  # Die Konsole kodiert UTF-8 MIT BOM; der Prozess schriebe die drei Bytes vor die erste JSON-Zeile (Server: Invalid JSON).
  $alteEingabe = [Console]::InputEncoding
  try { [Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }
  try { [void]$proc.Start() } finally { try { [Console]::InputEncoding = $alteEingabe } catch { } }
  $errTask = $proc.StandardError.ReadToEndAsync()
  $t0 = Get-Date
  try {
    $w = $proc.StandardInput
    $w.NewLine = "`n"
    $w.WriteLine('{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}')
    $w.Flush()
    $antwort = $null
    $ende = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $ende -and -not $antwort) {
      $t = $proc.StandardOutput.ReadLineAsync()
      if (-not $t.Wait(([int]($ende - (Get-Date)).TotalMilliseconds))) { break }
      if ($t.Result -match '"id"\s*:\s*1[,}]') { $antwort = $t.Result }
      elseif ($null -eq $t.Result) { break }
    }
    if (-not $antwort) { throw 'keine Antwort auf initialize' }
    Say ('initialize nach ' + [int](((Get-Date) - $t0).TotalSeconds) + ' s: ' + (Kurz $antwort 150))
    $w.WriteLine('{"jsonrpc":"2.0","method":"notifications/initialized"}'); $w.Flush()
    $w.WriteLine('{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'); $w.Flush()
    $antwort2 = $null
    $ende = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $ende -and -not $antwort2) {
      $t = $proc.StandardOutput.ReadLineAsync()
      if (-not $t.Wait(([int]($ende - (Get-Date)).TotalMilliseconds))) { break }
      if ($t.Result -match '"id"\s*:\s*2[,}]') { $antwort2 = $t.Result }
      elseif ($null -eq $t.Result) { break }
    }
    if (-not $antwort2) { throw 'keine Antwort auf tools/list' }
    $j = $antwort2 | ConvertFrom-Json
    Say ('Werkzeuge: ' + @($j.result.tools).Count)
  } finally {
    if (-not $proc.HasExited) { $proc.Kill() }
    [void]$errTask.Wait(3000)
    if ($errTask.IsCompleted) {
      $zl = @(($errTask.Result -split "`n") | Where-Object { $_.Trim() })
      Say ('stderr: ' + $zl.Count + ' Zeilen; letzte:')
      foreach ($z in ($zl | Select-Object -Last 4)) { Say ('   ' + (Kurz $z.Trim() 110)) }
    }
  }
}

function Phase-check {
  $bj = Join-Path $W 'baseline.json'
  if (-not (Test-Path -LiteralPath $bj)) { throw 'baseline.json fehlt' }
  $B = Get-Content -LiteralPath $bj -Raw -Encoding UTF8 | ConvertFrom-Json
  $L = New-Object System.Collections.ArrayList
  [void]$L.Add('=== CHECK ' + (Get-Date -Format 's'))
  [void]$L.Add('PBP-Ordner MB=' + (Mb $BASE) + ' (Basis ' + $B.base_mb + ') | ms-playwright MB=' + (Mb $PWR) + ' (Basis ' + $B.pw_mb + ') | pip MB=' + (Mb $PIP) + ' (Basis ' + $B.pip_mb + ')')
  [void]$L.Add('Verknuepfung=' + (Test-Path -LiteralPath $LNK) + ' (Basis ' + $B.lnk + ') | Registry=' + (Test-Path $REG) + ' (Basis ' + $B.reg + ')')
  [void]$L.Add('Temp-Deinstaller=' + @(Get-ChildItem -LiteralPath $env:TEMP -Filter 'PBP-Deinstaller-*' -ErrorAction SilentlyContinue).Count + ' | Port ' + $Port + ' belegt=' + @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue).Count)
  $pr = @(PbpProzesse)
  [void]$L.Add('PBP-Prozesse: ' + $pr.Count)
  foreach ($p in $pr) { [void]$L.Add('   ' + $p) }
  $i = 0
  foreach ($c in (ConfigPfade)) {
    $i++
    # Nicht `$b`: PowerShell unterscheidet `$b` und `$B` nicht, die Zuweisung ueberschriebe die Basis (Testlauf 11.10.2026: "Basis" blieb ab der zweiten Datei leer).
    $bk = @($B.configs)[$i - 1]
    $ex = Test-Path -LiteralPath $c
    $eintrag = $false
    if ($ex) { try { $eintrag = [bool]((Get-Content -LiteralPath $c -Raw -Encoding UTF8 | ConvertFrom-Json).mcpServers.'bewerbungs-assistent') } catch { } }
    [void]$L.Add('config' + $i + ': vorhanden=' + $ex + ' (Basis ' + $bk.vorhanden + ') sha=' + (Sha $c) + ' (Basis ' + $bk.sha + ') fremd=' + $(if ($ex) { Fremd $c } else { '-' }) + ' (Basis ' + $bk.fremd + ') PBP-Eintrag=' + $eintrag)
  }
  # PP26: die Texterkennung "nur fuer mich" liegt ausserhalb von PBP; nach dem Deinstaller darf davon nichts bleiben
  [void]$L.Add('Tesseract-OCR (nur fuer mich) vorhanden=' + (Test-Path -LiteralPath (Join-Path $LA 'Programs\Tesseract-OCR')) + ' | Startmenue=' + (Test-Path -LiteralPath (Join-Path $RA 'Microsoft\Windows\Start Menu\Programs\Tesseract-OCR')))
  [void]$L.Add('Temp: tmp*\pip.zip=' + @(Get-ChildItem -LiteralPath $env:TEMP -Directory -Filter 'tmp*' -ErrorAction SilentlyContinue | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'pip.zip') }).Count + ' | pbp_installer_aufraeumen.py=' + (Test-Path -LiteralPath (Join-Path $env:TEMP 'pbp_installer_aufraeumen.py')) + ' | deinstall_log.txt=' + (Test-Path -LiteralPath (Join-Path $env:TEMP 'deinstall_log.txt')))
  $L | Set-Content -LiteralPath (Join-Path $W 'check.txt') -Encoding UTF8
  $L | ForEach-Object { Say $_ }
}


function Phase-komp {
  $r = Api 'GET' '/api/components' $null
  foreach ($k in @($r.komponenten)) {
    Say ('komponente: ' + $k.name + ' | status=' + $k.status + ' | quelle=' + $k.quelle + ' | version=' + $k.version + ' | pfad=' + (Kurz ([string]$k.binary) 90))
  }
  Say ('ollama: verfuegbar=' + $r.ollama.verfuegbar)
  # PP26: ohne Administratorrechte installiert das Setup "nur fuer mich" ausserhalb von PBP; der Vermerk im Komponenten-Ordner sagt es
  $marker = Join-Path $BASE 'components\tesseract\pbp-installation.json'
  Say ('vermerk: ' + $(if (Test-Path -LiteralPath $marker) { Kurz ((Get-Content -LiteralPath $marker -Raw) -replace '\s+', ' ') 260 } else { 'keiner' }))
  $pu = Join-Path $LA 'Programs\Tesseract-OCR'
  if (Test-Path -LiteralPath $pu) {
    Say ('programmordner: ' + $pu + ' | ' + (Mb $pu) + ' MB | tesseract.exe=' + (Test-Path -LiteralPath (Join-Path $pu 'tesseract.exe')) + ' | deinstaller=' + (Test-Path -LiteralPath (Join-Path $pu 'tesseract-uninstall.exe')))
    $td = Join-Path $pu 'tessdata'
    if (Test-Path -LiteralPath $td) { Say ('tessdata: ' + ((Get-ChildItem -LiteralPath $td -Filter '*.traineddata' | ForEach-Object { $_.Name + ' ' + [int]($_.Length / 1KB) + 'KB' }) -join '; ')) }
  } else { Say ('programmordner: ' + $pu + ' | nicht da') }
  $sm = Join-Path $RA 'Microsoft\Windows\Start Menu\Programs\Tesseract-OCR'
  Say ('startmenue: ' + $(if (Test-Path -LiteralPath $sm) { 'vorhanden' } else { 'nicht da' }))
}

function Phase-ocr {
  if (-not $A1) { throw 'ocr <pdf>' }
  if (-not (Test-Path -LiteralPath $A1)) { throw ('Datei fehlt: ' + $A1) }
  $out = & curl.exe -s -S -m 300 -F ('file=@' + $A1) ($API + '/api/documents/upload')
  Say ('antwort: ' + (Kurz ($out -join ' ') 700))
  try {
    $j = ($out -join '') | ConvertFrom-Json
    if ($j.ocr) { Say ('ocr: ' + ($j.ocr | ConvertTo-Json -Compress -Depth 4)) }
  } catch { Say ('antwort nicht als JSON lesbar: ' + $_.Exception.Message) }
}

function Phase-linie {
  # F2 (dritter Lauf): eine 1.7-Installation nennt eine hoehere Linie (neue_linie), ohne sie anzubieten.
  # Quelle ist das Probe-Repository (A1 = Besitzer/Name); die Einstellung update_quellen wird auf dieser Testinstallation gesetzt.
  if (-not $A1) { throw 'linie <Besitzer/Repository>' }
  # 1.7.153 und neuer: Laufzeit und Code liegen unter app\; aelterer Aufbau (1.4 bis 1.6) direkt unter BASE
  $py = Join-Path $APP 'python\python.exe'
  $src = Join-Path $APP 'src'
  if (-not (Test-Path -LiteralPath $py)) { $py = Join-Path $BASE 'python\python.exe'; $src = Join-Path $BASE 'src' }
  if (-not (Test-Path -LiteralPath $py)) { throw ('Laufzeit fehlt: ' + $py) }
  $q = @(
    @{ name = 'probe'; url = ('https://api.github.com/repos/' + $A1 + '/releases/latest'); art = 'github' },
    @{ name = 'probe-liste'; url = ('https://api.github.com/repos/' + $A1 + '/releases?per_page=30'); art = 'github_liste' }
  )
  $datei = Join-Path $W 'update_quellen.json'
  [IO.File]::WriteAllText($datei, (ConvertTo-Json -InputObject $q -Depth 4 -Compress), (New-Object Text.UTF8Encoding($false)))
  $code = "import sys, json; sys.path.insert(0, sys.argv[1]); from bewerbungs_assistent.database import Database; db = Database(); db.initialize(); db.set_setting('update_quellen', json.load(open(sys.argv[2], encoding='utf-8'))); print('update_quellen gesetzt')"
  & $py -c $code $src $datei
  $r = Api 'GET' '/api/update-check?frisch=1' $null
  Say ('current=' + $r.current_version + ' | linie=' + $r.linie + ' | stand=' + $r.stand + ' | update_available=' + $r.update_available)
  if ($r.neue_linie) { Say ('neue_linie: version=' + $r.neue_linie.version + ' | linie=' + $r.neue_linie.linie + ' | url=' + $r.neue_linie.url) } else { Say 'neue_linie: keine' }
  Say ('quellen: ' + (ConvertTo-Json -InputObject @($r.quellen_versucht) -Depth 4 -Compress))
}

switch ($Phase) {
  'base' { Phase-base }
  'get' { Phase-get }
  'seed' { Phase-seed }
  'verify' { Phase-verify }
  'mcp' { Phase-mcp }
  'check' { Phase-check }
  'komp' { Phase-komp }
  'ocr' { Phase-ocr }
  'linie' { Phase-linie }
  default { Say ('unbekannte Phase: ' + $Phase) }
}
