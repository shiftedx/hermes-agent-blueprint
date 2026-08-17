<#
.SYNOPSIS
  Register a Windows Scheduled Task that ticks the Hermes cron scheduler every minute.

.DESCRIPTION
  On a desktop-only install nothing fires scheduled jobs: Hermes cron is run by the
  gateway's background ticker, and the desktop app does not tick it. `hermes cron tick`
  runs any due jobs once and exits, which is exactly what a scheduled task should call.

  This registers one task that repeats every minute, indefinitely, hidden (no console
  window flashing once a minute). A lock file at <HERMES_ROOT>\cron\.tick.lock keeps
  overlapping ticks from double-running a batch, so a one-minute interval is safe.

.PARAMETER Profile
  Hermes profile name. Required.

.PARAMETER HermesExe
  Full path to hermes.exe. Auto-detected if omitted.

.EXAMPLE
  .\setup-windows-scheduler.ps1 -Profile myagent

.NOTES
  Run in a normal (non-elevated) PowerShell. The task runs as the current user, only
  while that user is logged on — correct for a desktop that stays signed in. If the
  machine is used logged-out, re-create the task with -User/-Password so it runs
  regardless, which requires storing credentials.

  VERIFY THIS WORKED. Do not assume. The verification steps are printed at the end.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Profile,
    [string]$HermesExe,
    [string]$TaskName
)

$ErrorActionPreference = 'Stop'
if (-not $TaskName) { $TaskName = "Hermes cron tick ($Profile)" }

# --- locate hermes.exe -------------------------------------------------------
if (-not $HermesExe) {
    $cmd = Get-Command hermes -ErrorAction SilentlyContinue
    if ($cmd) {
        $HermesExe = $cmd.Source
    } else {
        $candidates = @(
            (Join-Path $env:LOCALAPPDATA 'hermes\bin\hermes.exe'),
            (Join-Path $env:LOCALAPPDATA 'hermes\hermes.exe'),
            (Join-Path $env:LOCALAPPDATA 'Programs\hermes\hermes.exe')
        )
        $HermesExe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    }
}
if (-not $HermesExe -or -not (Test-Path $HermesExe)) {
    throw "Could not find hermes.exe. Pass it explicitly: -HermesExe 'C:\path\to\hermes.exe'"
}
Write-Host "hermes.exe : $HermesExe"
Write-Host "profile    : $Profile"
Write-Host "task name  : $TaskName"

# --- prove the command works before scheduling it ----------------------------
Write-Host "`nRunning one tick now to confirm the command is valid..."
& $HermesExe --profile $Profile cron tick
if ($LASTEXITCODE -ne 0) {
    throw "'hermes --profile $Profile cron tick' exited $LASTEXITCODE. Fix that before scheduling it."
}
Write-Host "Tick command works." -ForegroundColor Green

# --- register the task -------------------------------------------------------
$action = New-ScheduledTaskAction -Execute $HermesExe -Argument "--profile $Profile cron tick"

# Repeat every minute forever. A start time in the past means it begins immediately.
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(-1) `
    -RepetitionInterval (New-TimeSpan -Minutes 1)

$settings = New-ScheduledTaskSettingsSet -Hidden `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Write-Host "`nExisting task found — replacing it."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Ticks the Hermes cron scheduler every minute (profile: $Profile)." | Out-Null

Write-Host "`nRegistered '$TaskName'." -ForegroundColor Green

Write-Host @"

VERIFY — do all three, do not skip:

  1. Task is registered and ready:
       Get-ScheduledTask -TaskName "$TaskName" | Select-Object TaskName, State

  2. It actually ran (check a couple of minutes from now; LastTaskResult 0 = OK):
       Get-ScheduledTaskInfo -TaskName "$TaskName" |
         Select-Object LastRunTime, LastTaskResult, NextRunTime

  3. End to end — create a throwaway job due in ~2 minutes, wait for it, and confirm
     output lands in the cron output directory. Then delete the job. This is the only
     check that proves the whole chain works:
       hermes --profile $Profile cron list
       # ...and look in:  %LOCALAPPDATA%\hermes\cron\output\

  To remove later:
       Unregister-ScheduledTask -TaskName "$TaskName" -Confirm:`$false
"@
