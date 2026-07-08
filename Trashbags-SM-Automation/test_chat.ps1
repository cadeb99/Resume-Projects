# Trashbags DM bot - terminal tester
# Chat with the bot from your terminal: type a customer message, see how it would reply.
#
# Run it:   .\test_chat.ps1
# Quit:     type  exit  (or press Ctrl+C)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8   # so emojis show properly
$base = "http://127.0.0.1:8000"
$root = $PSScriptRoot
$sender = "terminal_" + (Get-Random -Maximum 99999)        # one conversation per run, so the bot remembers context

function Test-Server {
    try { Invoke-RestMethod "$base/health" -TimeoutSec 3 | Out-Null; return $true } catch { return $false }
}

Write-Host ""
Write-Host "  Trashbags DM bot - terminal tester" -ForegroundColor Cyan
Write-Host "  Type a message like a customer would. Type 'exit' to quit." -ForegroundColor DarkGray
Write-Host ""

if (-not (Test-Server)) {
    Write-Host "  The bot server isn't running. Open another terminal and start it with:" -ForegroundColor Yellow
    Write-Host "    cd `"$root`"" -ForegroundColor Gray
    Write-Host "    .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000" -ForegroundColor Gray
    Write-Host "  then run this script again." -ForegroundColor Yellow
    Write-Host ""
    return
}

while ($true) {
    Write-Host "you (customer): " -ForegroundColor Green -NoNewline
    $text = Read-Host
    if ([string]::IsNullOrWhiteSpace($text)) { continue }
    if ($text.Trim().ToLower() -in @("exit", "quit", "q")) { break }

    try {
        $body = @{ sender_id = $sender; text = $text } | ConvertTo-Json
        $r = Invoke-RestMethod -Method Post "$base/simulate" -ContentType "application/json" -Body $body
    } catch {
        Write-Host "  (couldn't reach the bot: $($_.Exception.Message))" -ForegroundColor Red
        continue
    }

    Write-Host ""
    Write-Host "trashbags bot: " -ForegroundColor Magenta -NoNewline
    Write-Host $r.ai_reply
    if ($r.human_takeover) {
        Write-Host ("  -> flagged to the owner: " + $r.takeover_reason) -ForegroundColor Yellow
    } else {
        Write-Host ("  -> would send to the customer after ~" + $r.response_delay_minutes + " min") -ForegroundColor DarkGray
    }
    Write-Host ""
}

Write-Host "  later dawg." -ForegroundColor Cyan
Write-Host ""
