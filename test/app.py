from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Registered users
users = {
    1: "Aditya",
    2: "Aman",
    3: "Admin"
}

# Stores latest scan result
last_scan = {
    "status": "waiting"
}


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/last', methods=['GET'])
def last():
    return jsonify(last_scan)


@app.route('/verify', methods=['POST'])
def verify():

    global last_scan

    data = request.json

    finger_id = data.get("finger_id")
    confidence = data.get("confidence")

    if finger_id in users:

        last_scan = {
            "status": "authorized",
            "user": users[finger_id],
            "confidence": confidence
        }

        return jsonify(last_scan)

    last_scan = {
        "status": "unauthorized",
        "user": "Unknown"
    }

    return jsonify(last_scan)


if __name__ == '__main__':
    print(app.url_map)
    app.run(host='0.0.0.0', port=5000, debug=True)