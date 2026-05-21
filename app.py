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
# লাইভ সার্ভারের জন্য CORS পারফেক্টলি কনফিগার করা
CORS(app, resources={r"/*": {"origins": "*"}})

AUDIO_FOLDER = "/tmp/generated_audios" if os.path.exists("/tmp") else "generated_audios"
if not os.path.exists(AUDIO_FOLDER):
    os.makedirs(AUDIO_FOLDER)

def process_video_to_bangla(video_url, video_id):
    output_mp3 = os.path.join(AUDIO_FOLDER, f"{video_id}.mp3")
    
    if os.path.exists(output_mp3):
        return f"{video_id}.mp3"

    temp_audio = os.path.join(AUDIO_FOLDER, f"temp_{video_id}")
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
    
    model = whisper.load_model("base")
    result = model.transcribe(temp_file)
    original_text = result["text"]
    
    translator = Translator()
    bangla_text = translator.translate(original_text, dest='bn').text
    
    tts = gTTS(text=bangla_text, lang='bn', slow=False)
    tts.save(output_mp3)
    
    if os.path.exists(temp_file):
        os.remove(temp_file)
        
    return f"{video_id}.mp3"

@app.route('/')
def home():
    return jsonify({"status": "Server is running perfectly!"})

@app.route('/convert', methods=['POST', 'OPTIONS'])
def convert_video():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
        
    data = request.json or {}
    video_url = data.get('url', '')
    
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
        # রেন্ডারের লাইভ লিঙ্ক ডাইনামিকালি জেনারেট করা
        host_url = request.host_url.rstrip('/')
        return jsonify({
            "success": True,
            "video_id": video_id,
            "audio_url": f"{host_url}/audio/{audio_file_name}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/audio/<filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_FOLDER, filename)

if __name__ == '__main__':
    app.run(port=5000, debug=True)
