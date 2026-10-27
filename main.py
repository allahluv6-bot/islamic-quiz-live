import os
import json
import time
import subprocess
import threading
from PIL import Image, ImageDraw, ImageFont
import pytchat

STREAM_KEY = os.environ.get("STREAM_KEY", "")
VIDEO_WIDTH = 720
VIDEO_HEIGHT = 1280
FPS = 10
DURATION_LIMIT = 21600  # Strict 6 Hours

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

def draw_rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    x1, y1, x2, y2 = xy
    draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
    draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
    draw.pieslice([x1, y1, x1 + radius * 2, y1 + radius * 2], 180, 270, fill=fill)
    draw.pieslice([x2 - radius * 2, y1, x2, y1 + radius * 2], 270, 360, fill=fill)
    draw.pieslice([x1, y2 - radius * 2, x1 + radius * 2, y2], 90, 180, fill=fill)
    draw.pieslice([x2 - radius * 2, y2 - radius * 2, x2, y2], 0, 90, fill=fill)

def draw_ui(q_data, leaderboard, ticker_msg, timer_val):
    # Dark Olive Green Aesthetic Theme Background (#132A13)
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), color="#132A13")
    draw = ImageDraw.Draw(img)

    # Top Header: AHAD Z9 LIVE (@AhadZ9)
    draw.rectangle([30, 30, 690, 130], fill="#386641")
    draw.text((50, 45), "AHAD Z9 LIVE", fill="#F2E8CF", font=font_large)
    draw.text((50, 85), "@AhadZ9 - Islamic Trivia Live", fill="#dda15e", font=font_small)
    
    # Live Leaderboard Box (Top 5)
    draw.rectangle([30, 150, 690, 330], fill="#283618", outline="#606C38", width=2)
    draw.text((50, 160), "LIVE LEADERBOARD (TOP 5)", fill="#dda15e", font=font_large)
    draw.text((50, 190), "Rank   User                        Points", fill="#a3b18a", font=font_small)
    
    sorted_lb = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)[:5]
    y_offset = 215
    for rank, (user, pts) in enumerate(sorted_lb, 1):
        draw.text((50, y_offset), f"{rank}.      @{user[:15]:<15}     {pts} pts", fill="#fefae0", font=font_small)
        y_offset += 22

    # Center Quiz Card (Question Box)
    draw.rectangle([30, 350, 690, 680], fill="#283618", outline="#606C38", width=3)
    draw.text((50, 370), f"ISLAMIC TRIVIA Q#{q_data.get('id', 1)}:", fill="#dda15e", font=font_large)
    
    q_text = str(q_data.get('question', ''))
    draw.text((50, 420), q_text, fill="#fefae0", font=font_large)

    # Countdown Timer Bar
    bar_width = int(610 * (timer_val / 30.0))
    draw.rectangle([50, 520, 660, 545], fill="#386641")
    if bar_width > 0:
        draw.rectangle([50, 520, 50 + bar_width, 545], fill="#bc6c25")
    draw.text((310, 525), f"TIME: {timer_val} SEC", fill="#fefae0", font=font_small)

    # Options A, B, C, D (Rounded Buttons Grid)
    options = q_data.get('options', ['', '', '', ''])
    opt_coords = [
        (50, 565, 345, 625),  # A
        (375, 565, 670, 625), # B
        (50, 640, 345, 700),  # C
        (375, 640, 670, 700)  # D
    ]
    for i, box in enumerate(opt_coords):
        if i < len(options):
            draw_rounded_rect(draw, box, radius=10, fill="#386641", outline="#dda15e", width=2)
            draw.text((box[0] + 15, box[1] + 18), str(options[i]), fill="#fefae0", font=font_small)

    # Bottom Stream Area: Engagement Prompt & Winner Ticker
    draw.rectangle([30, 710, 690, 830], fill="#283618", outline="#606C38", width=2)
    draw.text((50, 730), "+10 Points for Correct Jawab! Type A, B, C, or D in chat!", fill="#dda15e", font=font_small)
    draw.text((50, 780), f"LAST CORRECT JAWAB: {ticker_msg}", fill="#fefae0", font=font_small)

    return img

def main():
    if not STREAM_KEY:
        print("Error: STREAM_KEY secret missing!")
        return

    questions = load_json("questions.json", [])
    if not questions:
        print("Error: questions.json is empty!")
        return

    # FFmpeg command configured for Vertical 9:16 Stream with silent audio track for YouTube compliance
    ffmpeg_cmd = [
        'ffmpeg', '-y', 
        '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-pix_fmt', 'rgb24', '-s', f'{VIDEO_WIDTH}x{VIDEO_HEIGHT}',
        '-r', str(FPS), '-i', '-',
        '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
        '-c:v', 'libx264', '-preset', 'ultrafast',
        '-pix_fmt', 'yuv420p', '-b:v', '800k',
        '-c:a', 'aac', '-b:a', '64k',
        '-flvflags', 'no_duration_filesize',
        '-f', 'flv', f'rtmp://a.rtmp.youtube.com/live2/{STREAM_KEY}'
    ]
    
    process = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
    start_time = time.time()
    
    chat = None
    try:
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
                except Exception as e:
                    pass

            for _ in range(FPS):
                frame_img = draw_ui(current_q, leaderboard, ticker_msg, timer)
                try:
                    process.stdin.write(frame_img.tobytes())
                    process.stdin.flush()
                except BrokenPipeError:
                    print("FFmpeg connection closed. Reconnecting...")
                    break
                time.sleep(1.0 / FPS)

        q_index += 1

    try:
        process.stdin.close()
    except:
        pass
    process.wait()

if __name__ == "__main__":
    main()
    
