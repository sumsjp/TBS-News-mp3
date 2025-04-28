import os
import sys
import pandas as pd
import time
import ssl
import re
import glob
import shutil

# 獲取當前文件的目錄
current_dir = os.path.dirname(os.path.abspath(__file__))
# 獲取專案根目錄（上一層目錄）
project_root = os.path.dirname(current_dir)
# 將專案根目錄加入到 Python 路徑
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.lib.mytube import download_subtitle, download_mp3_file
from src.lib.mylog import setup_logger

# 設定 logger
logger = setup_logger('ayano_update')

# === 設定目錄路徑 ===
src_dir = os.path.dirname(os.path.abspath(__file__))

# under base_dir
srt_dir = os.path.join(src_dir, 'srt/')
mp3_dir = os.path.join(src_dir, 'mp3/')
notes_dir = os.path.join(src_dir, 'notes/')

# google dir
google_dir = "J:/我的雲端硬碟/AUDIO/ayano/"

# under src_dir
csv_file = os.path.join(src_dir, 'ayano_list.csv')


# === 設定頻道網址 ===
channel_url = 'https://www.youtube.com/playlist?list=PLhoNlZaJqDLaPgn1NqC9FxMPnlkemRpyr'

def download_mp3(df):  # Changed from download_audio
    # 確保 video_dir 存在
    os.makedirs(mp3_dir, exist_ok=True)
        
    # 計數器
    download_count = 0
    max_downloads = 5
    
    # 從最後一筆往前處理
    for idx in df.index:
        if download_count >= max_downloads:
            logger.info(f"download_mp3: 已達到最大下載數量 ({max_downloads})")
            break
            
        myidx = df.loc[idx, 'idx']
        mp3_title = f"ayano_{myidx:03d}"
        video_id = df.loc[idx, 'id']
        
        # 設定檔案路徑
        mp3_file = os.path.join(mp3_dir, f"{mp3_title}.mp3")
        tmp_file = os.path.join(mp3_dir, f"tmp.mp3")
        
        # 如果正式檔案已存在，跳過
        if os.path.exists(mp3_file):
            continue
            
        # 清理可能存在的臨時檔案
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception as e:
                logger.error(f"download_mp3: 清理臨時檔案失敗 {tmp_file}: {str(e)}")
                continue
            
        logger.info(f"download_mp3: 下載影片中：{idx}:{mp3_title}")
        try:
            # 下載到臨時檔案
            success = download_mp3_file(video_id, tmp_file)
            if success and os.path.exists(tmp_file):
                # 重新命名為正式檔案
                os.rename(tmp_file, mp3_file)
                download_count += 1
                logger.info(f"download_mp3: 完成下載：{mp3_title}")
                # 每次下載後暫停 5 秒
                time.sleep(5)
            else:
                raise Exception("下載失敗或檔案不存在")
                
        except Exception as e:
            logger.error(f"download_mp3: 下載失敗 {idx}:{video_id},{mp3_title}: {str(e)}")
            # 清理失敗的臨時檔案
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except:
                    pass
            return df
          
    return df

def download_srt(df):
    """
    下載 YouTube 影片的日文字幕（如果有的話）
    一次最多處理 3 個檔案
    使用臨時檔案避免下載中斷造成的問題
    """
    # 確保 srt_dir 存在
    os.makedirs(srt_dir, exist_ok=True)
    
    # 計數器
    processed_count = 0
    max_process = 5  # 設定最大處理數量為 3
    
    # 從最後一筆往前處理
    for idx in df.index:
        # 檢查是否達到最大處理數量
        if processed_count >= max_process:
            logger.info(f"download_srt: 已達到最大處理數量 ({max_process})")
            break
            
        # 取得檔名和影片ID
        myidx = df.loc[idx, 'idx']
        title = f"ayano_{myidx:03d}"
        video_id = df.loc[idx, 'id']
        
        # 設定檔案路徑
        srt_file = os.path.join(srt_dir, f"{title}.srt")
        
        # 如果正式檔案已存在，跳過
        if os.path.exists(srt_file):
            continue
                        
        logger.info(f"download_srt: 下載字幕中：{title}")
        try:
            # 使用新的 download_subtitle 函數
            success = download_subtitle(video_id, srt_file, ['ja'])
            
            if success and os.path.exists(srt_file):
                # 重新命名為正式檔案
                processed_count += 1
                logger.info(f"download_srt: 完成下載：{srt_file}")
                # 每次下載後暫停 5 秒
                time.sleep(5)
            else:
                logger.warning(f"download_srt: 影片沒有日文字幕：{title}")
                
        except Exception as e:
            logger.error(f"download_srt: 字幕下載失敗 {title}: {str(e)}")
            continue
    
    # 輸出處理結果
    if processed_count > 0:
        logger.info(f"download_srt: 完成下載 {processed_count} 個檔案")
    else:
        logger.info("download_srt: 沒有需要處理的檔案")

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
    for index, row in df.iterrows():
        title = f'ayano_{index:03d}'
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

def copy_files(df):
    """
    將 mp3、notes、srt 檔案複製到 google_dir
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
    
    # 複製所有檔案
    for idx in df.index:
        myidx = df.loc[idx, 'idx']
        title = f"ayano_{myidx:03d}"
        
        # 複製 mp3
        mp3_file = os.path.join(mp3_dir, f"{title}.mp3")
        if os.path.exists(mp3_file):
            copy_if_not_exists(mp3_file, google_dir)
            
        # 複製 notes
        notes_file = os.path.join(notes_dir, f"{title}.Notes.txt")
        if os.path.exists(notes_file):
            copy_if_not_exists(notes_file, google_dir)
            
        # 複製 srt
        srt_file = os.path.join(srt_dir, f"{title}.srt")
        if os.path.exists(srt_file):
            copy_if_not_exists(srt_file, google_dir)
    
    # 輸出處理結果
    if copied_count > 0:
        logger.info(f"copy_files: 完成複製 {copied_count} 個檔案")
    else:
        logger.info("copy_files: 沒有需要處理的檔案")

if __name__ == '__main__':
    logger.info("開始執行更新程序")
    df = pd.read_csv(csv_file)
    write_notes(df)
    download_mp3(df)  # Changed from download_audio
    download_srt(df)  # Changed from download_audio
    copy_files(df)
    logger.info("更新程序完成")
