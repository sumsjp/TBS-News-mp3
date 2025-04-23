import os
import pandas as pd
import time
import ssl
import re
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
readme_file = os.path.join(base_dir, 'README.md')  

# google dir
google_dir = "E:/My Drive/AUDIO/TBS-News/"

# under src_dir
csv_file = os.path.join(src_dir, 'video_list.csv')


# === 設定頻道網址 ===
channel_url = 'https://www.youtube.com/playlist?list=PLhoNlZaJqDLaPgn1NqC9FxMPnlkemRpyr'


def update_list():
    # === yt-dlp 參數設定 ===
    videos = get_video_list(channel_url)
    # === 建立新影片的DataFrame ===
    new_videos = []
    for video in reversed(videos):
        video_id = video.get('id')
        new_videos.append({
            'id': video_id,
            'title': video.get('title'),
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


def update_date(df):
    """
    Update unknown or missing upload dates in the DataFrame
    - Processes from the latest entries backwards
    - Updates entries where date is 'unknown'
    - Limits to maximum 10 API calls
    - Saves updated data back to CSV
    """
    if df.empty:
        return df
        
    update_count = 0
    max_updates = 10
    
    # Process from newest to oldest
    for idx in reversed(df.index):
        if update_count >= max_updates:
            logger.info(f"已達到最大更新數量 ({max_updates})")
            break
            
        video_id = df.loc[idx, 'id']
        current_date = df.loc[idx, 'date']
        
        if current_date == 'unknown':
            logger.info(f"更新日期中：{idx}:{video_id}")
            try:
                new_date = get_upload_date(video_id)
                if new_date != 'unknown':
                    df.loc[idx, 'date'] = new_date
                    update_count += 1
                    logger.info(f"更新成功：{idx}:{video_id} -> {new_date}")
                else:
                    logger.warning(f"無法取得日期：{idx}:{video_id}")
            except Exception as e:
                logger.error(f"更新日期失敗 {idx}:{video_id}: {str(e)}")
                continue
    
    if update_count > 0:
        # Save updates back to CSV
        df.to_csv(csv_file, index=False)
        logger.info(f"完成 {update_count} 個影片的日期更新")
    else:
        logger.info("沒有需要更新的日期")
        
    return df


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
    將 mp3 檔案轉換為 srt 字幕檔
    每次執行最多處理 max_transcriptions 個檔案
    """
    # 確保 summary 目錄存在
    os.makedirs(srt_dir, exist_ok=True)
    
    # 取得所有 srt_dir 目錄下的 mp3 檔案
    mp3_files = [f for f in os.listdir(mp3_dir) if f.endswith('.mp3')]
    
    # 計數器
    processed_count = 0
    max_transcriptions = 3  # 設定最大轉換次數
    
    for mp3_file_name in mp3_files:
        # 檢查是否達到最大轉換次數
        if processed_count >= max_transcriptions:
            logger.info(f"已達到最大轉換次數 ({max_transcriptions})")
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
                logger.info(f"已完成 {processed_count}/{max_transcriptions} 個轉換")
                
            except Exception as e:
                logger.error(f"transcribe_srt: 字幕產生失敗 {fname}: {str(e)}")
                continue
    
    if processed_count > 0:
        logger.info(f"transcribe_srt: 完成 {processed_count} 個檔案的字幕")
    else:
        logger.info("transcribe_srt: 沒有需要處理的檔案")

def copy_files():
    # 將 mp3_dir 和 srt_dir 下的所有檔案複製到 google_dir
    for src_dir in [mp3_dir, srt_dir]:
        for file_name in os.listdir(src_dir):
            src_file = os.path.join(src_dir, file_name)
            dst_file = os.path.join(google_dir, file_name)
            if not os.path.exists(dst_file):
                shutil.copyfile(src_file, dst_file)  # 改用 copyfile
                logger.info(f"已複製檔案：{file_name} 到 {google_dir}")

if __name__ == '__main__':
    logger.info("開始執行更新程序")
    df, new_df = update_list()
    download_mp3(df)  # Changed from download_audio
    transcribe_srt()
    copy_files()
    logger.info("更新程序完成")
