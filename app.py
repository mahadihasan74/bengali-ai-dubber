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
import whisper
from googletrans import Translator
from gtts import gTTS
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ফাইল আপলোড এবং সেভ করার ফোল্ডার সেটিংস
UPLOAD_FOLDER = "/tmp/uploads" if os.path.exists("/tmp") else "uploads"
AUDIO_FOLDER = "/tmp/generated_audios" if os.path.exists("/tmp") else "generated_audios"

for folder in [UPLOAD_FOLDER, AUDIO_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

ALLOWED_EXTENSIONS = {'mp3', 'wav', 'm4a', 'ogg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    return jsonify({"status": "AI Audiobook Server is running perfectly!"})

@app.route('/convert', methods=['POST', 'OPTIONS'])
def convert_audio():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
        
    # রিকোয়েস্টে ফাইল আছে কিনা চেক করা
    if 'file' not in request.files:
        return jsonify({"error": "কোনো ফাইল পাওয়া যায়নি"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "সঠিক ফাইল সিলেক্ট করুন"}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        base_name = os.path.splitext(filename)[0]
        input_path = os.path.join(UPLOAD_FOLDER, filename)
        output_mp3_name = f"bn_{base_name}.mp3"
        output_path = os.path.join(AUDIO_FOLDER, output_mp3_name)
        
        # ফাইলটি সার্ভারে সেভ করা
        file.save(input_path)
        
        try:
            # ১. Whisper AI দিয়ে স্পিচ-টু-টেক্সট করা
            model = whisper.load_model("base")
            result = model.transcribe(input_path)
            original_text = result["text"]
            
            # ২. Google দিয়ে বাংলায় অনুবাদ করা
            translator = Translator()
            bangla_text = translator.translate(original_text, dest='bn').text
            
            # ৩. gTTS দিয়ে নতুন বাংলা অডিওবুক তৈরি করা
            tts = gTTS(text=bangla_text, lang='bn', slow=False)
            tts.save(output_path)
            
            # কাজ শেষে আপলোড করা মূল ফাইলটি ডিলিট করে দেওয়া (সার্ভার ফাস্ট রাখতে)
            if os.path.exists(input_path):
                os.remove(input_path)
                
            host_url = request.host_url.rstrip('/')
            return jsonify({
                "success": True,
                "original_text": original_text,
                "bangla_note": bangla_text,
                "audio_url": f"{host_url}/audio/{output_mp3_name}"
            })
            
        except Exception as e:
            if os.path.exists(input_path):
                os.remove(input_path)
            return jsonify({"error": str(e)}), 500
            
    return jsonify({"error": "অনুমোদিত ফাইল ফরম্যাট নয় (.mp3, .wav প্রয়োজন)"}), 400

@app.route('/audio/<filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_FOLDER, filename)

if __name__ == '__main__':
    app.run(port=5000, debug=True)
