import os
import json
import time
import subprocess
import threading
from PIL import Image, ImageDraw, ImageFont
import pytchat
import pyttsx3

STREAM_KEY = os.environ.get("STREAM_KEY", "")
VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
FPS = 30
DURATION_LIMIT = 21600  # Strict 6 Hours

def speak_text(text):
    try:
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print("TTS Audio warning:", e)

try:
    font_large = ImageFont.load_default()
    font_small = ImageFont.load_default()
except:
    font_large = None
    font_small = None

def load_json(filename, default):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except:
                return default
    return default

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def draw_ui(q_data, leaderboard, ticker_msg, timer_val):
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), color="#132A13")
    draw = ImageDraw.Draw(img)

    # Top Header
    draw.rectangle([30, 30, 1250, 100], fill="#386641")
    draw.text((50, 45), "AHAD Z9 LIVE (@AhadZ9) - Islamic Trivia Live", fill="#F2E8CF", font=font_large)
    
    # Leaderboard (Top 5)
    sorted_lb = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)[:5]
    draw.rectangle([880, 110, 1250, 320], fill="#283618", outline="#606C38", width=2)
    draw.text((900, 120), "Live Leaderboard (Top 5)", fill="#dda15e", font=font_large)
    
    y_offset = 155
    for rank, (user, pts) in enumerate(sorted_lb, 1):
        draw.text((900, y_offset), f"{rank}. {user}: {pts} pts", fill="#fefae0", font=font_small)
        y_offset += 30

    # Question Box
    draw.rectangle([50, 130, 850, 350], fill="#283618", outline="#606C38", width=3)
    draw.text((70, 150), f"ISLAMIC TRIVIA Q#{q_data.get('id', 1)}:", fill="#dda15e", font=font_large)
    
    q_text = str(q_data.get('question', ''))
    draw.text((70, 200), q_text, fill="#fefae0", font=font_large)

    # Options A, B, C, D
    opt_y = 260
    for opt in q_data.get('options', []):
        draw.text((70, opt_y), str(opt), fill="#a3b18a", font=font_small)
        opt_y += 25

    # Timer Bar
    bar_width = int(780 * (timer_val / 30.0))
    draw.rectangle([50, 370, 830, 390], fill="#386641")
    draw.rectangle([50, 370, 50 + max(0, bar_width), 390], fill="#bc6c25")

    # Bottom Stream Area
    draw.rectangle([30, 580, 1250, 680], fill="#283618", outline="#606C38", width=2)
    draw.text((50, 595), "+10 Points for Correct Jawab! Type A, B, C, or D in chat!", fill="#dda15e", font=font_large)
    draw.text((50, 635), f"LAST CORRECT JAWAB: {ticker_msg}", fill="#fefae0", font=font_large)

    return img

def main():
    if not STREAM_KEY:
        print("Error: STREAM_KEY secret missing!")
        return

    questions = load_json("questions.json", [])
    if not questions:
        print("Error: questions.json is empty!")
        return

    # FFmpeg command with Silent Audio Track (anullsrc) for YouTube RTMP
    ffmpeg_cmd = [
        'ffmpeg', '-y', 
        '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-pix_fmt', 'rgb24', '-s', f'{VIDEO_WIDTH}x{VIDEO_HEIGHT}',
        '-r', str(FPS), '-i', '-',
        '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
        '-c:v', 'libx264', '-preset', 'ultrafast',
        '-pix_fmt', 'yuv420p', '-b:v', '1500k',
        '-c:a', 'aac', '-b:a', '128k',
        '-flvflags', 'no_duration_filesize',
        '-f', 'flv', f'rtmp://a.rtmp.youtube.com/live2/{STREAM_KEY}'
    ]
    
    process = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
    start_time = time.time()
    
    chat = None
    try:
        # Apni YouTube live stream ki real video ID yahan daal dein
        chat = pytchat.create(video_id="YOUR_LIVE_VIDEO_ID") 
    except Exception as e:
        print("Chat monitor init warning:", e)

    q_index = 0
    ticker_msg = "Awaiting first correct jawab! 🎉"
    
    while True:
        if (time.time() - start_time) > DURATION_LIMIT:
            print("6 hours completed. Shutting down stream safely.")
            break

        current_q = questions[q_index % len(questions)]
        leaderboard = load_json("leaderboard.json", {})

        threading.Thread(target=speak_text, args=(f"Question {current_q.get('id')}: {current_q.get('question')}",)).start()

        for timer in range(30, 0, -1):
            if chat and chat.is_alive():
                try:
                    for c in chat.get().sync_items():
                        msg = c.message.strip().upper()
                        author = c.author.name
                        if msg in ["A", "B", "C", "D"]:
                            correct_ans = str(current_q.get('answer', '')).strip().upper()
                            if msg == correct_ans:
                                leaderboard[author] = leaderboard.get(author, 0) + 10
                                save_json("leaderboard.json", leaderboard)
                                ticker_msg = f"@{author} (+10 pts) 🎉"
                                threading.Thread(target=speak_text, args=(f"Correct jawab by {author}!",)).start()
                except Exception as e:
                    pass

            frame_img = draw_ui(current_q, leaderboard, ticker_msg, timer)
            try:
                process.stdin.write(frame_img.tobytes())
                process.stdin.flush()
            except BrokenPipeError:
                print("FFmpeg connection closed. Reconnecting...")
                break

            time.sleep(1)

        q_index += 1

    try:
        process.stdin.close()
    except:
        pass
    process.wait()

if __name__ == "__main__":
    main()
    
