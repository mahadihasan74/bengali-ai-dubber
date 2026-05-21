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
import speech_recognition as sr
from googletrans import Translator
from gtts import gTTS
import static_ffmpeg
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

# ffmpeg পাথ অ্যাড করা যাতে mp3 থেকে wav কনভার্ট হতে পারে
static_ffmpeg.add_paths()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

UPLOAD_FOLDER = "/tmp/uploads" if os.path.exists("/tmp") else "uploads"
AUDIO_FOLDER = "/tmp/generated_audios" if os.path.exists("/tmp") else "generated_audios"

for folder in [UPLOAD_FOLDER, AUDIO_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

ALLOWED_EXTENSIONS = {'wav', 'mp3', 'm4a', 'ogg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_audio_to_bangla(input_path, base_name, file_ext):
    wav_path = input_path
    converted = False
    
    # যদি ফাইলটি mp3 বা অন্য ফরম্যাটের হয়, তবে সেটাকে pcm wav এ কনভার্ট করা
    if file_ext != 'wav':
        wav_path = os.path.join(UPLOAD_FOLDER, f"{base_name}_temp.wav")
        # ffmpeg কমান্ড ব্যবহার করে স্মুথ কনভার্সন
        os.system(f'ffmpeg -y -i "{input_path}" -ac 1 -ar 16000 "{wav_path}"')
        converted = True

    output_mp3_name = f"bn_{base_name}.mp3"
    output_path = os.path.join(AUDIO_FOLDER, output_mp3_name)
    
    # স্পিচ রিকগনিশন প্রসেস
    r = sr.Recognizer()
    with sr.AudioFile(wav_path) as source:
        audio_data = r.record(source)
        original_text = r.recognize_google(audio_data, language="en-US")
            
    # বাংলায় অনুবাদ
    translator = Translator()
    bangla_text = translator.translate(original_text, dest='bn').text
    
    # বাংলা অডিও জেনারেশন
    tts = gTTS(text=bangla_text, lang='bn', slow=False)
    tts.save(output_path)
    
    # টেম্পোরারি কনভার্ট করা wav ফাইল ডিলিট করা
    if converted and os.path.exists(wav_path):
        os.remove(wav_path)
        
    return original_text, bangla_text, output_mp3_name

@app.route('/')
def home():
    return jsonify({"status": "AI Audiobook Server is running perfectly with MP3 Support!"})

@app.route('/convert', methods=['POST', 'OPTIONS'])
def convert_audio():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
        
    if 'file' not in request.files:
        return jsonify({"error": "কোনো ফাইল পাওয়া যায়নি"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "সঠিক ফাইল সিলেক্ট করুন"}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        base_name = os.path.splitext(filename)[0]
        file_ext = filename.rsplit('.', 1)[1].lower()
        input_path = os.path.join(UPLOAD_FOLDER, filename)
        
        file.save(input_path)
        
        try:
            orig_text, bn_note, out_file = process_audio_to_bangla(input_path, base_name, file_ext)
            
            if os.path.exists(input_path):
                os.remove(input_path)
                
            host_url = request.host_url.rstrip('/')
            return jsonify({
                "success": True,
                "original_text": orig_text,
                "bangla_note": bn_note,
                "audio_url": f"{host_url}/audio/{out_file}"
            })
            
        except Exception as e:
            if os.path.exists(input_path):
                os.remove(input_path)
            return jsonify({"error": str(e)}), 500
            
    return jsonify({"error": "অনুমোদিত ফাইল ফরম্যাট নয়"}), 400

@app.route('/audio/<filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_FOLDER, filename)

if __name__ == '__main__':
    app.run(port=5000, debug=True)
