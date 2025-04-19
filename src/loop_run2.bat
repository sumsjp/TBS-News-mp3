@echo off
FOR /L %%i IN (1,1,130) DO (
    echo This is iteration %%i
    python update_youtube2.py
)
