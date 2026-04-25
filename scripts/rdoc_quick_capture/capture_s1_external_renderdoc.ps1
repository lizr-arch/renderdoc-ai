[CmdletBinding()]
param(
  [switch]$CheckOnly,
  [switch]$SkipLaunch,
  [switch]$SkipReport,
  [string]$OutputPrefix = "",
  [int]$TargetControlPort = 38920,
  [switch]$KeepGameAlive,
  [switch]$VerboseLog,
  [string]$RenderDocCmd = "D:\Code\git\renderdoc\x64\Development\renderdoccmd.exe",
  [string]$S1Exe = "F:\Code\S1\Engine\Binaries\Win64\Game_x64h.exe",
  [string]$S1Workdir = "F:\Code\S1\Engine\Binaries\Win64",
  [int]$LaunchTimeoutSec = 60,
  [int]$CaptureTimeoutSec = 60,
  [int]$ModuleTimeoutSec = 60,
  [int]$PreCaptureDelaySec = 10,
  [string]$TargetControlPython = "D:\Program Files\Python36\python.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$DevRenderDocDll = "D:\Code\git\renderdoc\x64\Development\renderdoc.dll"
$SystemRenderDocDll = "C:\Program Files\RenderDoc\renderdoc.dll"
$GameArgs = @(
  "--dx11",
  "--console",
  "--start=Python",
  "--python-args=nopatch",
  "--disable-shepherd",
  "--disable-streamline",
  "--force-debug-shader=1",
  "--enable-renderdoc",
  "--suppress=Shepherd",
  "--suppress=RenderDoc",
  "--respawn=0"
)

function Write-Step {
  param([string]$Message)
  Write-Host "[S1 external capture] $Message"
}

function Write-Detail {
  param([string]$Message)
  if($VerboseLog)
  {
    Write-Host "[detail] $Message"
  }
}

function Fail {
  param([string]$Message)
  throw $Message
}

function Get-RepoRoot {
  return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
}

function Resolve-CapturePrefix {
  if($OutputPrefix)
  {
    return $OutputPrefix
  }

  $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
  return "F:\Code\S1\LocalData\RenderDocCaptures\codex_external_$stamp"
}

function Assert-ExistingFile {
  param(
    [string]$Path,
    [string]$Label
  )
  if(-not (Test-Path -LiteralPath $Path -PathType Leaf))
  {
    Fail "$Label not found: $Path"
  }
  Write-Detail "$Label OK: $Path"
}

function Assert-ExistingDirectory {
  param(
    [string]$Path,
    [string]$Label
  )
  if(-not (Test-Path -LiteralPath $Path -PathType Container))
  {
    Fail "$Label not found: $Path"
  }
  Write-Detail "$Label OK: $Path"
}

function Assert-WritableDirectory {
  param([string]$Path)
  New-Item -ItemType Directory -Force -Path $Path | Out-Null
  $probe = Join-Path $Path ".codex_external_capture_write_probe"
  Set-Content -LiteralPath $probe -Value "ok" -Encoding ascii
  Remove-Item -LiteralPath $probe -Force
  Write-Detail "Writable output directory OK: $Path"
}

function Get-GameProcessName {
  return [System.IO.Path]::GetFileNameWithoutExtension($S1Exe)
}

function Get-GameProcesses {
  $processName = Get-GameProcessName
  return @(Get-Process -Name $processName -ErrorAction SilentlyContinue)
}

function Wait-GameProcess {
  param(
    [int[]]$BeforePids,
    [int]$TimeoutSec
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while((Get-Date) -lt $deadline)
  {
    $candidates = @(Get-GameProcesses | Where-Object { $BeforePids -notcontains $_.Id })
    if($candidates.Count -gt 0)
    {
      return ($candidates | Sort-Object Id -Descending | Select-Object -First 1)
    }
    Start-Sleep -Seconds 1
  }
  Fail "Timed out waiting for Game_x64h.exe to start"
}

function Get-SingleExistingGameProcess {
  $processes = @(Get-GameProcesses)
  if($processes.Count -eq 0)
  {
    Fail "No Game_x64h.exe process found for -SkipLaunch"
  }
  if($processes.Count -gt 1)
  {
    $ids = ($processes | ForEach-Object { $_.Id }) -join ", "
    Fail "Multiple Game_x64h.exe processes found for -SkipLaunch: $ids"
  }
  return $processes[0]
}

function Get-ProcessModulePaths {
  param([int]$ProcessId)
  try
  {
    $process = Get-Process -Id $ProcessId -ErrorAction Stop
    return @($process.Modules | ForEach-Object { [string]$_.FileName })
  }
  catch
  {
    Fail "Could not read modules for process $ProcessId. $($_.Exception.Message)"
  }
}

function Has-Path {
  param(
    [string[]]$Paths,
    [string]$Needle
  )
  foreach($path in $Paths)
  {
    if($path -ieq $Needle)
    {
      return $true
    }
  }
  return $false
}

function Wait-RenderDocModuleGate {
  param(
    [int]$ProcessId,
    [int]$TimeoutSec
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while((Get-Date) -lt $deadline)
  {
    $paths = @(Get-ProcessModulePaths -ProcessId $ProcessId)
    $renderdocPaths = @($paths | Where-Object { $_ -like "*renderdoc.dll" })
    if($VerboseLog -and $renderdocPaths.Count -gt 0)
    {
      Write-Detail ("RenderDoc modules: " + ($renderdocPaths -join "; "))
    }

    if(Has-Path -Paths $paths -Needle $SystemRenderDocDll)
    {
      Fail "System RenderDoc DLL loaded in process ${ProcessId}: $SystemRenderDocDll"
    }
    if(Has-Path -Paths $paths -Needle $DevRenderDocDll)
    {
      Write-Step "Module gate passed: development renderdoc.dll is loaded"
      return
    }
    Start-Sleep -Seconds 1
  }

  Fail "Timed out waiting for development renderdoc.dll in process $ProcessId"
}

function Wait-FileNonZero {
  param(
    [string]$Path,
    [int]$TimeoutSec
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while((Get-Date) -lt $deadline)
  {
    if(Test-Path -LiteralPath $Path -PathType Leaf)
    {
      $item = Get-Item -LiteralPath $Path
      if($item.Length -gt 0)
      {
        return $item
      }
    }
    Start-Sleep -Seconds 1
  }
  Fail "Capture file missing or empty after timeout: $Path"
}

function Invoke-LoggedCommand {
  param(
    [string]$Exe,
    [string[]]$Arguments,
    [string]$Stage,
    [int[]]$AllowedExitCodes = @()
  )

  if($VerboseLog)
  {
    $display = @($Exe) + $Arguments
    Write-Detail "$Stage command: $($display -join ' ')"
  }
  & $Exe @Arguments
  $exitCode = $LASTEXITCODE
  if($exitCode -ne 0 -and $AllowedExitCodes -notcontains $exitCode)
  {
    Fail "$Stage failed with exit code $exitCode"
  }
  if($exitCode -ne 0)
  {
    Write-Detail "$Stage returned accepted exit code $exitCode"
  }
  return $exitCode
}

function Invoke-TargetCapture {
  param(
    [string]$PythonExe,
    [string]$TriggerScript,
    [int]$Port,
    [int]$TimeoutSec
  )

  $triggerArgs = @(
    $TriggerScript,
    "--target-control-port",
    [string]$Port,
    "--timeout-sec",
    [string]$TimeoutSec,
    "--json"
  )
  if($VerboseLog)
  {
    Write-Detail "target-control command: $PythonExe $($triggerArgs -join ' ')"
  }
  $output = @(& $PythonExe @triggerArgs 2>&1)
  if($LASTEXITCODE -ne 0)
  {
    $output | ForEach-Object { Write-Host $_ }
    Fail "target-control capture trigger failed with exit code $LASTEXITCODE"
  }
  $jsonLine = @($output | Where-Object { $_ -match "^\s*\{" } | Select-Object -Last 1)
  if($jsonLine.Count -eq 0)
  {
    $output | ForEach-Object { Write-Host $_ }
    Fail "target-control capture trigger did not return JSON"
  }
  return ($jsonLine[0] | ConvertFrom-Json)
}

function Assert-ReportArtifacts {
  param(
    [string]$BundleDir,
    [string]$SmokeDir
  )

  $requiredFiles = @(
    "index.html",
    "events.html",
    "textures.html",
    "shaders.html",
    "manifest.json"
  )
  foreach($fileName in $requiredFiles)
  {
    $path = Join-Path $BundleDir $fileName
    if(-not (Test-Path -LiteralPath $path -PathType Leaf))
    {
      Fail "Report artifact missing: $path"
    }
  }

  $texturesPath = Join-Path $BundleDir "textures_data.json"
  if(-not (Test-Path -LiteralPath $texturesPath -PathType Leaf))
  {
    Fail "Report artifact missing: $texturesPath"
  }
  $texturesItem = Get-Item -LiteralPath $texturesPath
  if($texturesItem.Length -le 2)
  {
    Fail "textures_data.json is empty: $texturesPath"
  }
  $textures = @(Get-Content -LiteralPath $texturesPath -Raw | ConvertFrom-Json)
  if($textures.Count -eq 0)
  {
    Fail "textures_data.json has no texture rows: $texturesPath"
  }

  $smokeJson = Join-Path $SmokeDir "ui_smoke_result.json"
  if(-not (Test-Path -LiteralPath $smokeJson -PathType Leaf))
  {
    Fail "UI smoke result missing: $smokeJson"
  }
  $smoke = Get-Content -LiteralPath $smokeJson -Raw | ConvertFrom-Json
  if($smoke.overall_pass -ne $true)
  {
    Fail "UI smoke overall_pass is not true: $smokeJson"
  }
}

function Invoke-BundleReport {
  param(
    [string]$RepoRoot,
    [string]$CapturePath,
    [string]$Prefix
  )

  $oneClick = Join-Path $RepoRoot "scripts\rdc_analyzer\one_click_bundle_report.py"
  $bundleDir = "${Prefix}_bundle"
  $xmlPath = "${Prefix}.zip.xml"
  $smokeDir = "${Prefix}_ui_smoke"
  $reportArgs = @(
    "-3",
    $oneClick,
    $CapturePath,
    "-o",
    $bundleDir,
    "--xml-path",
    $xmlPath,
    "--renderdoccmd",
    $RenderDocCmd,
    "--force-texture-export",
    "--smoke-viewports",
    "1366x768,1920x1080",
    "--smoke-out",
    $smokeDir
  )
  if($VerboseLog)
  {
    Write-Detail "bundle command: py $($reportArgs -join ' ')"
  }
  $reportOutput = @(py @reportArgs 2>&1)
  $reportExitCode = $LASTEXITCODE
  $reportOutput | ForEach-Object { Write-Host $_ }
  if($reportExitCode -ne 0)
  {
    Fail "one_click_bundle_report.py failed with exit code $reportExitCode"
  }
  Assert-ReportArtifacts -BundleDir $bundleDir -SmokeDir $smokeDir
  return [PSCustomObject]@{
    BundleDir = $bundleDir
    XmlPath = $xmlPath
    ZipPath = "${Prefix}.zip"
    SmokeDir = $smokeDir
  }
}

function Invoke-EnvironmentCheck {
  param(
    [string]$RepoRoot,
    [string]$Prefix
  )

  $triggerScript = Join-Path $PSScriptRoot "trigger_target_capture.py"
  $oneClick = Join-Path $RepoRoot "scripts\rdc_analyzer\one_click_bundle_report.py"
  $smokeScript = Join-Path $RepoRoot "scripts\rdc_analyzer\tools\ui_headless_smoke.py"
  $pymodulesDir = "D:\Code\git\renderdoc\x64\Development\pymodules"

  Assert-ExistingFile -Path $RenderDocCmd -Label "renderdoccmd.exe"
  Assert-ExistingFile -Path $DevRenderDocDll -Label "development renderdoc.dll"
  Assert-ExistingFile -Path $TargetControlPython -Label "target-control Python"
  Assert-ExistingDirectory -Path $pymodulesDir -Label "development pymodules"
  Assert-ExistingFile -Path $S1Exe -Label "S1 Game_x64h.exe"
  Assert-ExistingDirectory -Path $S1Workdir -Label "S1 working directory"
  Assert-ExistingFile -Path $triggerScript -Label "target-control trigger script"
  Assert-ExistingFile -Path $oneClick -Label "one-click bundle script"
  Assert-ExistingFile -Path $smokeScript -Label "UI smoke script"
  Assert-WritableDirectory -Path (Split-Path -Parent $Prefix)
}

$launchedGameProcessId = $null
$capturePrefix = Resolve-CapturePrefix
$repoRoot = Get-RepoRoot

try
{
  Write-Step "Using capture prefix: $capturePrefix"
  Invoke-EnvironmentCheck -RepoRoot $repoRoot -Prefix $capturePrefix

  if($CheckOnly)
  {
    Write-Step "CheckOnly complete; no game process was launched"
    exit 0
  }

  if($SkipLaunch)
  {
    $gameProcess = Get-SingleExistingGameProcess
    Write-Step "Using existing Game_x64h.exe PID $($gameProcess.Id)"
  }
  else
  {
    $existing = @(Get-GameProcesses)
    if($existing.Count -gt 0)
    {
      $ids = ($existing | ForEach-Object { $_.Id }) -join ", "
      Fail "Existing Game_x64h.exe process(es) detected: $ids. Use -SkipLaunch or close them first."
    }

    $beforePids = @($existing | ForEach-Object { $_.Id })
    $captureArgs = @(
      "capture",
      "--capture-file",
      $capturePrefix,
      "--working-dir",
      $S1Workdir,
      "--opt-capture-all-cmd-lists",
      $S1Exe
    ) + $GameArgs
    Invoke-LoggedCommand -Exe $RenderDocCmd -Arguments $captureArgs -Stage "renderdoccmd capture" -AllowedExitCodes (38920..38927) | Out-Null
    $gameProcess = Wait-GameProcess -BeforePids $beforePids -TimeoutSec $LaunchTimeoutSec
    $launchedGameProcessId = $gameProcess.Id
    Write-Step "Launched Game_x64h.exe PID $launchedGameProcessId"
  }

  Wait-RenderDocModuleGate -ProcessId $gameProcess.Id -TimeoutSec $ModuleTimeoutSec

  if($PreCaptureDelaySec -gt 0)
  {
    Write-Step "Waiting $PreCaptureDelaySec seconds before triggering capture"
    Start-Sleep -Seconds $PreCaptureDelaySec
  }

  $triggerScriptPath = Join-Path $PSScriptRoot "trigger_target_capture.py"
  $captureInfo = Invoke-TargetCapture -PythonExe $TargetControlPython -TriggerScript $triggerScriptPath -Port $TargetControlPort -TimeoutSec $CaptureTimeoutSec
  $capturePath = [string]$captureInfo.path
  $captureItem = Wait-FileNonZero -Path $capturePath -TimeoutSec $CaptureTimeoutSec
  Write-Step "New capture: $capturePath"
  Write-Step "Capture frame/API/PID: frame=$($captureInfo.frame), api=$($captureInfo.api), pid=$($captureInfo.pid), bytes=$($captureItem.Length)"

  $reportInfo = $null
  if($SkipReport)
  {
    Write-Step "SkipReport set; bundle generation skipped"
  }
  else
  {
    $reportInfo = Invoke-BundleReport -RepoRoot $repoRoot -CapturePath $capturePath -Prefix $capturePrefix
    Write-Step "Bundle report: $($reportInfo.BundleDir)"
    Write-Step "UI smoke artifacts: $($reportInfo.SmokeDir)"
  }

  Write-Step "External RenderDoc capture workflow completed"
  exit 0
}
catch
{
  Write-Error $_.Exception.Message
  exit 1
}
finally
{
  if($launchedGameProcessId -ne $null -and -not $KeepGameAlive)
  {
    $liveProcess = Get-Process -Id $launchedGameProcessId -ErrorAction SilentlyContinue
    if($liveProcess)
    {
      Write-Step "Stopping launched Game_x64h.exe PID $launchedGameProcessId"
      Stop-Process -Id $launchedGameProcessId -Force
    }
  }
}
