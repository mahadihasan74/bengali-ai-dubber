import sys
import types

# পাইথন ৩.১৪ এর cgi.parse_header এরর ফিক্স
cgi_module = types.ModuleType('cgi')
cgi_module.parse_header = lambda content_type: (
    content_type.split(';')[0], 
    {k.split('=')[0].strip(): k.split('=')[1].strip() for k in content_type.split(';')[1:] if '=' in k}
)
sys.modules['cgi'] = cgi_module

import os
import yt_dlp
import whisper
from googletrans import Translator
from gtts import gTTS
import static_ffmpeg
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

static_ffmpeg.add_paths()

app = Flask(__name__)
CORS(app) # ফ্রন্টএন্ড থেকে রিকোয়েস্ট অ্যালাউ করার জন্য

AUDIO_FOLDER = "generated_audios"
if not os.path.exists(AUDIO_FOLDER):
    os.makedirs(AUDIO_FOLDER)

def process_video_to_bangla(video_url, video_id):
    output_mp3 = os.path.join(AUDIO_FOLDER, f"{video_id}.mp3")
    
    # যদি এই ভিডিও আগে থেকেই কনভার্ট করা থাকে, তবে নতুন করে করবে না (টাকা ও সময় বাঁচবে)
    if os.path.exists(output_mp3):
        return f"{video_id}.mp3"

    # ১. অডিও ডাউনলোড
    temp_audio = f"temp_{video_id}"
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{temp_audio}.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
    
    temp_file = f"{temp_audio}.mp3"
    
    # ২. ট্রান্সক্রাইব
    model = whisper.load_model("base")
    result = model.transcribe(temp_file)
    original_text = result["text"]
    
    # ৩. অনুবাদ
    translator = Translator()
    bangla_text = translator.translate(original_text, dest='bn').text
    
    # ৪. বাংলা ভয়েস তৈরি
    tts = gTTS(text=bangla_text, lang='bn', slow=False)
    tts.save(output_mp3)
    
    # টেম্পোরারি ফাইল ডিলিট
    if os.path.exists(temp_file):
        os.remove(temp_file)
        
    return f"{video_id}.mp3"

@app.route('/convert', methods=['POST'])
def convert_video():
    data = request.json
    video_url = data.get('url')
    
    # ভিডিও আইডি এক্সট্রাক্ট করা
    video_id = ""
    if "youtu.be/" in video_url:
        video_id = video_url.split("youtu.be/")[1].split("?")[0]
    elif "v=" in video_url:
        video_id = video_url.split("v=")[1].split("&")[0]
    elif "shorts/" in video_url:
        video_id = video_url.split("shorts/")[1].split("?")[0]

    if not video_id:
        return jsonify({"error": "ভুল ইউটিউব লিংক"}), 400
        
    try:
        audio_file_name = process_video_to_bangla(video_url, video_id)
        return jsonify({
            "success": True,
            "video_id": video_id,
            "audio_url": f"http://127.0.0.1:5000/audio/{audio_file_name}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/audio/<filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_FOLDER, filename)

if __name__ == '__main__':
    app.run(port=5000, debug=True)