from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq
import json
import os

app = Flask(__name__)

# ----------------------------------------------------------
# UNIVERSAL CORS
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
# 1) ONBOARDING PLAN (unchanged for now)
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
# 2) WEEKLY MOUNTAIN — NEW GENTLE VERSION
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
                    "You generate a Weekly Mountain.\n"
                    "The goal: ONE gentle, realistic, motivating focus for the week.\n"
                    "\n"
                    "RULES:\n"
                    "- The mountain must be SMALL and KIND.\n"
                    "- It must feel doable even during a stressful week.\n"
                    "- No big deadlines, no giant projects, no unrealistic workload.\n"
                    "- It should be something the user can complete in 3–5 tiny sessions.\n"
                    "- Tone must be warm, soft, encouraging.\n"
                    "\n"
                    "FORMAT (STRICT JSON):\n"
                    "{\n"
                    "  name: string,\n"
                    "  note: string,\n"
                    "  weeklyTarget: string\n"
                    "}\n"
                    "\n"
                    "Examples of good soft mountains:\n"
                    "- \"Create one small portfolio improvement\"\n"
                    "- \"Learn the basics of one Express concept\"\n"
                    "- \"Do gentle progress on LinkedIn presence\"\n"
                    "- \"Prepare one clean resume section\"\n"
                    "\n"
                    "The note must feel like a supportive friend.\n"
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
# 3) DAILY SWEETSTEPS — FINAL MICRO-STEPS VERSION
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
                            "You generate today's Daily SweetSteps in JSON format.\n"
                            "Your job: help the user make REAL progress without feeling overwhelmed.\n"
                            "\n"
                            "Every task MUST be tiny, gentle, and easy to start.\n"
                            "\n"
                            "RULES:\n"
                            "1. Tasks must be ATOMIC (one small action only).\n"
                            "2. Tasks must be 5–20 minutes (MAX 30).\n"
                            "3. Never give giant study sessions, big goals, or multi-step tasks.\n"
                            "4. Everything must feel emotionally safe.\n"
                            "5. Tasks must be SPECIFIC and ACTIONABLE.\n"
                            "6. Tone must be warm + encouraging + cute.\n"
                            "7. Output STRICT JSON:\n"
                            "{\n"
                            "  tasks: [\n"
                            "    { title: string, description: string, estimatedMinutes: number }\n"
                            "  ],\n"
                            "  coachNote: string\n"
                            "}\n"
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

    # Attempt 1
    out = ask()

    # Retry if malformed
    if out is None or "tasks" not in out:
        print("Retrying Groq once…")
        out = ask()

    # Hard fallback
    if out is None or "tasks" not in out:
        return jsonify({
            "tasks": [
                {
                    "title": "Tiny Warm-up",
                    "description": "Take 5 minutes to gently start moving toward your mountain.",
                    "estimatedMinutes": 5
                },
                {
                    "title": "Small Progress",
                    "description": "Take one tiny actionable step toward your big goal.",
                    "estimatedMinutes": 15
                }
            ],
            "coachNote": "Fallback activated — even tiny steps count!"
        }), 200

    return jsonify(out)

# ----------------------------------------------------------
# HEALTH CHECK
# ----------------------------------------------------------
@app.get("/")
def health():
    return {"status": "alive"}, 200
