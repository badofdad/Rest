from flask import Flask, request, jsonify
import subprocess
import threading
import os
import signal
import logging
import sys
import time
import stat

app = Flask(__name__)

# Configure logging
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
output_logs = []

# Try to make bgmi executable at startup
def ensure_bgmi_executable():
    bgmi_path = './bgmi'
    if os.path.exists(bgmi_path):
        try:
            # Check if it's executable
            if not os.access(bgmi_path, os.X_OK):
                logger.info("Making bgmi executable...")
                # Add executable permissions for owner, group, and others
                current_permissions = os.stat(bgmi_path).st_mode
                os.chmod(bgmi_path, current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                logger.info("bgmi is now executable")
            else:
                logger.info("bgmi is already executable")
        except Exception as e:
            logger.error(f"Failed to make bgmi executable: {e}")
    else:
        logger.error("bgmi binary not found in current directory!")

# Run this when the app starts
ensure_bgmi_executable()

def log_output(stream, log_func, source):
    global output_logs
    for line in stream:
        if line.strip():
            log_entry = f"[{source}] {line.strip()}"
            log_func(line.strip())
            output_logs.append(log_entry)
            if len(output_logs) > 1000:
                output_logs.pop(0)

def run_bgmi_server(ip, port, duration, threads):
    global bgmi_process, output_logs
    
    output_logs = []
    
    try:
        # Double-check binary exists and is executable
        if not os.path.exists('./bgmi'):
            error_msg = "BGMI binary not found in current directory"
            logger.error(error_msg)
            output_logs.append(error_msg)
            return
        
        # Ensure it's executable (again, just in case)
        if not os.access('./bgmi', os.X_OK):
            logger.warning("bgmi not executable, attempting to chmod...")
            os.chmod('./bgmi', 0o755)
        
        command = f"./bgmi {ip} {port} {duration} {threads}"
        logger.info(f"Starting BGMI server with command: {command}")

        bgmi_process = subprocess.Popen(
            command,
            shell=True,
            preexec_fn=os.setsid if os.name != 'nt' else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        stdout_thread = threading.Thread(
            target=log_output,
            args=(bgmi_process.stdout, logger.info, "STDOUT")
        )
        stderr_thread = threading.Thread(
            target=log_output,
            args=(bgmi_process.stderr, logger.error, "STDERR")
        )
        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()

        start_time = time.time()
        while time.time() - start_time < float(duration):
            if stop_event.is_set():
                logger.info("Stop event received, terminating process")
                break
            time.sleep(1)

        if bgmi_process and bgmi_process.poll() is None:
            if os.name != 'nt':
                os.killpg(os.getpgid(bgmi_process.pid), signal.SIGTERM)
            else:
                bgmi_process.terminate()
            bgmi_process.wait(timeout=5)

    except subprocess.TimeoutExpired:
        logger.error("Process didn't terminate in time, forcing kill")
        if bgmi_process:
            if os.name != 'nt':
                os.killpg(os.getpgid(bgmi_process.pid), signal.SIGKILL)
            else:
                bgmi_process.kill()
    except Exception as e:
        logger.error(f"Error running BGMI: {e}")
        output_logs.append(f"ERROR: {str(e)}")
    finally:
        bgmi_process = None
        stop_event.clear()

@app.route('/start-server', methods=['POST'])
def start_server():
    global bgmi_process

    if bgmi_process and bgmi_process.poll() is None:
        return jsonify({"status": "error", "message": "Server already running"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No JSON data provided"}), 400

    required_params = ['ip', 'port', 'duration']
    if not all(param in data for param in required_params):
        return jsonify({
            "status": "error",
            "message": f"Missing required parameters: {required_params}"
        }), 400

    try:
        port_num = int(data['port'])
        duration_sec = int(data['duration'])
        threads = int(data.get('threads', 1))
        
        if port_num < 1 or port_num > 65535:
            return jsonify({"status": "error", "message": "Invalid port number"}), 400
        if duration_sec < 1:
            return jsonify({"status": "error", "message": "Duration must be at least 1 second"}), 400
    except ValueError:
        return jsonify({"status": "error", "message": "Port, duration, and threads must be numbers"}), 400

    # Check if bgmi binary exists before starting
    if not os.path.exists('./bgmi'):
        return jsonify({
            "status": "error", 
            "message": "bgmi binary not found. Please ensure the binary file is uploaded."
        }), 500

    stop_event.clear()

    thread = threading.Thread(
        target=run_bgmi_server,
        args=(data['ip'], port_num, duration_sec, threads),
        daemon=True
    )
    thread.start()

    return jsonify({
        "status": "success",
        "message": "Server started",
        "parameters": {
            "ip": data['ip'],
            "port": port_num,
            "duration": duration_sec,
            "threads": threads
        }
    })

@app.route('/stop-server', methods=['POST'])
def stop_server():
    global bgmi_process

    if not bgmi_process or bgmi_process.poll() is not None:
        return jsonify({"status": "error", "message": "No server running"}), 400

    try:
        stop_event.set()
        if os.name != 'nt':
            os.killpg(os.getpgid(bgmi_process.pid), signal.SIGTERM)
        else:
            bgmi_process.terminate()
        bgmi_process.wait(timeout=5)
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
    global output_logs
    # Get last N lines, default 100
    limit = request.args.get('limit', default=100, type=int)
    return jsonify({
        "logs": output_logs[-limit:] if output_logs else []
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
