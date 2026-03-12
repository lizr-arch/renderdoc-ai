param(
  [Parameter(Mandatory = $true)]
  [string]$CommitHash,
  [string]$RepoRoot = "",
  [string]$JavaHome = "",
  [string]$AndroidSdk = "",
  [string]$AndroidNdk = "",
  [string]$HostClang = "",
  [string]$AaptPath = "C:\Program Files\RenderDoc\plugins\android\aapt.exe",
  [string]$PluginDir = "",
  [switch]$SkipBuild,
  [switch]$SkipCopy,
  [switch]$ResetDevicePackages
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info([string]$text)
{
  Write-Host "[INFO] $text"
}

function Require-Path([string]$path, [string]$name)
{
  if(-not (Test-Path $path))
  {
    throw "$name not found: $path"
  }
}

function Run-Step([string]$name, [scriptblock]$action)
{
  Write-Info "Step: $name"
  & $action
}

function Find-RepoRoot()
{
  if($RepoRoot)
  {
    return (Resolve-Path $RepoRoot).Path
  }
  return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Find-JavaHome()
{
  if($JavaHome)
  {
    return $JavaHome
  }
  if($env:JAVA_HOME)
  {
    return $env:JAVA_HOME
  }

  $candidates = @(
    "C:\Program Files\Java\jdk-16.0.2",
    "C:\Program Files\Java\jdk-17",
    "C:\Program Files\Microsoft\jdk-17.0.9.8-hotspot"
  )
  foreach($candidate in $candidates)
  {
    if(Test-Path (Join-Path $candidate "bin\java.exe"))
    {
      return $candidate
    }
  }

  throw "JAVA_HOME is not set and no fallback JDK was found."
}

function Find-AndroidSdk()
{
  if($AndroidSdk)
  {
    return $AndroidSdk
  }

  $candidates = @(
    $env:ANDROID_SDK_ROOT,
    $env:ANDROID_HOME,
    $env:ANDROID_SDK,
    (Join-Path $env:LOCALAPPDATA "Android\Sdk")
  ) | Where-Object { $_ -and $_.Trim() -ne "" }

  foreach($candidate in $candidates)
  {
    if(Test-Path (Join-Path $candidate "build-tools"))
    {
      return $candidate
    }
  }

  throw "Android SDK not found. Set ANDROID_SDK_ROOT/ANDROID_HOME/ANDROID_SDK."
}

function Find-AndroidNdk([string]$sdkPath)
{
  if($AndroidNdk)
  {
    return $AndroidNdk
  }

  $candidates = @(
    $env:ANDROID_NDK_HOME,
    $env:ANDROID_NDK_ROOT,
    $env:NDK_HOME,
    $env:ANDROID_NDK
  ) | Where-Object { $_ -and $_.Trim() -ne "" }

  foreach($candidate in $candidates)
  {
    if(Test-Path (Join-Path $candidate "build\cmake\android.toolchain.cmake"))
    {
      return $candidate
    }
  }

  $ndkRoot = Join-Path $sdkPath "ndk"
  if(Test-Path $ndkRoot)
  {
    $latest = Get-ChildItem $ndkRoot -Directory | Sort-Object Name -Descending | Select-Object -First 1
    if($latest)
    {
      $toolchain = Join-Path $latest.FullName "build\cmake\android.toolchain.cmake"
      if(Test-Path $toolchain)
      {
        return $latest.FullName
      }
    }
  }

  throw "Android NDK not found. Set ANDROID_NDK_HOME/ANDROID_NDK_ROOT/NDK_HOME/ANDROID_NDK."
}

function Find-HostClang()
{
  if($HostClang)
  {
    return $HostClang
  }

  try
  {
    $whereMatches = & where.exe clang++ 2>$null
    if($LASTEXITCODE -eq 0 -and $whereMatches)
    {
      $first = ($whereMatches | Select-Object -First 1).Trim()
      if($first -and (Test-Path $first))
      {
        return $first
      }
    }
  }
  catch
  {
  }

  $programFiles = ${env:ProgramFiles}
  $programFilesX86 = ${env:ProgramFiles(x86)}

  $candidates = @(
    (Join-Path $programFiles "Microsoft Visual Studio\2022\Community\VC\Tools\Llvm\x64\bin\clang++.exe"),
    (Join-Path $programFiles "Microsoft Visual Studio\2022\Professional\VC\Tools\Llvm\x64\bin\clang++.exe"),
    (Join-Path $programFiles "Microsoft Visual Studio\2022\Enterprise\VC\Tools\Llvm\x64\bin\clang++.exe"),
    (Join-Path $programFiles "Microsoft Visual Studio\2022\BuildTools\VC\Tools\Llvm\x64\bin\clang++.exe"),
    (Join-Path $programFiles "LLVM\bin\clang++.exe"),
    (Join-Path $programFilesX86 "LLVM\bin\clang++.exe")
  )

  foreach($candidate in $candidates)
  {
    if($candidate -and (Test-Path $candidate))
    {
      return $candidate
    }
  }

  $driveCandidates = Get-PSDrive -PSProvider FileSystem | Select-Object -ExpandProperty Root
  foreach($root in $driveCandidates)
  {
    $vsPattern = Join-Path $root "Program Files\Microsoft Visual Studio\2022\*\VC\Tools\Llvm\x64\bin\clang++.exe"
    $vsMatch = Get-ChildItem -Path $vsPattern -ErrorAction SilentlyContinue | Select-Object -First 1
    if($vsMatch)
    {
      return $vsMatch.FullName
    }

    $llvmPattern = Join-Path $root "Program Files\LLVM\bin\clang++.exe"
    $llvmMatch = Get-ChildItem -Path $llvmPattern -ErrorAction SilentlyContinue | Select-Object -First 1
    if($llvmMatch)
    {
      return $llvmMatch.FullName
    }
  }

  throw "Host clang++ not found. Pass -HostClang explicitly."
}

function Update-HostCompilerWrapper([string]$wrapperPath, [string]$clangPath)
{
  $wrapperDir = Split-Path -Parent $wrapperPath
  New-Item -ItemType Directory -Path $wrapperDir -Force | Out-Null

  $content = @"
@echo off
setlocal
"$clangPath" %*
exit /b %ERRORLEVEL%
"@
  Set-Content -Path $wrapperPath -Value $content -Encoding ascii
}

function Patch-IncludeBinInNinja([string]$ninjaPath)
{
  Require-Path $ninjaPath "build.ninja"

  $raw = Get-Content -Path $ninjaPath -Raw
  $patched = $raw
  $patched = $patched -replace '(?<!\.exe)\bbin/include-bin\b', 'bin/include-bin.exe'
  $patched = $patched -replace '(?<!\.exe)\\bin\\include-bin\b', '\bin\include-bin.exe'

  if($patched -ne $raw)
  {
    Set-Content -Path $ninjaPath -Value $patched -Encoding ascii
    Write-Info "Patched include-bin => include-bin.exe in $ninjaPath"
  }
  else
  {
    Write-Info "No include-bin patch needed in $ninjaPath"
  }
}

function Configure-And-Build(
  [string]$repoPath,
  [string]$buildDirName,
  [string]$abi,
  [string]$toolchainFile,
  [string]$wrapperPath,
  [string]$hash)
{
  $buildDir = Join-Path $repoPath $buildDirName

  if(-not $SkipBuild)
  {
    if(Test-Path $buildDir)
    {
      Remove-Item -Path $buildDir -Recurse -Force
    }

    $wrapperForCMake = $wrapperPath -replace '\\', '/'
    $toolchainForCMake = $toolchainFile -replace '\\', '/'

    Push-Location $repoPath
    try
    {
      & cmake -S . -B $buildDirName -G Ninja `
        "-DCMAKE_TOOLCHAIN_FILE=$toolchainForCMake" `
        -DBUILD_ANDROID=On `
        "-DANDROID_ABI=$abi" `
        "-DBUILD_VERSION_HASH=$hash" `
        "-DHOST_NATIVE_CPP_COMPILER=$wrapperForCMake"
      if($LASTEXITCODE -ne 0)
      {
        throw "CMake configure failed for $abi"
      }

      Patch-IncludeBinInNinja (Join-Path $buildDir "build.ninja")

      & cmake --build $buildDirName -j8
      if($LASTEXITCODE -ne 0)
      {
        throw "CMake build failed for $abi"
      }
    }
    finally
    {
      Pop-Location
    }
  }
  else
  {
    Patch-IncludeBinInNinja (Join-Path $buildDir "build.ninja")
  }
}

function Validate-Apk([string]$aapt, [string]$apkPath, [string]$hash)
{
  Require-Path $apkPath "APK"
  Require-Path $aapt "aapt"

  $badging = & $aapt dump badging $apkPath
  if($LASTEXITCODE -ne 0)
  {
    throw "aapt badging failed: $apkPath"
  }

  $badgingText = ($badging -join "`n")

  if($badgingText -notmatch "versionName='$([regex]::Escape($hash))'")
  {
    throw "APK versionName mismatch: $apkPath"
  }

  $versionLine = ($badging | Where-Object { $_ -match "versionCode=" } | Select-Object -First 1)
  $nameLine = ($badging | Where-Object { $_ -match "versionName=" } | Select-Object -First 1)
  Write-Info "$apkPath"
  Write-Info "  $versionLine"
  Write-Info "  $nameLine"
}

function Copy-Apk([string]$srcPath, [string]$dstDir)
{
  New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
  Copy-Item -Path $srcPath -Destination $dstDir -Force
}

function Reset-DevicePackages()
{
  & adb uninstall org.renderdoc.renderdoccmd.arm32 | Out-Host
  & adb uninstall org.renderdoc.renderdoccmd.arm64 | Out-Host
  & adb kill-server | Out-Host
  & adb start-server | Out-Host
  & adb devices -l | Out-Host
}

$repoPath = Find-RepoRoot
if(-not $PluginDir)
{
  $PluginDir = Join-Path $repoPath "x64\Development\plugins\android"
}

$resolvedJavaHome = Find-JavaHome
$resolvedSdk = Find-AndroidSdk
$resolvedNdk = Find-AndroidNdk $resolvedSdk
$resolvedHostClang = Find-HostClang
$toolchain = Join-Path $resolvedNdk "build\cmake\android.toolchain.cmake"
$wrapper = Join-Path $repoPath "build-android-tools\host-clangpp.cmd"

Require-Path $toolchain "Android toolchain file"
Require-Path (Join-Path $resolvedJavaHome "bin\java.exe") "JAVA_HOME\bin\java.exe"

$env:JAVA_HOME = $resolvedJavaHome
$env:ANDROID_HOME = $resolvedSdk
$env:ANDROID_SDK_ROOT = $resolvedSdk
$env:ANDROID_SDK = $resolvedSdk
$env:ANDROID_NDK_HOME = $resolvedNdk
$env:ANDROID_NDK_ROOT = $resolvedNdk
$env:NDK_HOME = $resolvedNdk
$env:ANDROID_NDK = $resolvedNdk

Run-Step "Write host compiler wrapper" {
  Update-HostCompilerWrapper $wrapper $resolvedHostClang
}

Run-Step "Configure/Build arm32" {
  Configure-And-Build $repoPath "build-android-arm32" "armeabi-v7a" $toolchain $wrapper $CommitHash
}

Run-Step "Configure/Build arm64" {
  Configure-And-Build $repoPath "build-android-arm64" "arm64-v8a" $toolchain $wrapper $CommitHash
}

$arm32Apk = Join-Path $repoPath "build-android-arm32\bin\org.renderdoc.renderdoccmd.arm32.apk"
$arm64Apk = Join-Path $repoPath "build-android-arm64\bin\org.renderdoc.renderdoccmd.arm64.apk"

Run-Step "Validate built APKs" {
  Validate-Apk $AaptPath $arm32Apk $CommitHash
  Validate-Apk $AaptPath $arm64Apk $CommitHash
}

if(-not $SkipCopy)
{
  Run-Step "Copy APKs to qrenderdoc plugin dir" {
    Copy-Apk $arm32Apk $PluginDir
    Copy-Apk $arm64Apk $PluginDir
    Validate-Apk $AaptPath (Join-Path $PluginDir "org.renderdoc.renderdoccmd.arm32.apk") $CommitHash
    Validate-Apk $AaptPath (Join-Path $PluginDir "org.renderdoc.renderdoccmd.arm64.apk") $CommitHash
  }
}

if($ResetDevicePackages)
{
  Run-Step "Reset device renderdoc packages" {
    Reset-DevicePackages
  }
}

Write-Info "Done."
