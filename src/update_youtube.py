import os
import pandas as pd
import time
import ssl
import re

from lib.mytube import get_video_list, download_video_file, convert_script, get_upload_date
from lib.mylog import setup_logger
from verify_chinese import detect_chinese

# 設定 logger
logger = setup_logger('youtube_update')

# === 設定目錄路徑 ===
src_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.join(src_dir, '../')

# under base_dir
pages_dir = os.path.join(base_dir, 'pages/')
summary_dir = os.path.join(base_dir, 'summary/')  
readme_file = os.path.join(base_dir, 'README.md')  

# under src_dir
subtitle_dir = os.path.join(src_dir, 'subtitle/')
video_dir = os.path.join(src_dir, 'video/')
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


def download_video(df):  # Changed from download_audio
    # 確保 video_dir 存在
    os.makedirs(video_dir, exist_ok=True)
        
    # 計數器
    download_count = 0
    max_downloads = 2
    
    # 從最後一筆往前處理
    lst = reversed(df.index)
    for idx in lst:
        if download_count >= max_downloads:
            logger.info(f"download_video: 已達到最大下載數量 ({max_downloads})")
            break
            
        video_id = df.loc[idx, 'id']
        
        # 檢查兩種可能的影片格式
        video_file_webm = f"{video_dir}\\{video_id}.webm"
        video_file_mp4 = f"{video_dir}\\{video_id}.mp4"
        script_file = f"{subtitle_dir}/{video_id}.txt"
        
        # 檢查是否有字幕檔案，若有則刪除影片檔案
        if os.path.exists(script_file):
            for video_file in [video_file_webm, video_file_mp4]:
                if os.path.exists(video_file):
                    os.remove(video_file)
                    logger.info(f"download_video: 刪除影片：{video_file}")
            continue

        # 檢查檔案是否已存在（任一格式）
        if os.path.exists(video_file_webm) or os.path.exists(video_file_mp4):
            continue
            
        logger.info(f"download_video: 下載影片中：{idx}:{video_id}")
        success = False
        try:
            download_video_file(video_id, video_dir)
            download_count += 1
            success = True                                                   
        except Exception as e:
            logger.error(f"download_video: 下載失敗 {idx}:{video_id}: {str(e)}")
            exit(0)
          
    return df

def convert_subtitle():
    # 確保 summary 目錄存在
    os.makedirs(subtitle_dir, exist_ok=True)
    
    # 取得所有 subtitle 目錄下的 webm 和 mp4 檔案
    video_files = [f for f in os.listdir(video_dir) if f.endswith(('.webm', '.mp4'))]
    
    # 計數器
    processed_count = 0
    
    for video_file in video_files:
        # 取得檔名（不含副檔名）
        fname = os.path.splitext(video_file)[0]
        
        # 檢查對應的 summary 檔案是否存在
        script_path = f"{subtitle_dir}{fname}.txt"
        video_path = f"{video_dir}{video_file}"
        
        if not os.path.exists(script_path):
            try:
                convert_script(video_path, script_path)
                processed_count += 1
                
            except Exception as e:
                logger.error(f"convert_subtitle: 字幕產生失敗 {fname}: {str(e)}")
                continue
    
    if processed_count > 0:
        logger.info(f"convert_subtitle: 完成 {processed_count} 個檔案的字幕")
    else:
        logger.info("convert_subtitle: 沒有需要處理的檔案")

