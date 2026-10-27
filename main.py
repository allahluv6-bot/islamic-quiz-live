import time
import json
import os

def load_questions():
    if os.path.exists("questions.json"):
        with open("questions.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def run_quiz_bot():
    questions = load_questions()
    if not questions:
        print("No questions found!")
        return

    print("AhadZ9 Aesthetic Islamic Quiz Bot Initialized successfully!")
    while True:
        for q in questions:
            print(f"\n[Q#{q['id']}] {q['question']}")
            for opt in q['options']:
                print(f"  {opt}")
            print(f"Correct Answer: {q['answer']}")
            time.sleep(15)

if __name__ == "__main__":
    run_quiz_bot()
  
