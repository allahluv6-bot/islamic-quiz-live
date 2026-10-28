import os
import json
import time
import subprocess
import threading
from PIL import Image, ImageDraw, ImageFont
import pytchat
import pyttsx3

STREAM_KEY = os.environ.get("STREAM_KEY", "")
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 15
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

def draw_rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    x1, y1, x2, y2 = xy
    draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
    draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
    draw.pieslice([x1, y1, x1 + radius * 2, y1 + radius * 2], 180, 270, fill=fill)
    draw.pieslice([x2 - radius * 2, y1, x2, y1 + radius * 2], 270, 360, fill=fill)
    draw.pieslice([x1, y2 - radius * 2, x1 + radius * 2, y2], 90, 180, fill=fill)
    draw.pieslice([x2 - radius * 2, y2 - radius * 2, x2, y2], 0, 90, fill=fill)

def draw_ui(q_data, leaderboard, ticker_msg, timer_val, recent_chats):
    # Dark Olive Green Background (#132A13)[span_9](start_span)[span_9](end_span)
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), color="#132A13")
    draw = ImageDraw.Draw(img)

    # 1. Top-Left Branding (AHAD Z9 LIVE, No DP)[span_10](start_span)[span_10](end_span)
    draw.rectangle([40, 40, 1040, 190], fill="#386641", outline="#606C38", width=3)
    draw.text((70, 60), "AHAD Z9 LIVE", fill="#F2E8CF", font=font_large)
    draw.text((70, 110), "@AhadZ9", fill="#dda15e", font=font_small)
    draw.text((70, 145), "CURRENT QUIZ: ISLAMIC TRIVIA", fill="#fefae0", font=font_small)

    # 2. Top-Right Live Leaderboard (Top 5)[span_11](start_span)[span_11](end_span)
    draw.rectangle([40, 210, 1040, 490], fill="#283618", outline="#606C38", width=3)
    draw.text((70, 225), "LIVE LEADERBOARD (TOP 5)", fill="#dda15e", font=font_large)
    draw.text((70, 265), "Rank   User                                           Points", fill="#a3b18a", font=font_small)
    
    sorted_lb = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)[:5]
    y_offset = 300
    for rank, (user, pts) in enumerate(sorted_lb, 1):
        draw.text((70, y_offset), f"{rank}.        @{user[:20]:<20}                {pts} pts", fill="#fefae0", font=font_small)
        y_offset += 32

    # 3. Center Quiz Card (Question Box)[span_12](start_span)[span_12](end_span)
    draw.rectangle([40, 510, 1040, 1060], fill="#283618", outline="#606C38", width=4)
    draw.text((70, 535), f"ISLAMIC TRIVIA Q#{q_data.get('id', 1)}:", fill="#dda15e", font=font_large)
    
    q_text = str(q_data.get('question', ''))
    draw.text((70, 600), q_text, fill="#fefae0", font=font_large)

    # 4. 15-Second Countdown Timer Bar[span_13](start_span)[span_13](end_span)
    bar_width = int(900 * (timer_val / 15.0))
    draw.rectangle([90, 830, 990, 875], fill="#386641")
    if bar_width > 0:
        draw.rectangle([90, 830, 90 + bar_width, 875], fill="#bc6c25")
    draw.text((450, 840), f"TIME: {timer_val} SEC", fill="#fefae0", font=font_small)

    # 5. Four Answer Options (2x2 Grid)[span_14](start_span)[span_14](end_span)
    options = q_data.get('options', ['', '', '', ''])
    opt_coords = [
        (90, 905, 510, 995),   # A
        (570, 905, 990, 995),  # B
        (90, 1015, 510, 1105), # C
        (570, 1015, 990, 1105) # D
    ]
    for i, box in enumerate(opt_coords):
        if i < len(options):
            draw_rounded_rect(draw, box, radius=15, fill="#386641", outline="#dda15e", width=3)
            draw.text((box[0] + 25, box[1] + 22), str(options[i]), fill="#fefae0", font=font_small)

    # 6. Fixed Instruction Line[span_15](start_span)[span_15](end_span)
    draw.rectangle([40, 1085, 1040, 1200], fill="#283618", outline="#606C38", width=3)
    draw.text((70, 1110), "+10 Points for Correct Answer! Type A, B, C, or D in chat!", fill="#dda15e", font=font_large)

    # 7. Live Announcement Strip[span_16](start_span)[span_16](end_span)
    draw.text((70, 1160), f"🔊 LAST CORRECT JAWAB: {ticker_msg}", fill="#fefae0", font=font_small)

    # 8. Live Chat Area (Bottom Section)[span_17](start_span)[span_17](end_span)
    draw.rectangle([40, 1220, 1040, 1860], fill="#1b2816", outline="#606C38", width=3)
    draw.text((70, 1240), "Live Chat Messages:", fill="#dda15e", font=font_small)
    
    chat_y = 1285
    for c_author, c_msg in recent_chats[-7:]:
        draw.text((70, chat_y), f"@{c_author}: {c_msg}", fill="#fefae0", font=font_small)
        chat_y += 38

    return img

