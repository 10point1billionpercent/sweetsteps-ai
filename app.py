from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq
import json
import os

app = Flask(__name__)

# ----------------------------------------------------------
# CAFEINE-SAFE, MINIMAL, UNIVERSAL CORS
# ----------------------------------------------------------
CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    methods=["GET", "POST", "OPTIONS"]
)

@app.route("/<path:path>", methods=["OPTIONS"])
def options_handler(path):
    return ("", 204)

# ----------------------------------------------------------
# GROQ CLIENT
# ----------------------------------------------------------
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ----------------------------------------------------------
# JSON BODY EXTRACTOR (RENDER-FIX)
# ----------------------------------------------------------
def get_json():
    try:
        if request.is_json:
            return request.get_json()
        raw = request.data.decode("utf-8")
        print("RAW BODY FROM RENDER:", raw)
        return json.loads(raw) if raw else {}
    except Exception as e:
        print("JSON PARSE ERROR:", e)
        return {}

# ----------------------------------------------------------
# 1) ONBOARDING PLAN
# /onboarding-plan
# ----------------------------------------------------------
@app.post("/onboarding-plan")
def generate_onboarding():
    data = get_json()
    vague_goal = data.get("vagueGoal")
    current_progress = data.get("currentProgress")
    time_limit = data.get("timeLimit")

    if not vague_goal or not current_progress or not time_limit:
        return jsonify({"error": "vagueGoal, currentProgress, and timeLimit required"}), 400

    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        temperature=0.7,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Generate onboarding results. "
                    "Return STRICT JSON with exactly:\n"
                    "{ bigGoal: string,\n"
                    "  dailyStep: string,\n"
                    "  weeklyMountain: { name: string, note: string, weeklyTarget: string }\n"
                    "}\n"
                    "Make weeklyTarget a descriptive string (example: 'Learn 10 new shlokas')."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Vague Goal: {vague_goal}\n"
                    f"Current Progress: {current_progress}\n"
                    f"Time Limit: {time_limit}"
                )
            }
        ]
    )

    result = json.loads(completion.choices[0].message.content)
    return jsonify(result)

# ----------------------------------------------------------
# 2) WEEKLY MOUNTAIN
# /weekly-mountain
# ----------------------------------------------------------
@app.post("/weekly-mountain")
def generate_weekly_mountain():
    data = get_json()
    big_goal = data.get("bigGoal")

    if not big_goal:
        return jsonify({"error": "bigGoal required"}), 400

    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        temperature=0.7,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Generate a weekly mountain. "
                    "Return STRICT JSON:\n"
                    "{ name: string, note: string, weeklyTarget: string }\n"
                    "weeklyTarget MUST be a descriptive string."
                )
            },
            {
                "role": "user",
                "content": f"Big Goal: {big_goal}"
            }
        ]
    )

    result = json.loads(completion.choices[0].message.content)
    return jsonify(result)

# ----------------------------------------------------------
# 3) DAILY SWEETSTEPS
# /daily-steps
# ----------------------------------------------------------
@app.post("/daily-steps")
def generate_daily_steps():
    data = get_json()
    big_goal = data.get("bigGoal")
    weekly_mountain = data.get("weeklyMountain")

    if not big_goal or not weekly_mountain:
        print("DATA RECEIVED:", data)
        return jsonify({"error": "bigGoal and weeklyMountain required"}), 400

    def ask():
        try:
            c = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                temperature=0.7,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Generate today's Daily SweetSteps.\n"
                            "Return STRICT JSON:\n"
                            "{ steps: [ { day: string, task: string, time: string } ],\n"
                            "  coachNote: string }\n"
                            "All fields MUST be strings."
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
            print("Groq JSON ERROR:", e)
            return None

    out = ask()
    if out is None:
        print("Retrying Groq once…")
        out = ask()

    if out is None:
        return jsonify({
            "error": "Groq failed twice",
            "fallback": {
                "steps": [
                    {"day": "Today", "task": "Warm up", "time": "5 minutes"},
                    {"day": "Today", "task": "Main push", "time": "15 minutes"}
                ],
                "coachNote": "Fallback activated, keep going!"
            }
        }), 500

    return jsonify(out)

# ----------------------------------------------------------
# HEALTH CHECK
# ----------------------------------------------------------
@app.get("/")
def health():
    return {"status": "alive"}, 200


# ----------------------------------------------------------
# END
# ----------------------------------------------------------