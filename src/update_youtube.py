import os
import pandas as pd
import time
import ssl
import re
import glob
import shutil

from lib.mytube import get_video_list, download_mp3_file, transcribe_audio
from lib.mylog import setup_logger

# 設定 logger
logger = setup_logger('youtube_update')

# === 設定目錄路徑 ===
src_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.join(src_dir, '../')

# under base_dir
srt_dir = os.path.join(base_dir, 'srt/')
mp3_dir = os.path.join(base_dir, 'mp3/')
notes_dir = os.path.join(base_dir, 'notes/')
readme_file = os.path.join(base_dir, 'README.md')  

# google dir
google_dir = "J:/我的雲端硬碟/AUDIO/TBS-News/"

# under src_dir
csv_file = os.path.join(src_dir, 'video_list.csv')


# === 設定頻道網址 ===
channel_url = 'https://www.youtube.com/playlist?list=PLhoNlZaJqDLaPgn1NqC9FxMPnlkemRpyr'

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

def update_list():
    # === yt-dlp 參數設定 ===
    videos = get_video_list(channel_url)
    # === 建立新影片的DataFrame ===
    new_videos = []
    for video in videos:
        # 過濾掉時間超過1小時的影片或live影片
        duration = video.get('duration')
        if duration is None or duration > 3600:
            continue

        video_id = video.get('id')
        video_title = video.get('title')
        new_videos.append({
            'id': video_id,
            'title': rename_title(video_title),
            'url': f"https://www.youtube.com/watch?v={video_id}",
            'date': video.get('upload_date', 'unknown')
        })

    new_df = pd.DataFrame(new_videos).sort_values(by='title', ascending=True)

    # === 讀取現有的CSV檔案 ===
    try:
        existing_df = pd.read_csv(csv_file)
        last_idx = existing_df['idx'].max()
    except FileNotFoundError:
        existing_df = pd.DataFrame(columns=['idx', 'id', 'title', 'url', 'date'])
        last_idx = 0

    # === 比較並合併新舊資料 ===
    new_videos_mask = ~new_df['id'].isin(existing_df['id'])
    if new_videos_mask.any():
        # 取得新影片並反轉順序
        new_videos_df = new_df[new_videos_mask].copy()
        # 為新影片加入遞增的 idx
        new_videos_count = len(new_videos_df)
        new_videos_df['idx'] = range(last_idx + 1, last_idx + new_videos_count + 1)
        
        # 合併新舊資料
        combined_df = pd.concat([existing_df, new_videos_df], ignore_index=True)
        
        # 儲存更新後的資料
        combined_df.to_csv(csv_file, index=False)
        logger.info(f"已更新 {new_videos_mask.sum()} 部新影片")
        return combined_df, new_videos_df
    else:
        logger.info("沒有新影片")
        # new_df = existing_df.tail(1)
        new_df = pd.DataFrame()
        return existing_df, new_df

def download_mp3(df):  # Changed from download_audio
    # 確保 video_dir 存在
    os.makedirs(mp3_dir, exist_ok=True)
        
    # 計數器
    download_count = 0
    max_downloads = 2
    
    # 從最後一筆往前處理
    lst = reversed(df.index)
    for idx in lst:
        if download_count >= max_downloads:
            logger.info(f"download_mp3: 已達到最大下載數量 ({max_downloads})")
            break
            
        mp3_title = df.loc[idx, 'title']
        video_id = df.loc[idx, 'id']
        
        # 檢查兩種可能的影片格式
        mp3_file = f"{mp3_dir}\\{mp3_title}.mp3"
        
        # 檢查檔案是否已存在（任一格式）
        if os.path.exists(mp3_file):
            continue
            
        logger.info(f"download_mp3: 下載影片中：{idx}:{mp3_file}")
        success = False
        try:
            download_mp3_file(video_id, mp3_file)
            download_count += 1
            success = True                                                   
        except Exception as e:
            logger.error(f"download_mp3: 下載失敗 {idx}:{video_id},{mp3_file}: {str(e)}")
            exit(0)
          
    return df

