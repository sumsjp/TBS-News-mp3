import os
import re
import pandas as pd
from yt_dlp import YoutubeDL

# === 設定頻道網址 ===
channel_url = 'https://www.youtube.com/playlist?list=PLLu2ukn_7nTnak5XCmltjrLNjsRLMgS1B'

# === 設定 CSV 檔案名稱 ===
src_dir = os.path.dirname(os.path.abspath(__file__))
csv_file = os.path.join(src_dir, 'ayano_list.csv')

# === yt-dlp 參數 ===
ydl_opts = {
    'quiet': True,
    'extract_flat': True,
    'skip_download': True,
    'dump_single_json': True,
}

# === 取得頻道影片清單 ===
with YoutubeDL(ydl_opts) as ydl:
    channel_info = ydl.extract_info(channel_url, download=False)

videos = channel_info.get('entries', [])

# === 建立 DataFrame ===
video_list = []
index = 0
for video in videos:
    # 過濾掉時間超過1小時的影片或live影片
    duration = video.get('duration')
    if duration is None or duration > 36000:
        continue

    index += 1
    video_id = video.get('id')
    video_title = video.get("title")
    video_list.append({
        'id': video_id,
        'idx': index,
        'title': video_title,
        'url': f"https://www.youtube.com/watch?v={video_id}",
        'date': video.get('upload_date', 'unknown')
    })

df = pd.DataFrame(video_list)

# === 儲存到 CSV 檔案 ===
df.to_csv(csv_file, index=False)
print(f"📌 已建立 {csv_file}，共儲存 {len(df)} 部影片。")
