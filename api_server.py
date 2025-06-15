from flask import Flask, jsonify
from database import get_logs

app = Flask(__name__)

@app.route("/logs", methods=["GET"])
def logs():
    return jsonify(get_logs())

def start_api():
    app.run(host="0.0.0.0", port=5000)
