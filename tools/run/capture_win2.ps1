# capture_win2.ps1 -- capture the game window of a pid (PrintWindow, DPI aware, no focus needed).
param([Parameter(Mandatory=$true)][int]$ProcessId, [Parameter(Mandatory=$true)][string]$Out)
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class W2 {
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  public struct RECT { public int Left, Top, Right, Bottom; }
  public static IntPtr best; public static int bestW, bestH;
  static bool Cb(IntPtr hh, IntPtr p) {
    uint pid; GetWindowThreadProcessId(hh, out pid);
    if (pid != (uint)(long)p || !IsWindowVisible(hh)) return true;
    var sb = new StringBuilder(512); GetWindowTextW(hh, sb, 512);
    if (sb.Length == 0) return true;
    RECT r; GetWindowRect(hh, out r);
    int ww = r.Right - r.Left, hh2 = r.Bottom - r.Top;
    if ((long)ww * hh2 > (long)bestW * bestH) { best = hh; bestW = ww; bestH = hh2; }
    return true; }
  public static IntPtr Find(uint want) { best = IntPtr.Zero; bestW = 0; bestH = 0; EnumWindows(Cb, (IntPtr)(long)want); return best; }
}
"@
[void][W2]::SetProcessDPIAware()
$hnd = [W2]::Find([uint32]$ProcessId)
if ($hnd -eq [IntPtr]::Zero) { Write-Output "no window for pid $ProcessId"; exit 1 }
$w = [W2]::bestW; $h = [W2]::bestH
Write-Output "window $hnd  ${w}x${h}"
$bmp = New-Object System.Drawing.Bitmap $w, $h
$g = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $g.GetHdc()
[void][W2]::PrintWindow($hnd, $hdc, 2)
$g.ReleaseHdc($hdc); $g.Dispose()
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Output "saved $Out"