def summerize_script():
    # 確保 summary 目錄存在
    os.makedirs(summary_dir, exist_ok=True)
    
    # 取得所有 subtitle 目錄下的 txt 檔案
    script_files = [f for f in os.listdir(subtitle_dir) if f.endswith('.txt')]
    
    # 計數器
    processed_count = 0
    
    for script_file in script_files:
        # 取得檔名（不含副檔名）
        fname = os.path.splitext(script_file)[0]
        
        # 檢查對應的 summary 檔案是否存在
        summary_file = f"{summary_dir}{fname}.md"
        script_path = f"{subtitle_dir}{script_file}"
        
        if not os.path.exists(summary_file):
            logger.info(f"處理摘要中：{fname}")
            
            try:
                # 讀取字幕檔案
                with open(script_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                try_count = 0
                threshold = 0.3
                while True:
                    # 產生摘要
                    summary_text = get_summary(content)
                    chinese_ratio = detect_chinese(summary_text)
                    if chinese_ratio > threshold:
                        break
                    try_count += 1
                    if try_count > 10:
                        raise Exception(f"summerize_script: 無法產生中文摘要")
                    else:
                        logger.warning(f"summerize_script: 中文比例過低 ({chinese_ratio:.2f}):第{try_count}次")
            
                # 寫入摘要檔案
                with open(summary_file, 'w', encoding='utf-8') as f:
                    f.write(summary_text)
                
                logger.info(f"summerize_script: 摘要已儲存：{summary_file}")
                processed_count += 1
                
            except Exception as e:
                logger.error(f"summerize_script: 摘要產生失敗 {fname}: {str(e)}")
                continue
    
    if processed_count > 0:
        logger.info(f"summerize_script: 完成 {processed_count} 個檔案的摘要")
    else:
        logger.info("summerize_script: 沒有需要處理的檔案")

def make_doc(filename: str, video_list: list, reverse):
    """
    將影片清單製作成文件
    Args:
        filename (str): 輸出的文件名稱
        video_list (list): 影片資料列表
    """

    # 檔案模板
    details_template = """<details>
<summary>{idx}. {date}{title}</summary><br>

<a href="https://www.youtube.com/watch?v={id}" target="_blank">
    <img src="https://img.youtube.com/vi/{id}/maxresdefault.jpg" 
        alt="[Youtube]" width="200">
</a>{transcript_url}

# {title}

{summary_file}

---

</details>

"""

    try:
        # 確保目標目錄存在
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # 依 idx 由大到小排序
        sorted_videos = sorted(video_list, key=lambda x: x['idx'], reverse=reverse)
        
        with open(filename, 'w', encoding='utf-8') as f:
            for video in sorted_videos:
                # 處理日期格式
                id = video['id']
                date_str = f"[{video['date']}] " if video['date'] != 'unknown' else ""
                
                # 檢查是否有摘要檔案
                summary_path = f"{summary_dir}{id}.md"
                summary_content = ""
                if os.path.exists(summary_path):
                    with open(summary_path, 'r', encoding='utf-8') as sf:
                        summary_content = sf.read()
                
                # Remove text enclosed in 【】from title
                title = re.sub(r'【[^】]*】', '', video['title']).strip()             

                transcript_url = ""
                transcript_path = f"{transcript_dir}{id}.md"
                if os.path.exists(transcript_path):
                    transcript_url = f"\n\n[Transcript](../transcript/{id}.md)"
            
                # 填入模板
                content = details_template.format(
                    idx=video['idx'],
                    date=date_str,
                    title=title,
                    id=id,
                    summary_file=summary_content,
                    transcript_url=transcript_url
                )
                
                f.write(content)
                
    except Exception as e:
        logger.error(f"製作文件失敗 {filename}: {str(e)}")

def create_readme_doc(max_idx, latest_date, batch_size, reverse):
    content = f"""# Bonnie Blockchain ({latest_date})

---

"""
    end_batch = (max_idx - 1) // batch_size  # 最大的批次編號
    if reverse:
        # 反向計算範圍
        rng = range(end_batch, -1, -1)
    else:
        rng = range(0, end_batch+1)
    
    # 從大到小遍歷
    for i in rng:
        start_idx = i * batch_size + 1
        end_idx = min((i + 1) * batch_size, max_idx)
        content += f"- [{start_idx:04d}~{end_idx:04d}](pages/{i:02d}-index.md)\n"

    content += "\n---\n"

    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(content)

def create_doc(df, batch_size, reverse):
    """
    從 DataFrame 中分批取出影片資料，並呼叫 make_doc 製作文件
    每批次處理 idx 範圍內的所有資料（如1-100內的所有存在的idx）
    檔名格式為 01-index.md, 02-index.md, ...
    """
    try:
        # 取得最大的 idx
        max_idx = df['idx'].max()
        
        # 計算需要產生幾個檔案
        num_batches = (max_idx + batch_size - 1) // batch_size  # 向上取整
        
        # 處理每一批次
        for batch_num in range(num_batches):
            # 計算當前批次的 idx 範圍
            start_idx = batch_num * batch_size + 1
            end_idx = min((batch_num + 1) * batch_size, max_idx)
            
            # 取出符合 idx 範圍的資料
            batch_df = df[df['idx'].between(start_idx, end_idx)]
            
            # 如果這個範圍有資料才處理
            if not batch_df.empty:
                # 產生檔名 (01-index.md, 02-index.md, ...)
                filename = f"{pages_dir}/{batch_num:02d}-index.md"
                
                # 將 DataFrame 轉換成字典列表
                video_list = batch_df.to_dict('records')
                
                logger.info(f"處理文件：{filename} (idx: {start_idx}-{end_idx}, 實際筆數: {len(video_list)})")
                
                # 呼叫 make_doc 製作文件
                make_doc(filename, video_list, reverse)
                
                logger.info(f"完成文件：{filename}")
        
        logger.info(f"總共產生了 {num_batches} 個文件")

        # 取得最新日期
        # latest_date = df['date'].iloc[-1]
        # create_readme_doc(max_idx, latest_date, batch_size, reverse)
        
    except Exception as e:
        logger.error(f"處理文件時發生錯誤：{str(e)}")

if __name__ == '__main__':
    logger.info("開始執行更新程序")
    df, new_df = update_list()
    exit(0)
    update_date(df)
    download_video(df)  # Changed from download_audio
    convert_subtitle()
    summerize_script()
    create_doc(df, 50, True)
    email_notify(new_df)
    logger.info("更新程序完成")
