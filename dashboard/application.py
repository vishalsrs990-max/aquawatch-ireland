import os
from flask import Flask, Response, send_from_directory

from flask import Flask, send_from_directory, jsonify
import os

application = Flask(__name__, static_folder="static", static_url_path="/static")

@application.route("/")
def index():
    return send_from_directory("static", "index.html")

@application.route("/config.js")
def config_js():
    api_base = os.environ.get("DASHBOARD_API_BASE", "").strip()
    js = f'window.APP_CONFIG = {{ API_BASE: "{api_base}" }};'
    return application.response_class(js, mimetype="application/javascript")

@application.route("/health")
def health():
    return jsonify({
        "ok": True,
        "api_base": os.environ.get("DASHBOARD_API_BASE", "").strip()
    })

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=8000, debug=True)