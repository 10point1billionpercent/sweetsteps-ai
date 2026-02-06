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
# JSON BODY EXTRACTOR
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
# 1) ONBOARDING
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
                    "}"
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

    return jsonify(json.loads(completion.choices[0].message.content))

# ----------------------------------------------------------
# 2) WEEKLY MOUNTAIN
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
                    "{ name: string, note: string, weeklyTarget: string }"
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
# ----------------------------------------------------------
# 3) DAILY SWEETSTEPS  (FINAL + FRONTEND-COMPATIBLE)
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
"Return STRICT JSON with EXACT shape:\n"
"{\n"
"  tasks: [\n"
"    { title: string, description: string, estimatedMinutes: number }\n"
"  ],\n"
"  coachNote: string\n"
"}\n"
"Rules:\n"
"- estimatedMinutes MUST be a number between 5 and 30.\n"
"- NEVER exceed 30 minutes.\n"
"- NEVER return hours.\n"
"- Prefer 10, 15, 20, 25, or 30-minute tasks.\n"
"- Tasks should be practical tiny steps, not giant goals.\n"
"- NO extra fields. NO nested objects."
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

    # First try
    out = ask()

    # Retry once if needed
    if out is None or "tasks" not in out:
        print("Retrying Groq once…")
        out = ask()

    # If STILL invalid, return safe fallback
    if out is None or "tasks" not in out:
        return jsonify({
            "tasks": [
                {
                    "title": "Warm-up Push",
                    "description": "Do a tiny 5-minute action toward your weekly mountain.",
                    "estimatedMinutes": 5
                },
                {
                    "title": "Main Step",
                    "description": "A meaningful action that moves your big goal forward.",
                    "estimatedMinutes": 15
                }
            ],
            "coachNote": "Fallback activated — don’t stop now!"
        }), 200

    return jsonify(out)

# ----------------------------------------------------------
# HEALTH
# ----------------------------------------------------------
@app.get("/")
def health():
    return {"status": "alive"}, 200