from flask import Flask, request, jsonify, render_template_string
import requests
import os
import time
import datetime
import random
import threading
import uuid
import json

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
LOG_FILE = 'logs.txt'
SESSION_FILE = 'session_data.json'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

sessions = {}  # Active sessions (session_id -> {stop_flag, count})
session_data = {}  # Saved session data (session_id -> last_comment)

# Load saved session data if available
if os.path.exists(SESSION_FILE):
    try:
        with open(SESSION_FILE, 'r') as f:
            session_data = json.load(f)
    except json.JSONDecodeError:
        print("Error: The session data file is empty or corrupted. Initializing with an empty dictionary.")
        session_data = {}
else:
    print("Session data file does not exist. Initializing with an empty dictionary.")
    session_data = {}

# Save session data function remains the same
def save_session_data():
    with open(SESSION_FILE, 'w') as f:
        json.dump(session_data, f)


def log_message(message):
    with open(LOG_FILE, 'a') as log:
        log.write(f"{datetime.datetime.now()} - {message}\n")

def is_token_valid(access_token):
    url = f"https://graph.facebook.com/me?access_token={access_token}"
    response = requests.get(url)
    return response.status_code == 200

def post_comment(post_id, comment, access_token):
    url = f"https://graph.facebook.com/{post_id}/comments"
    payload = {"message": comment, "access_token": access_token}
    response = requests.post(url, data=payload)

    try:
        result = response.json()
        if "error" in result:
            log_message(f"Error: {result['error']['message']}")
        return result
    except Exception as e:
        log_message(f"Error parsing response: {str(e)}")
        return {"error": "Invalid response"}

@app.route('/')
def index():
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Facebook Comments Bot</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: 'Arial', sans-serif;
            background-color: #f4f4f9;
            overflow-x: hidden;
        }

        header {
            position: relative;
            height: 400px;
            background: url('https://i.ibb.co/0RrL7cRm/1739107283793.jpg') no-repeat center center/cover;
            color: white;
            display: flex;
            justify-content: center;
            align-items: center;
            text-align: center;
            overflow: hidden;
        }
        header::after {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(135deg, rgba(0, 0, 0, 0.7), rgba(255, 0, 0, 0.3));
            z-index: 1;
        }
        header h1, header p {
            position: relative;
            z-index: 2;
            margin: 0;
        }
        header h1 {
            font-size: 3.5em;
            font-weight: bold;
            text-shadow: 2px 2px 10px black;
        }
        header p {
            font-size: 1.5em;
            margin-top: 10px;
        }

        form {
            background: white;
            margin: -50px auto 20px;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.3);
            max-width: 500px;
            position: relative;
            z-index: 2;
        }
        form label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
            color: #333;
        }
        form input, form button {
            width: 100%;
            padding: 10px;
            margin-bottom: 15px;
            border: 1px solid #ccc;
            border-radius: 5px;
            font-size: 1em;
        }
        form button {
            background-color: #007bff;
            color: white;
            border: none;
            cursor: pointer;
            font-size: 1.2em;
            transition: all 0.3s ease-in-out;
        }
        form button:hover {
            background-color: #0056b3;
            transform: scale(1.05);
        }

        .status-box {
            margin: 20px auto;
            padding: 15px;
            background: linear-gradient(135deg, #007bff, #0056b3);
            color: white;
            text-align: center;
            border-radius: 10px;
            max-width: 500px;
            font-size: 1.2em;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
        }

        .stop-container {
            text-align: center;
            margin: 20px 0;
        }
        .stop-container input {
            width: 60%;
            padding: 10px;
            font-size: 1em;
            border: 1px solid #ccc;
            border-radius: 5px;
            margin-right: 10px;
        }
        .stop-container button {
            padding: 10px 20px;
            background: red;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 1em;
            cursor: pointer;
            transition: background 0.3s ease;
        }
        .stop-container button:hover {
            background: darkred;
        }
    </style>
</head>
<body>
    <header>
        <div>
            <h1></h1>
            <p></p>
        </div>
    </header>

    <form action="/submit" method="POST" enctype="multipart/form-data">
        <label>Facebook Post ID:</label>
        <input type="text" name="wall_post_id" required>

        <label>Resume Session ID (Optional):</label>
        <input type="text" name="resume_session_id">

        <label>Hater Name (Optional):</label>
        <input type="text" name="hater_name">

        <label>Token File (TXT format):</label>
        <input type="file" name="token_file" required>

        <label>Comments File (TXT format):</label>
        <input type="file" name="comments_file" required>

        <label>Speed (Min Seconds between comments):</label>
        <input type="number" name="min_speed" min="1" value="5" required>

        <label>Speed (Max Seconds between comments):</label>
        <input type="number" name="max_speed" min="1" value="10" required>

        <button type="submit">Start Commenting</button>
    </form>

    <div class="status-box">
        Comments Posted: <span id="comment-count">0</span>
    </div>

    <div class="stop-container">
        <label for="session_id">Enter Session ID to Stop:</label>
        <input type="text" id="session_id">
        <button onclick="stopSession()">Stop</button>
    </div>

    <script>
        function updateStatus() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('comment-count').innerText = data.count;
                });
        }
        setInterval(updateStatus, 5000);

        function stopSession() {
            let sessionId = document.getElementById('session_id').value;
            if (!sessionId) {
                alert("Enter a valid session ID!");
                return;
            }
            fetch('/stop?session_id=' + sessionId)
                .then(response => response.json())
                .then(data => alert(data.message));
        }
    </script>
