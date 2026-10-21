Option Explicit
Dim shell, fso, root, electron, entry
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
electron = fso.BuildPath(root, "electron\node_modules\electron\dist\electron.exe")
entry = fso.BuildPath(root, "electron")
If Not fso.FileExists(electron) Then
  MsgBox "Eloszor futtasd az NG_TELEPITES.cmd fajlt ebben a mappaban.", 48, "Jarvis inditas"
  WScript.Quit 1
End If
If Not fso.FileExists(fso.BuildPath(root, "venv\Scripts\python.exe")) Then
  MsgBox "Hianyzik a Python kornyezet. Futtasd az NG_TELEPITES.cmd fajlt.", 48, "Jarvis inditas"
  WScript.Quit 1
End If
shell.CurrentDirectory = root
shell.Run Chr(34) & electron & Chr(34) & " " & Chr(34) & entry & Chr(34), 1, False
