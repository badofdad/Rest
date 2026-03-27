from flask import Flask, request, jsonify
import subprocess
import threading
import os
import signal
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
bgmi_process = None
stop_event = threading.Event()

def run_bgmi_server(ip, port, duration, threads):
    global bgmi_process
    try:
        command = f"./bgmi {ip} {port} {duration} {threads}"
        logger.info(f"Starting BGMI server with command: {command}")

        bgmi_process = subprocess.Popen(
            command,
            shell=True,
            preexec_fn=os.setsid,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        stop_event.wait(timeout=int(duration))

        if bgmi_process and bgmi_process.poll() is None:
            os.killpg(os.getpgid(bgmi_process.pid), signal.SIGTERM)
            bgmi_process.wait()

    except Exception as e:
        logger.error(f"Error running BGMI: {e}")
    finally:
        stop_event.clear()

@app.route('/start-server', methods=['POST'])
def start_server():
    global bgmi_process

    if bgmi_process and bgmi_process.poll() is None:
        return jsonify({"status": "error", "message": "Server already running"}), 400

    data = request.get_json()
    required_params = ['ip', 'port', 'duration']
    if not all(param in data for param in required_params):
        return jsonify({
            "status": "error",
            "message": f"Missing required parameters: {required_params}"
        }), 400

    threads = data.get('threads', 1)
    stop_event.clear()

    thread = threading.Thread(
        target=run_bgmi_server,
        args=(data['ip'], data['port'], data['duration'], threads)
    )
    thread.start()

    return jsonify({
        "status": "success",
        "message": "Server started",
        "parameters": {
            "ip": data['ip'],
            "port": data['port'],
            "duration": data['duration'],
            "threads": threads
        }
    })

@app.route('/stop-server', methods=['POST'])
def stop_server():
    global bgmi_process

    if not bgmi_process or bgmi_process.poll() is not None:
        return jsonify({"status": "error", "message": "No server running"}), 400

    try:
        os.killpg(os.getpgid(bgmi_process.pid), signal.SIGTERM)
        bgmi_process.wait()
        return jsonify({"status": "success", "message": "Server stopped"})
    except Exception as e:
        logger.error(f"Error stopping server: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/status', methods=['GET'])
def status():
    global bgmi_process

    if bgmi_process and bgmi_process.poll() is None:
        return jsonify({
            "status": "running",
            "pid": bgmi_process.pid,
            "return_code": None
        })
    else:
        return jsonify({
            "status": "stopped",
            "pid": None,
            "return_code": bgmi_process.poll() if bgmi_process else None
        })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)