from flask import Flask, request, jsonify
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def call_groq(system_prompt, user_prompt):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }

    body = {
        "model": "llama-3.1-8b-instant",
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    }

    resp = requests.post(GROQ_URL, json=body, headers=headers)
    data = resp.json()

    try:
        return json.loads(data["choices"][0]["message"]["content"])
    except:
        return None


@app.post("/onboarding-plan")
def onboarding_plan():
    data = request.json
    vague = data.get("vagueGoal", "")
    clar = data.get("clarifications", [])

    system_prompt = (
        "You are the Swiss Chocolate Coach. Convert vague goals into a clear big goal, "
        "then create ONE sample weekly mountain and ONE sample daily step. "
        "Respond ONLY in JSON with keys: "
        "bigGoal, weeklyMountain{name, weeklyTarget, note}, dailyStep."
    )

    user_prompt = f"Vague Goal: {vague}\nClarifications:\n- " + "\n- ".join(clar)

    result = call_groq(system_prompt, user_prompt)
    return jsonify(result or {})


@app.post("/weekly-mountain")
def weekly_mountain():
    data = request.json
    big = data.get("bigGoal", "")

    system_prompt = (
        "Generate this week's mountain ONLY as JSON with keys: "
        "name, weeklyTarget, note."
    )

    user_prompt = f"Big goal: {big}"

    result = call_groq(system_prompt, user_prompt)
    return jsonify(result or {})


@app.post("/daily-steps")
def daily_steps():
    data = request.json
    big = data.get("bigGoal", "")

    # CHANGED ONLY THIS PROMPT
    system_prompt = (
        "Generate today's micro-steps as a LIST. Respond ONLY in JSON with key: "
        "steps: [ { task: string, time: number_in_minutes } ]. "
        "Generate 3 to 6 tasks. Time should be an integer like 10, 15, 20."
    )

    user_prompt = f"Big goal: {big}"

    result = call_groq(system_prompt, user_prompt)
    return jsonify(result or {})


if __name__ == "__main__":
    app.run()