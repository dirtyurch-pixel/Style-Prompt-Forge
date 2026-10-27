' Style Prompt Forge - double-click to open it in its own window.
' Each time it also makes sure there's a Style Prompt Forge shortcut on your desktop and in the Start menu.
' The first time (or after moving the folder) it runs a one-minute setup in a visible window.
Option Explicit
Dim fso, sh, here, pyw, rc, places, p, lnk
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
here = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = here

places = Array(sh.SpecialFolders("Desktop"), sh.SpecialFolders("Programs"))
For Each p In places
  If p <> "" Then
    Set lnk = sh.CreateShortcut(p & "\Style Prompt Forge.lnk")
    lnk.TargetPath = sh.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\wscript.exe"
    lnk.Arguments = """" & WScript.ScriptFullName & """"
    lnk.IconLocation = here & "\forge.ico,0"
    lnk.WorkingDirectory = here
    lnk.Description = "Style Prompt Forge - Suno v6 prompt builder"
    lnk.Save
  End If
Next

pyw = here & "\.venv\Scripts\pythonw.exe"
If fso.FileExists(pyw) Then
  rc = sh.Run("""" & pyw & """ -c ""import anthropic""", 0, True)
  If rc = 0 Then
    sh.Run """" & pyw & """ """ & here & "\app.py""", 0, False
    WScript.Quit
  End If
End If
sh.Run """" & here & "\Setup.bat""", 1, False
