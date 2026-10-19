param(
    [string]$Title = "KeepDesk",
    [string]$Out = "tmp\win.png",
    [int]$ProcId = 0
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

if (-not ("Win" -as [type])) {
    Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class Win {
    public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr lParam);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdc, uint flags);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
"@
}

$script:matches = @()
$callback = [Win+EnumProc]{
    param($hWnd, $lParam)
    if (-not [Win]::IsWindowVisible($hWnd)) { return $true }
    $procId = 0
    [Win]::GetWindowThreadProcessId($hWnd, [ref]$procId) | Out-Null
    if ($ProcId -ne 0 -and $procId -ne $ProcId) { return $true }
    $sb = New-Object System.Text.StringBuilder 512
    [Win]::GetWindowText($hWnd, $sb, 512) | Out-Null
    $text = $sb.ToString()
    if ($text -and $text.Contains($Title)) {
        $script:matches += [pscustomobject]@{ Hwnd = $hWnd; Title = $text; Pid = $procId }
    }
    return $true
}
[Win]::EnumWindows($callback, [IntPtr]::Zero) | Out-Null

if (-not $script:matches) {
    Write-Output "window containing '$Title' not found"
    exit 1
}

$target = $script:matches[0]
Write-Output ("matched: '{0}' (pid {1})" -f $target.Title, $target.Pid)

$rect = New-Object Win+RECT
[Win]::GetWindowRect($target.Hwnd, [ref]$rect) | Out-Null
$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top

$bmp = New-Object System.Drawing.Bitmap $width, $height
$graphics = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $graphics.GetHdc()
$ok = [Win]::PrintWindow($target.Hwnd, $hdc, 2)
$graphics.ReleaseHdc($hdc)
$graphics.Dispose()
$bmp.Save((Join-Path (Get-Location) $Out), [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Output "captured ${width}x${height} ok=$ok -> $Out"