def transcribe_srt():
    """
    將 MP3 檔案轉換為 SRT 字幕檔，一次最多處理 3 個檔案
    """
    # 確保 summary 目錄存在
    os.makedirs(srt_dir, exist_ok=True)
    
    # 取得所有 srt_dir 目錄下的 mp3 檔案
    mp3_files = [f for f in os.listdir(mp3_dir) if f.endswith('.mp3')]
    
    # 計數器
    processed_count = 0
    max_process = 3  # 設定最大處理數量為 3
    
    for mp3_file_name in mp3_files:
        # 檢查是否達到最大處理數量
        if processed_count >= max_process:
            logger.info(f"已達到最大處理數量 ({max_process})")
            break
            
        # 取得檔名（不含副檔名）
        fname = os.path.splitext(mp3_file_name)[0]
        
        # 檢查對應的 summary 檔案是否存在
        srt_file = f"{srt_dir}{fname}.srt"
        mp3_file = f"{mp3_dir}{mp3_file_name}"
        
        if not os.path.exists(srt_file):
            try:
                transcribe_audio(mp3_file, srt_file)
                processed_count += 1
                
            except Exception as e:
                logger.error(f"transcribe_srt: 字幕產生失敗 {fname}: {str(e)}")
                continue
    
    if processed_count > 0:
        logger.info(f"transcribe_srt: 完成 {processed_count} 個檔案的字幕")
    else:
        logger.info("transcribe_srt: 沒有需要處理的檔案")

def write_notes(df):
    """
    為每個影片建立 notes 文件，內容為 YouTube URL
    如果文件已存在則跳過
    """
    # 確保 notes 目錄存在
    os.makedirs(notes_dir, exist_ok=True)
    
    # 計數器
    created_count = 0
    
    # 處理每個影片
    for _, row in df.iterrows():
        title = row['title']
        url = row['url']
        
        # 建立 notes 文件路徑
        notes_file = os.path.join(notes_dir, f"{title}.Notes.txt")
        
        # 如果文件不存在，則建立
        if not os.path.exists(notes_file):
            try:
                with open(notes_file, 'w', encoding='utf-8') as f:
                    f.write(url)
                created_count += 1
                logger.info(f"已建立筆記文件：{notes_file}")
            except Exception as e:
                logger.error(f"建立筆記文件失敗 {notes_file}: {str(e)}")
    
    if created_count > 0:
        logger.info(f"write_notes: 完成 {created_count} 個筆記文件")
    else:
        logger.info("write_notes: 沒有需要建立的筆記文件")

def copy_files():
    """
    將 mp3、notes、srt 目錄下的檔案複製到 google_dir
    如果目標檔案已存在則跳過
    """    
    # 確保目標目錄存在
    os.makedirs(google_dir, exist_ok=True)
    
    # 計數器
    copied_count = 0
    
    # 複製函數
    def copy_if_not_exists(src_file, dst_dir):
        nonlocal copied_count
        filename = os.path.basename(src_file)
        dst_file = os.path.join(dst_dir, filename)
        
        if not os.path.exists(dst_file):
            try:
                shutil.copy2(src_file, dst_file)
                copied_count += 1
                logger.info(f"已複製：{filename}")
            except Exception as e:
                logger.error(f"複製失敗 {filename}: {str(e)}")
    
    # 複製 mp3 檔案
    mp3_files = glob.glob(os.path.join(mp3_dir, "*.mp3"))
    for mp3_file in mp3_files:
        copy_if_not_exists(mp3_file, google_dir)
    
    # 複製 notes 檔案
    notes_files = glob.glob(os.path.join(notes_dir, "*.txt"))
    for notes_file in notes_files:
        copy_if_not_exists(notes_file, google_dir)
    
    # 複製 srt 檔案
    srt_files = glob.glob(os.path.join(srt_dir, "*.srt"))
    for srt_file in srt_files:
        copy_if_not_exists(srt_file, google_dir)
    
    if copied_count > 0:
        logger.info(f"copy_files: 完成複製 {copied_count} 個檔案")
    else:
        logger.info("copy_files: 沒有需要複製的檔案")

if __name__ == '__main__':
    logger.info("開始執行更新程序")
    df, new_df = update_list()
    write_notes(df)
    download_mp3(df)  # Changed from download_audio
    transcribe_srt()
    copy_files()
    logger.info("更新程序完成")
