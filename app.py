import os
import re

from flask import Flask, render_template, request
from pypdf import PdfReader
from google import genai

app = Flask(__name__)

GEMINI_API_KEY = "YOUR_API_KEY_HERE"

client = genai.Client(api_key=GEMINI_API_KEY)

generated_questions = []
current_question = 0
total_score = 0
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def extract_text_from_pdf(file_path):

    text = ""

    reader = PdfReader(file_path)

    for page in reader.pages:
        text += page.extract_text() or ""

    return text

def calculate_ats_score(resume_text):

    keywords = [
        "python",
        "java",
        "c++",
        "sql",
        "html",
        "css",
        "javascript",
        "flask",
        "django",
        "machine learning",
        "communication",
        "teamwork",
        "problem solving",
        "excel",
        "power bi",
        "tableau",
        "pandas",
        "numpy"
    ]

    text = resume_text.lower()

    found = []
    missing = []

    for keyword in keywords:

        if keyword in text:
            found.append(keyword)
        else:
            missing.append(keyword)

    score = int((len(found) / len(keywords)) * 100)

    return score, found, missing


def analyze_resume_with_ai(resume_text):

    prompt = f"""
You are an ATS Resume Analyzer.

Analyze this resume and provide:

1. Resume Summary
2. Strengths
3. Weaknesses
4. Missing Skills
5. Suggestions for Improvement

Resume:

{resume_text}
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        feedback = response.text if hasattr(response, "text") else str(response)

        return feedback

    except Exception as e:
        return f"Error: {e}"
def generate_questions(job_description, resume_text):
    prompt = f"""
You are an experienced technical interviewer.

Generate exactly 10 interview questions.

Format your response EXACTLY like this:

Question 1:
...

Question 2:
...

Question 3:
...

Question 4:
...

Question 5:
...

Question 6:
...

Question 7:
...

Question 8:
...

Question 9:
...

Question 10:
...

Rules:
- One question per line.
- Leave one blank line between questions.
- Do NOT write paragraphs.
- Do NOT explain the questions.
- Do NOT use markdown.

Job Description:
{job_description}

Resume:
{resume_text}
"""

    global current_question
    global generated_questions

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        questions = response.text.replace("Question", "\nQuestion")

        generated_questions = re.findall(
            r"Question\s+\d+:\s*(.*?)(?=Question\s+\d+:|$)",
            response.text,
            re.DOTALL
        )

        generated_questions = [q.strip() for q in generated_questions]
        current_question = 0

        return questions
    except Exception:
        return "⚠ AI service is temporarily unavailable."

@app.route("/")
def home():

    return render_template("index.html")
@app.route("/upload", methods=["POST"])
def upload():

    if "resume" not in request.files:
        return "No file uploaded."

    file = request.files["resume"]

    if file.filename == "":
        return "Please select a PDF file."

    job_description = request.form.get("job_description", "")

    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    resume_text = extract_text_from_pdf(filepath)
    if not resume_text.strip():
        return "Could not extract any text from the uploaded PDF. Please upload a text-based PDF."

    score, found, missing = calculate_ats_score(resume_text)

    ai_feedback = analyze_resume_with_ai(resume_text)

    questions = generate_questions(job_description, resume_text)

    return render_template(
        "index.html",
        text=resume_text,
        score=score,
        found=found,
        missing=missing,
        ai_feedback=ai_feedback,
        questions=questions
    )

@app.route("/interview")
def interview():

    global generated_questions
    global current_question

    if len(generated_questions) == 0:
        question = "Tell me about yourself."
        total = 1
    else:
        question = generated_questions[current_question]
        total = len(generated_questions)

    return render_template(
        "interview.html",
        question=question,
        current=current_question,
        total=total
    )
@app.route("/evaluate", methods=["POST"])
def evaluate():
    global current_question, generated_questions, total_score

    question = request.form["question"]
    answer = request.form["answer"]

    prompt = f"""
You are an expert technical interviewer.

Evaluate the candidate's answer.

Question:
{question}

Answer:
{answer}

Give the response in this format:

Score: X/10

Strengths:
- ...

Weaknesses:
- ...

Suggestions:
- ...

Ideal Answer:
...
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        feedback = response.text if hasattr(response, "text") else str(response)

        match = re.search(r"Score:\s*(\d+)", feedback)

        if match:
            total_score += int(match.group(1))

    except Exception:
        feedback = "⚠ AI Interview Feedback is temporarily unavailable."

    # Move to the next question
    if current_question < len(generated_questions) - 1:
        current_question += 1

        return render_template(
            "result.html",
            question=question,
            answer=answer,
            feedback=feedback,
            next_question=True
        )
    else:
        return render_template(
            "final_result.html",
            score=total_score,
            total=10 * len(generated_questions)
        )
if __name__ == "__main__":
    app.run(debug=True)