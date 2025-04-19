import yt_dlp

def format_date(date):
    return f"{date[:4]}-{date[4:6]}-{date[6:]}" if date != 'unknown' else date

def get_upload_date(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        'quiet': True,  # 不顯示多餘的日誌
        'extract_flat': True  # 只提取影片資訊，不下載
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        date = info.get("upload_date", "unknown")        
        return format_date(date)


if __name__ == "__main__":
    video_id = "_YEWG7SBqC0"  # 替換成你的影片 ID
    upload_date = get_upload_date(video_id)

    if upload_date != "unknown":
        print("影片上架日期:", upload_date)
    else:
        print("無法獲取影片上架日期")