</body>
</html>
'''

@app.route('/submit', methods=['POST'])
def submit():
    post_id = request.form.get('wall_post_id')
    resume_session_id = request.form.get('resume_session_id')
    hater_name = request.form.get('hater_name', '').strip()
    min_speed = int(request.form.get('min_speed'))
    max_speed = int(request.form.get('max_speed'))

    token_file = request.files.get('token_file')
    comments_file = request.files.get('comments_file')

    token_path = os.path.join(app.config['UPLOAD_FOLDER'], token_file.filename)
    token_file.save(token_path)
    with open(token_path, 'r') as f:
        tokens = [line.strip() for line in f.readlines() if line.strip()]

    comments_path = os.path.join(app.config['UPLOAD_FOLDER'], comments_file.filename)
    comments_file.save(comments_path)
    with open(comments_path, 'r') as f:
        comments = [line.strip() for line in f.readlines() if line.strip()]

    start_index = 0
    if resume_session_id and resume_session_id in session_data:
        last_comment = session_data[resume_session_id]
        if last_comment in comments:
            start_index = comments.index(last_comment) + 1

    session_id = str(uuid.uuid4())[:8]
    sessions[session_id] = {"stop_flag": False, "count": 0}

    thread = threading.Thread(target=comment_process, args=(session_id, post_id, tokens, comments, hater_name, start_index, min_speed, max_speed))
    thread.start()

    return jsonify({"message": "Commenting started!", "session_id": session_id})

def comment_process(session_id, post_id, tokens, comments, hater_name, start_index, min_speed, max_speed):
    session = sessions[session_id]
    token_index = 0

    for i in range(start_index, len(comments)):
        if session['stop_flag']:
            session_data[session_id] = comments[i - 1]
            save_session_data()
            log_message(f"Session {session_id} stopped. Last comment saved.")
            return

        comment = f"{hater_name} {comments[i]}" if hater_name else comments[i]
        current_token = tokens[token_index]
        if not is_token_valid(current_token):
            token_index = (token_index + 1) % len(tokens)
            continue

        post_comment(post_id, comment, current_token)
        session['count'] += 1

        sleep_time = random.randint(min_speed, max_speed)
        time.sleep(sleep_time)

    del sessions[session_id]

@app.route('/stop', methods=['GET'])
def stop():
    session_id = request.args.get('session_id')
    if session_id in sessions:
        sessions[session_id]['stop_flag'] = True
        return jsonify({"message": f"Stopping session {session_id}..."})
    return jsonify({"message": "Invalid session ID!"}), 400

@app.route('/status', methods=['GET'])
def status():
    total_comments = sum(session['count'] for session in sessions.values())
    return jsonify({"count": total_comments})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
  
