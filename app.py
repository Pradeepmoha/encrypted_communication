import os
import mysql.connector
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask_cors import CORS

app = Flask(__name__)
# This allows your future live React app to talk to this Python server
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# --- DATABASE CONNECTION ---
def get_db_connection():
    return mysql.connector.connect(
        host="gateway01.ap-southeast-1.prod.aws.tidbcloud.com",
        port=4000,
        user="",
        password="", # <-- UPDATE THIS!
        database="test", 
        ssl_ca="isrgrootx1.pem",  # <-- UPDATE THIS! (e.g., "isrgrootx1.pem")
        ssl_verify_cert=True,
        ssl_verify_identity=True
    )

# --- REST API ROUTES ---

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash, public_key) VALUES (%s, %s, %s)",
            (data['username'], data['password_hash'], data['public_key'])
        )
        conn.commit()
        return jsonify({"message": "User registered successfully!"}), 201
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 400
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

@app.route('/users', methods=['GET'])
def get_users():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, username, public_key FROM users")
        users = cursor.fetchall()
        return jsonify(users), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

@app.route('/create_group', methods=['POST'])
def create_group():
    data = request.json
    group_name = data.get('group_name')
    members = data.get('members') # Expects a list of usernames
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert the group
        cursor.execute("INSERT INTO chat_groups (group_name) VALUES (%s)", (group_name,))
        group_id = cursor.lastrowid
        
        # Insert the members
        for username in members:
            cursor.execute(
                "INSERT INTO group_members (group_id, username) VALUES (%s, %s)",
                (group_id, username)
            )
            
        conn.commit()
        return jsonify({"message": "Group created successfully", "group_id": group_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

# --- WEBSOCKET ROUTING (The Router) ---

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")

@socketio.on('join')
def on_join(data):
    username = data['username']
    room = data['room'] # Can be a direct chat ID or a group ID
    join_room(room)
    print(f"{username} has entered room: {room}")

@socketio.on('leave')
def on_leave(data):
    username = data['username']
    room = data['room']
    leave_room(room)
    print(f"{username} has left room: {room}")

@socketio.on('send_message')
def handle_message(data):
    room = data['room']
    # The server doesn't decrypt anything, it just blindly forwards the ciphertext!
    emit('receive_message', data, to=room)

if __name__ == '__main__':
    # Using port 5000 for local testing. Render will automatically assign its own port later!
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
