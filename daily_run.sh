#!/bin/bash

python src/update_youtube.py
python src/verify_chinese.py
git add .
git commit -am .
git push

