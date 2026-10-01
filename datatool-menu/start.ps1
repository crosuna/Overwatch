# Starts the DataTool menu and opens it in your browser. Close this window to stop it.
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
python "$here\server.py"
