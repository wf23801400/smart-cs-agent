[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$result = Invoke-RestMethod -Uri http://localhost:8000/chat -Method Post -ContentType "application/json" -Body '{"message":"退货退款要几天到账？"}'
Write-Output $result.reply
