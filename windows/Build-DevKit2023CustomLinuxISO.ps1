[CmdletBinding(DefaultParameterSetName='ThisTarget')]
param(
    [string]$Distribution='Debian',
    [Parameter(Mandatory,ParameterSetName='ThisTarget')][switch]$TargetThisDevice,
    [Parameter(Mandatory,ParameterSetName='ExportedTarget')][string]$TargetBundle,
    [switch]$ReplaceExisting,
    [switch]$PassThru
)
# One public build entry point; collection always requires an explicit target.
$parameters = @{ Distribution=$Distribution; ReplaceExisting=$ReplaceExisting; PassThru=$PassThru }
if ($PSCmdlet.ParameterSetName -eq 'ThisTarget') { $parameters.TargetThisDevice=$TargetThisDevice }
else { $parameters.TargetBundle=$TargetBundle }
& (Join-Path $PSScriptRoot 'Prepare-DevKit2023CustomLinux.ps1') @parameters
