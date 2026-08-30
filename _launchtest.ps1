# Full-folder launch test of the freshly built onedir exe.
# Covers the hardware-license gate: no license, valid license, foreign license.
$ErrorActionPreference = "Stop"
$src = "D:\claude_code\maryam_hesabdari\azaran_teb\dist\AzaranTeb"
$proj = "D:\claude_code\maryam_hesabdari\azaran_teb"
$py = "C:\Program Files\Python38\python.exe"
$tmp = Join-Path $env:TEMP ("azlaunch_" + [guid]::NewGuid().ToString("N").Substring(0,8))
# robocopy preserves the folder tree (Copy-Item "src\*" flattens _internal)
robocopy $src $tmp /E /NFL /NDL /NJH /NJS | Out-Null
$exe = Join-Path $tmp "AzaranTeb.exe"
$lic = Join-Path $tmp "license.key"
"EXE_EXISTS: " + (Test-Path $exe)
"INTERNAL:   " + (Test-Path (Join-Path $tmp "_internal"))
"KEYS_LEAKED_IN_DIST: " + ((Test-Path (Join-Path $src "keys")) -or (Test-Path (Join-Path $src "tools")))
"LICENSE_SHIPPED:     " + (Test-Path (Join-Path $src "license.key"))

function Start-App {
    $pi = New-Object System.Diagnostics.ProcessStartInfo
    $pi.FileName = $exe
    $pi.WorkingDirectory = $tmp
    $pi.UseShellExecute = $true
    $p = [System.Diagnostics.Process]::Start($pi)
    Start-Sleep -Seconds 14
    $alive = $false; $title = ""
    try { $p.Refresh(); $alive = -not $p.HasExited; $title = $p.MainWindowTitle } catch { }
    return @{ Proc = $p; Alive = $alive; Title = $title }
}
function Stop-App($r) {
    try { Stop-Process -Id $r.Proc.Id -Force -ErrorAction SilentlyContinue } catch { }
    Get-Process AzaranTeb -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 2
}

# ---- A: no license at all -> activation dialog, never the app -------------
if (Test-Path $lic) { Remove-Item $lic -Force }
$a = Start-App
"A_ALIVE:  $($a.Alive)"
"A_TITLE:  $($a.Title)"
"A_BLOCKED: " + ($a.Title -like "*فعال‌سازی*")
Stop-App $a

# ---- B: license issued for a DIFFERENT machine -> still blocked -----------
$foreign = & $py -u "$proj\tools\license_issuer.py" --hw "ABCDE-FGHIJ-KLMNP-QRSTU" `
    --name "دستگاه دیگر" --perpetual 2>$null
Set-Content -Path $lic -Value $foreign -Encoding UTF8
"FOREIGN_TOKEN_LEN: " + (Get-Item $lic).Length
$b = Start-App
"B_ALIVE:  $($b.Alive)"
"B_TITLE:  $($b.Title)"
"B_BLOCKED: " + ($b.Title -like "*فعال‌سازی*")
Stop-App $b

# ---- C: valid license for THIS machine -> past the gate, to the login -----
$hw = (& $py -u "$proj\tools\license_issuer.py" --print-hwid | Select-Object -Last 1).Trim()
"HWID: " + $hw
& $py -u "$proj\tools\license_issuer.py" --hw $hw --name "تست exe" `
    --expires 1407-06-31 --out $lic | Out-Null
"C_LICENSE: " + (Test-Path $lic)
$c = Start-App
"C_ALIVE:  $($c.Alive)"
"C_TITLE:  $($c.Title)"
# The license gate is passed once the activation dialog is gone; the app then
# stops at the login dialog (nobody types credentials in this test).
"C_PAST_LICENSE: " + (($c.Title -notlike "*فعال‌سازی*") -and
                      (($c.Title -like "*ورود*") -or ($c.Title -like "*حسابداری*")))
Stop-App $c
"DB_CREATED: " + (Test-Path (Join-Path $tmp "azaran_teb.db"))
"DIRS: " + ((Get-ChildItem $tmp -Directory -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty Name) -join ", ")
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
"DONE"
