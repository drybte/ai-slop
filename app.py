import os
import datetime
import requests
import urllib3
import redis
from flask import Flask, request, jsonify
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

app = Flask(__name__)

api_key = os.environ.get("OPENAI_API_KEY", "")
base_url = os.environ.get("OPENAI_BASE_URL", "https://kurim.ithope.eu/v1")
port = int(os.environ.get("PORT", 5000))

redis_host = os.environ.get("REDIS_HOST", "redis")
redis_port = int(os.environ.get("REDIS_PORT", 6379))

r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "AI Game Advisor běží"
    })

@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "status": "running",
        "timestamp": datetime.datetime.now().isoformat(),
        "author": "Terka",
        "app": "AI Game Advisor"
    })

@app.route("/recommend", methods=["POST"])
def recommend():
    data = request.get_json(silent=True) or {}
    genre = data.get("genre", "akční").strip().lower()

    cache_key = f"game:{genre}"

    try:
        cached = r.get(cache_key)
        if cached:
            return jsonify({
                "genre": genre,
                "recommendation": cached,
                "source": "redis-cache"
            })
    except Exception as e:
        print(f"Redis chyba při čtení: {e}")

    prompt = (
        f"Uživatel má rád herní žánr: {genre}. "
        "Doporuč mu jednu konkrétní aktuální hru z tohoto žánru. "
        "Odpověz pouze jednou krátkou větou v češtině a stručně vysvětli proč."
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gemma3:27b",
        "messages": [
            {"role": "system", "content": "Jsi expert na videohry a herní průmysl."},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }

    try:
        target_url = f"{base_url.rstrip('/')}/chat/completions"

        response = requests.post(
            target_url,
            headers=headers,
            json=payload,
            timeout=20,
            verify=False
        )

        if response.status_code == 200:
            ai_response = response.json()["choices"][0]["message"]["content"]

            try:
                r.setex(cache_key, 3600, ai_response)
            except Exception as e:
                print(f"Redis chyba při zápisu: {e}")

            return jsonify({
                "genre": genre,
                "recommendation": ai_response,
                "source": "openai-api"
            })

        return jsonify({
            "error": f"Server vrátil {response.status_code}",
            "details": response.text
        }), response.status_code

    except Exception as e:
        return jsonify({
            "error": f"Spojení selhalo: {str(e)}"
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port)