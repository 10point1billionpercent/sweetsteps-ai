from flask import Flask, request, jsonify
import os
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"


# ---------------------------------------------------------
#  HELPER FUNCTION: call Groq API
# ---------------------------------------------------------
def groq_chat(system_prompt, user_prompt):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }

    body = {
        "model": MODEL,
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    }

    res = requests.post(GROQ_URL, headers=headers, json=body)
    data = res.json()

    try:
        return json_safe(data["choices"][0]["message"]["content"])
    except:
        return {"error": "Groq response parsing failed", "raw": data}


# ---------------------------------------------------------
#  SAFE JSON PARSE (Groq returns JSON in a string)
# ---------------------------------------------------------
import json
def json_safe(s):
    try:
        return json.loads(s)
    except:
        return {"error": "Invalid JSON from Groq", "raw": s}


# ---------------------------------------------------------
# 1. ONBOARDING: bigGoal + sample weekly + sample SweetStep
# ---------------------------------------------------------
@app.route("/onboarding-plan", methods=["POST"])
def onboarding_plan():
    data = request.json
    vagueGoal = data.get("vagueGoal", "")
    currentProgress = data.get("currentProgress", "")
    timeLimit = data.get("timeLimit", "")

    system_prompt = (
        "You are the Swiss Chocolate Coach. Convert vague goals into a clear big goal, "
        "then generate one sample weekly mountain (without tasks) and one sample daily SweetStep. "
        "Return ONLY JSON:\n"
        "{ bigGoal, weeklyMountain: { name, weeklyTarget, note }, dailyStep }"
    )

    user_prompt = (
        f"Vague Goal: {vagueGoal}\n"
        f"Current Progress: {currentProgress}\n"
        f"Time Limit: {timeLimit}"
    )

    return jsonify(groq_chat(system_prompt, user_prompt))


# ---------------------------------------------------------
# 2. WEEKLY MOUNTAIN (first real weekly mountain)
# ---------------------------------------------------------
@app.route("/weekly-mountain", methods=["POST"])
def weekly_mountain():
    data = request.json
    bigGoal = data.get("bigGoal", "")

    system_prompt = (
        "Generate the FIRST weekly mountain for the user's big goal. "
        "Return ONLY JSON with keys: { name, weeklyTarget, note }"
    )

    user_prompt = f"Big Goal: {bigGoal}"

    return jsonify(groq_chat(system_prompt, user_prompt))


# ---------------------------------------------------------
# 3. DAILY SWEETSTEPS (must use bigGoal + weeklyMountain)
# ---------------------------------------------------------
@app.post("/daily-steps")
def generate_daily_steps():
    data = request.json
    big_goal = data.get("big_goal")
    weekly_mountain = data.get("weekly_mountain")   # string or object, both fine

    if not big_goal or not weekly_mountain:
        return jsonify({"error": "big_goal and weekly_mountain required"}), 400

    def call_groq_once():
        try:
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                temperature=0.7,
                response_format={"type": "json_object"},   # FORCE STRICT JSON
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Generate today's micro-steps based on BOTH the user's big_goal "
                            "AND their weekly_mountain. Respond ONLY in a JSON object with:\n"
                            "steps: array of { title, description, minutes }\n"
                            "coachNote: string\n"
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

            raw = completion.choices[0].message.content
            return json.loads(raw)

        except Exception as e:
            print("Groq parse error:", e)
            return None

    # ----- FIRST ATTEMPT -----
    result = call_groq_once()

    # ----- RETRY ON BAD JSON -----
    if result is None:
        print("Retrying Groq due to invalid JSON…")
        result = call_groq_once()

        if result is None:
            return jsonify({
                "error": "Groq sent invalid JSON twice",
                "fallback": {
                    "steps": [
                        {"title": "Warmup step", "description": "Start gently", "minutes": 5},
                        {"title": "Progress step", "description": "Move your goal forward", "minutes": 10},
                        {"title": "Wrap-up step", "description": "Close the loop", "minutes": 5},
                    ],
                    "coachNote": "Let's keep moving at a gentle pace!"
                }
            }), 500

    return jsonify(result)

# ---------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return {"status": "SweetSteps AI Proxy running"}


# ---------------------------------------------------------
# RUN
# ---------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)