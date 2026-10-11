param([Parameter(Mandatory=$true)][string]$SourcePath,
      [Parameter(Mandatory=$true)][string]$CandidatePath,
      [Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$reportWord = $null
$openedReport = $null
try {
    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
    $reportWord = New-Object -ComObject Word.Application
    $reportWord.Visible = $false
    $reportWord.DisplayAlerts = 0
    $reportWord.AutomationSecurity = 3
    foreach ($item in @(@{Path=$SourcePath; Name='baseline.pdf'},
                        @{Path=$CandidatePath; Name='candidate.pdf'})) {
        $openedReport = $reportWord.Documents.Open($item.Path, $false, $true, $false)
        $openedReport.Repaginate()
        $reportPdf = Join-Path $OutputDirectory $item.Name
        $openedReport.ExportAsFixedFormat($reportPdf, 17)
        Write-Output ($item.Name + ': ' + $openedReport.ComputeStatistics(2) + ' pages')
        $openedReport.Close(0)
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($openedReport)
        $openedReport = $null
    }
} finally {
    if ($null -ne $openedReport) {
        $openedReport.Close(0)
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($openedReport)
    }
    if ($null -ne $reportWord) {
        if ($reportWord.Documents.Count -eq 0) { $reportWord.Quit() }
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($reportWord)
    }
}
