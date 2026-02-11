$InputXlsx = "C:\Users\44752\Desktop\raw_input.xlsx"
$Out = "C:\Users\44752\Desktop\Control Room\_i2_excel_import_export"

Import-Module ImportExcel

$data = Import-Excel $InputXlsx

$data |
    Select Forename,Surname,DOB,Nationality |
    Export-Csv "$Out\entities\entity_person.csv" -Append -NoTypeInformation

$data |
    Select MSISDN,IMEI,Network |
    Export-Csv "$Out\entities\entity_phone.csv" -Append -NoTypeInformation

$data |
    Select From_Phone,To_Phone,StartDateTime,DurationSeconds |
    Export-Csv "$Out\links\link_call.csv" -Append -NoTypeInformation

Write-Host "✅ Excel split complete"
