@echo off
FOR /L %%i IN (1,1,5) DO (
    echo This is iteration %%i
    python update_youtube.py
)
