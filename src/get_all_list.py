import os
import re
import pandas as pd
from yt_dlp import YoutubeDL

def rename_title(title):
    # Extract the time of day (朝/昼/夜)
    time_of_day = ""
    if "朝の" in title:
        time_of_day = "朝"
    elif "昼の" in title:
        time_of_day = "昼"
    elif "夜の" in title:
        time_of_day = "夜"
    
    # Extract the date (月日)
    date_match = re.search(r'（(\d+)月(\d+)日）', title)
    if date_match:
        month = date_match.group(1).zfill(2)
        day = date_match.group(2).zfill(2)
        formatted_date = f"{month}-{day}"
        
        # Construct the new title
        return f"TBS_News_{formatted_date}_{time_of_day}"
    
    # Return original title if pattern doesn't match
    return title

# === 設定頻道網址 ===
channel_url = 'https://www.youtube.com/playlist?list=PLhoNlZaJqDLaPgn1NqC9FxMPnlkemRpyr'

# === 設定 CSV 檔案名稱 ===
csv_file = './video_list.csv'

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
for video in videos:
    # 過濾掉時間超過1小時的影片或live影片
    duration = video.get('duration')
    if duration is None or duration > 3600:
        continue

    video_id = video.get('id')
    video_title = video.get('title')
    video_list.append({
        'id': video_id,
        'title': rename_title(video_title),
        'url': f"https://www.youtube.com/watch?v={video_id}",
        'date': video.get('upload_date', 'unknown')
    })

df = pd.DataFrame(video_list)

# === 若日期存在，轉換格式 ===
def format_date(date):
    return f"{date[:4]}-{date[4:6]}-{date[6:]}" if date != 'unknown' else date

df['date'] = df['date'].apply(format_date)
#sort by title
df = df.sort_values(by='title', ascending=True)
df = df.reset_index(drop=True)

# === 加入從1開始的 idx 欄位 ===
df.insert(0, 'idx', df.index + 1)

# === 儲存到 CSV 檔案 ===
df.to_csv(csv_file, index=False)
print(f"📌 已建立 {csv_file}，共儲存 {len(df)} 部影片。")
