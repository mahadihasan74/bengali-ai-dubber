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
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

UPLOAD_FOLDER = "/tmp/uploads" if os.path.exists("/tmp") else "uploads"
AUDIO_FOLDER = "/tmp/generated_audios" if os.path.exists("/tmp") else "generated_audios"

for folder in [UPLOAD_FOLDER, AUDIO_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

ALLOWED_EXTENSIONS = {'wav', 'mp3'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_audio_to_bangla(input_path, base_name):
    output_mp3_name = f"bn_{base_name}.mp3"
    output_path = os.path.join(AUDIO_FOLDER, output_mp3_name)
    
    # লাইটওয়েট স্পিচ রিকগনিশন (RAM বাঁচানোর জন্য)
    r = sr.Recognizer()
    with sr.AudioFile(input_path) as source:
        audio_data = r.record(source)
        # গুগল স্পিচ এপিআই দিয়ে ইংরেজি টেক্সট উদ্ধার
        original_text = r.recognize_google(audio_data, language="en-US")
            
    # বাংলায় অনুবাদ
    translator = Translator()
    bangla_text = translator.translate(original_text, dest='bn').text
    
    # বাংলা ভয়েস জেনারেশন
    tts = gTTS(text=bangla_text, lang='bn', slow=False)
    tts.save(output_path)
    
    return original_text, bangla_text, output_mp3_name

@app.route('/')
def home():
    return jsonify({"status": "Low-RAM AI Audiobook Server is running perfectly!"})

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
        input_path = os.path.join(UPLOAD_FOLDER, filename)
        
        file.save(input_path)
        
        try:
            orig_text, bn_note, out_file = process_audio_to_bangla(input_path, base_name)
            
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
            
    return jsonify({"error": "অনুমোদিত ফাইল ফরম্যাট নয় (.wav বা .mp3 প্রয়োজন)"}), 400

@app.route('/audio/<filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_FOLDER, filename)

if __name__ == '__main__':
    app.run(port=5000, debug=True)
