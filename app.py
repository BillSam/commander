import os
import json
import subprocess
import shlex
from flask import Flask, jsonify, request
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app)

OUTPUT_DIR = 'outputs'
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

running_commands = {}

def save_output(command_id, output):
    filepath = os.path.join(OUTPUT_DIR, f'{command_id}.json')
    if os.path.exists(filepath):
        with open(filepath, 'r') as file:
            data = json.load(file)
    else:
        data = {'output': []}
    
    data['output'].append(output)
    
    with open(filepath, 'w') as file:
        json.dump(data, file)

def load_output(command_id):
    filepath = os.path.join(OUTPUT_DIR, f'{command_id}.json')
    if os.path.exists(filepath):
        with open(filepath, 'r') as file:
            data = json.load(file)
        return data.get('output', [])
    return []

@app.route('/output/<command_id>')
def get_output(command_id):
    output = load_output(command_id)
    return jsonify({'output': output})

@app.route('/run_command', methods=['POST'])
def run_command():
    command_id = request.json.get('id')
    command = request.json.get('command')
    if not command_id or not command:
        return jsonify({'error': 'Missing command or ID'}), 400

    process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)
    running_commands[command_id] = process
    
    tool = command.split()[0]  # Extract the tool name from the command
    socketio.emit('command_started', {'id': command_id, 'command': command, 'tool': tool})

    for line in process.stdout:
        cleaned_line = line.strip()
        if cleaned_line:
            save_output(command_id, cleaned_line)  # Save output to a file
            socketio.emit('command_output', {'id': command_id, 'output': cleaned_line})

    process.wait()
    if process.returncode == 0:
        socketio.emit('command_completed', {'id': command_id, 'status': 'completed'})
    else:
        socketio.emit('command_completed', {'id': command_id, 'status': 'error'})

    del running_commands[command_id]
    return jsonify({'status': 'Command started'})

@app.route('/stop_command', methods=['POST'])
def stop_command():
    command_id = request.json.get('id')
    if command_id in running_commands:
        process = running_commands.pop(command_id)
        process.terminate()
        socketio.emit('command_stopped', {'id': command_id})
        return jsonify({'status': 'Command stopped'})
    return jsonify({'error': 'Command not found'}), 404

if __name__ == '__main__':
    socketio.run(app, debug=True)
