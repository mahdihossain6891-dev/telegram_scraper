$ports = 8510, 8501, 3000
foreach ($port in $ports) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        ForEach-Object {
            $listenPid = $_
            Write-Host "Stopping PID $listenPid on port $port"
            # Also stop uvicorn reload children that share the same tree.
            Get-CimInstance Win32_Process |
                Where-Object {
                    $_.ProcessId -eq $listenPid -or
                    $_.ParentProcessId -eq $listenPid -or
                    ($_.CommandLine -and $_.CommandLine -like '*uvicorn*server:app*')
                } |
                ForEach-Object {
                    Write-Host "  kill $($_.ProcessId)"
                    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
                }
        }
}
Start-Sleep -Seconds 2
Write-Host "Remaining listeners:"
Get-NetTCPConnection -LocalPort 8510,8501,3000 -State Listen -ErrorAction SilentlyContinue |
    Select-Object LocalPort, OwningProcess
