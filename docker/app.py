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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
