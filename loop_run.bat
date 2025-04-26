@echo off
FOR /L %%i IN (1,1,10) DO (
    echo This is iteration %%i
    python update_youtube.py
)
