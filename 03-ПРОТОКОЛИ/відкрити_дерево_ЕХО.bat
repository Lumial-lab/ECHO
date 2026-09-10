@echo off
rem no cyrillic literals: cmd reads .bat in OEM codepage; %~dp0 carries the path safely
cd /d "%~dp0"
"C:\Users\lpghu\AppData\Local\Programs\Python\Python313\python.exe" -X utf8 "%~dp0roy_map.py" --dag ysu
"C:\Users\lpghu\AppData\Local\Programs\Python\Python313\python.exe" -X utf8 "%~dp0roy_map.py" --dag mx-lab
start "" "%~dp0roy_map_ysu.html"
start "" "%~dp0roy_map_mx-lab.html"
