from flask import Flask, jsonify
import datetime

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        'message': 'Hello from Docker!',
        'status': 'success',
        'timestamp': datetime.datetime.now().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'python-web-api'
    })

@app.route('/api/data')
def get_data():
    return jsonify({
        'items': [
            {'id': 1, 'name': 'Docker', 'type': 'Container Platform'},
            {'id': 2, 'name': 'Python', 'type': 'Programming Language'},
            {'id': 3, 'name': 'Flask', 'type': 'Web Framework'}
        ],
        'count': 3
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
