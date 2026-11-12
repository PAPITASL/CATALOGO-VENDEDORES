Option Explicit
Dim shell, fso, root, python, launcher, code
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
python = root & "\runtime\pythonw.exe"
If Not fso.FileExists(python) Then python = root & "\.venv\Scripts\pythonw.exe"
launcher = root & "\desktop.py"
If Not fso.FileExists(python) Then
    MsgBox "No se encontro el Python local de Lujoshop en .venv. Restaure el entorno de la aplicacion.", 16, "Lujoshop"
    WScript.Quit 1
End If
shell.CurrentDirectory = root
code = shell.Run("""" & python & """ """ & launcher & """", 0, True)
If code <> 0 Then
    MsgBox "Lujoshop no pudo iniciarse. Consulte desktop-data\logs\desktop.log dentro de la carpeta de la aplicacion.", 16, "Lujoshop"
End If
