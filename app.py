from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq
import json
import os

app = Flask(__name__)

# Minimal, safe, Caffeine-compatible CORS
CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    methods=["GET", "POST", "OPTIONS"]
)

@app.route("/<path:path>", methods=["OPTIONS"])
def options_handler(path):
    return ("", 204)

# (ALL YOUR EXISTING ENDPOINTS BELOW… unchanged)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ----------------------------------------------------------
# SAFE JSON EXTRACTOR (Fixes Render empty-body issue)
# ----------------------------------------------------------
def get_json():
    try:
        if request.is_json:
            return request.get_json()
        else:
            raw = request.data.decode("utf-8")
            print("RAW BODY FROM RENDER:", raw)
            return json.loads(raw) if raw else {}
    except Exception as e:
        print("JSON PARSE ERROR:", e)
        return {}

# ----------------------------------------------------------
# ONBOARDING ENDPOINT
# ----------------------------------------------------------
@app.post("/generate-onboarding")
def generate_onboarding():
    data = get_json()
    vague_goal = data.get("vague_goal")
    progress = data.get("progress")
    time_limit = data.get("time_limit")

    if not vague_goal or not progress or not time_limit:
        return jsonify({"error": "vague_goal, progress and time_limit required"}), 400

    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        temperature=0.7,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Generate a big goal, weekly mountain info, and daily sample step. "
                    "Return strict JSON: { bigGoal, weeklyMountain { name, weeklyTarget, note }, dailyStep }"
                )
            },
            {
                "role": "user",
                "content": (
                    f"Vague Goal: {vague_goal}\n"
                    f"Current Progress: {progress}\n"
                    f"Time Limit: {time_limit}"
                )
            }
        ]
    )

    return jsonify(json.loads(completion.choices[0].message.content))


# ----------------------------------------------------------
# WEEKLY MOUNTAIN ENDPOINT
# ----------------------------------------------------------
@app.post("/generate-weekly-mountain")
def generate_weekly_mountain():
    data = get_json()
    big_goal = data.get("big_goal")

    if not big_goal:
        return jsonify({"error": "big_goal required"}), 400

    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        temperature=0.7,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Generate a weekly mountain. Return strict JSON: "
                    "{ name, weeklyTarget, note }"
                )
            },
            {
                "role": "user",
                "content": f"Big Goal: {big_goal}"
            }
        ]
    )

    return jsonify(json.loads(completion.choices[0].message.content))


# ----------------------------------------------------------
# DAILY STEPS ENDPOINT (FIXED AGAIN — NOW 100% SAFE)
# ----------------------------------------------------------
@app.post("/daily-steps")
def generate_daily_steps():
    data = get_json()
    big_goal = data.get("big_goal")
    weekly_mountain = data.get("weekly_mountain")

    if not big_goal or not weekly_mountain:
        print("DATA RECEIVED:", data)
        return jsonify({"error": "big_goal and weekly_mountain required"}), 400

    def ask_groq():
        try:
            c = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                temperature=0.7,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Generate today's daily SweetSteps using BOTH the big goal "
                            "and weekly mountain. Return JSON: { steps: [], coachNote }"
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Big Goal: {big_goal}\n"
                            f"Weekly Mountain: {weekly_mountain}"
                        )
                    }
                ]
            )
            return json.loads(c.choices[0].message.content)
        except Exception as e:
            print("Groq JSON error:", e)
            return None

    result = ask_groq()
    if result is None:
        print("Retrying Groq…")
        result = ask_groq()

    if result is None:
        return jsonify({
            "error": "Groq returned invalid JSON twice",
            "fallback": {
                "steps": [
                    {"title": "Warm up", "description": "Start small", "minutes": 5},
                    {"title": "Main push", "description": "Move goal forward", "minutes": 15},
                ],
                "coachNote": "Fallback activated; keep pushing!"
            }
        }), 500

    return jsonify(result)


# ----------------------------------------------------------
# HEALTH CHECK
# ----------------------------------------------------------
@app.get("/")
def health():
    return {"status": "alive"}, 200