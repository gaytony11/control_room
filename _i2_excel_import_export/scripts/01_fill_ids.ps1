$Base = "C:\Users\44752\Desktop\Control Room\_i2_excel_import_export"

function Fill-Ids {
    param (
        $Path,
        $IdColumn,
        $Prefix
    )

    $rows = Import-Csv $Path
    $counter = 1

    foreach ($row in $rows) {
        if (-not $row.$IdColumn -or $row.$IdColumn.Trim() -eq "") {
            $row.$IdColumn = "{0}{1:D6}" -f $Prefix, $counter
            $counter++
        }
    }

    $rows | Export-Csv $Path -NoTypeInformation -Encoding UTF8
}

Fill-Ids "$Base\entities\entity_person.csv"   "Person_ID"  "PER-"
Fill-Ids "$Base\entities\entity_phone.csv"    "Phone_ID"   "PHN-"
Fill-Ids "$Base\entities\entity_vehicle.csv"  "Vehicle_ID" "VEH-"
Fill-Ids "$Base\entities\entity_company.csv"  "Company_ID" "COM-"

Fill-Ids "$Base\links\link_call.csv"           "Link_ID" "LNK-"
Fill-Ids "$Base\links\link_vehicle_keeper.csv" "Link_ID" "LNK-"
Fill-Ids "$Base\links\link_director.csv"       "Link_ID" "LNK-"
Fill-Ids "$Base\links\link_meeting.csv"        "Link_ID" "LNK-"

Write-Host "✅ IDs filled where missing"
