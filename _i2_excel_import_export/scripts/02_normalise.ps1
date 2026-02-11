$Base = "C:\Users\44752\Desktop\Control Room\_i2_excel_import_export"

function Normalise-Phone($v) {
    if (!$v) { return $v }
    $v = $v -replace '\s',''
    if ($v.StartsWith("07")) { return "44" + $v.Substring(1) }
    if ($v.StartsWith("+44")) { return $v.Substring(1) }
    return $v
}

function Normalise-Date($v) {
    try {
        return (Get-Date $v).ToString("yyyy-MM-dd HH:mm:ss")
    } catch {
        return $v
    }
}

function Clean-Csv($Path, $PhoneCols, $DateCols) {
    $rows = Import-Csv $Path
    foreach ($row in $rows) {
        foreach ($p in $PhoneCols) {
            if ($row.$p) { $row.$p = Normalise-Phone $row.$p }
        }
        foreach ($d in $DateCols) {
            if ($row.$d) { $row.$d = Normalise-Date $row.$d }
        }
    }
    $rows | Export-Csv $Path -NoTypeInformation -Encoding UTF8
}

Clean-Csv "$Base\entities\entity_phone.csv" @("MSISDN") @()
Clean-Csv "$Base\links\link_call.csv" @() @("StartDateTime")
Clean-Csv "$Base\links\link_meeting.csv" @() @("DateTime")

Write-Host "✅ Normalisation complete"
