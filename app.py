from flask import Flask, request, jsonify
import subprocess
import threading
import os
import signal
import logging
import sys

app = Flask(__name__)

# Configure logging to show both Flask and BGMI output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Global variables
bgmi_process = None
stop_event = threading.Event()

def run_bgmi_server(ip, port, duration, threads):
    global bgmi_process
    try:
        command = f"./danger {ip} {port} {duration} {threads}"
        logger.info(f"Starting BGMI server with command: {command}")

        # Modified to show output in real-time
        bgmi_process = subprocess.Popen(
            command,
            shell=True,
            preexec_fn=os.setsid,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True
        )

        # Function to read and log output in real-time
        def log_output(stream, log_func):
            for line in stream:
                log_func(line.strip())

        # Start threads to read output
        stdout_thread = threading.Thread(
            target=log_output,
            args=(bgmi_process.stdout, logger.info)
        )
        stderr_thread = threading.Thread(
            target=log_output,
            args=(bgmi_process.stderr, logger.error)
        )
        stdout_thread.start()
        stderr_thread.start()

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

@app.route('/logs', methods=['GET'])
def get_logs():
    global bgmi_process
    if not bgmi_process:
        return jsonify({"error": "No process running"}), 404

    stdout, stderr = bgmi_process.communicate(timeout=1)  # 1-second timeout
    return jsonify({
        "stdout": stdout,
        "stderr": stderr,
        "return_code": bgmi_process.returncode
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)