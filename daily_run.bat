REM @echo off

REM �۰ʤ����� bat �ɮצۨ��Ҧb���ؿ�
cd /d "%~dp0"

REM �Ұʵ�������
call Scripts\activate.bat

REM ���� Python �}��
git pull
python src/update_youtube.py
git pull
git add .
git commit -am .
git push

REM ���ε������ҡ]�i��^
call Scripts\deactivate.bat