def main():
    if not STREAM_KEY:
        print("Error: STREAM_KEY secret missing!")
        return

    questions = load_json("questions.json", [])
    if not questions:
        print("Error: questions.json is empty!")
        return

    # FFmpeg command optimized for 1080x1920 Full HD & YouTube compliance
    ffmpeg_cmd = [
        'ffmpeg', '-y', 
        '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-pix_fmt', 'rgb24', '-s', f'{VIDEO_WIDTH}x{VIDEO_HEIGHT}',
        '-r', str(FPS), '-i', '-',
        '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
        '-c:v', 'libx264', '-preset', 'ultrafast',
        '-pix_fmt', 'yuv420p', '-b:v', '2500k',
        '-g', str(FPS * 2),  # Keyframe every 2 seconds
        '-c:a', 'aac', '-b:a', '128k',
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
    recent_chats = [("System", "Welcome to AhadZ9 Live Quiz!")]
    
    while True:
        if (time.time() - start_time) > DURATION_LIMIT:
            print("6 hours completed. Shutting down stream safely.")
            break

        current_q = questions[q_index % len(questions)]
        leaderboard = load_json("leaderboard.json", {})

        # AI Voice Reading Question & Options[span_18](start_span)[span_18](end_span)
        q_text_speech = f"Question {current_q.get('id')}: {current_q.get('question')}. Option A: {current_q.get('options', [''])[0]}, Option B: {current_q.get('options', ['', ''])[1]}, Option C: {current_q.get('options', ['', '', ''])[2]}, Option D: {current_q.get('options', ['', '', '', ''])[3]}. Sahi jawab live chat mein A, B, C ya D type karein!"
        threading.Thread(target=speak_text, args=(q_text_speech,)).start()

        question_start_wall_time = time.time()

        for timer in range(15, 0, -1):
            if chat and chat.is_alive():
                try:
                    for c in chat.get().sync_items():
                        msg = c.message.strip().upper()
                        author = c.author.name
                        recent_chats.append((author, c.message))
                        if len(recent_chats) > 20:
                            recent_chats.pop(0)

                        if msg in ["A", "B", "C", "D"]:
                            correct_ans = str(current_q.get('answer', '')).strip().upper()
                            if msg == correct_ans:
                                # Scoring Rule: First 3 seconds = 15 pts, else 10 pts[span_19](start_span)[span_19](end_span)
                                elapsed = time.time() - question_start_wall_time
                                pts_awarded = 15 if elapsed <= 3.0 else 10
                                
                                leaderboard[author] = leaderboard.get(author, 0) + pts_awarded
                                save_json("leaderboard.json", leaderboard)
                                ticker_msg = f"@{author} (+{pts_awarded} pts) 🎉"
                                
                                threading.Thread(target=speak_text, args=(f"{author} ne sahi jawab diya! {pts_awarded} points mile!",)).start()
                except Exception as e:
                    pass

            for _ in range(FPS):
                frame_img = draw_ui(current_q, leaderboard, ticker_msg, timer, recent_chats)
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
        
