import os
import re
import json
import requests
import time 
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_groq import ChatGroq
from flask import Blueprint, request, jsonify, render_template ,Response , send_file
from PyPDF2 import PdfReader
import pandas as pd
from datetime import datetime

resume_bp = Blueprint('resume', __name__, url_prefix='/resume')

# Paths
BASE_DIR = os.getcwd()
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads', 'resume_uploads')
RUBRIC_DIR = os.path.join(BASE_DIR, 'Rubrics')

os.makedirs(UPLOAD_DIR, exist_ok=True)

# Groq API setup
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# PDF text extraction
def extract_text_from_pdf(fp):
    try:
        reader = PdfReader(fp)
        return "\n".join(page.extract_text() or '' for page in reader.pages)
    except Exception as e:
        return f"Error reading PDF: {str(e)}"



# List available rubrics
@resume_bp.route('/rubrics', methods=['GET'])
def list_rubrics():
    try:
        files = [f[:-5] for f in os.listdir(RUBRIC_DIR) if f.endswith('.json')]
        return jsonify(files)
    except Exception as e:
        return jsonify(error=f"Failed to list rubrics: {str(e)}"), 500


# New endpoint for batch processing of multiple resumes against selected rubrics


@resume_bp.route('/langchain-stream', methods=['POST'])
def langchain_stream():
    resumes = request.files.getlist('resumes')
    rubric_names = request.form.getlist('rubric_names[]')
    if not rubric_names or not resumes:
        return {"error": "Rubric(s) and resumes required"}, 400


    rubrics = {}
    for name in rubric_names:
        path = os.path.join(RUBRIC_DIR, f"{name}.json")
        if not os.path.exists(path):
            return {"error": f"Rubric not found: {name}"}, 400
        with open(path) as f:
            rubrics[name] = json.load(f)

    


    resume_data = {}
    for resume in resumes:
        resume_data[resume.filename] = resume.read()

    # LangChain Groq setup
    llm = ChatGroq(
        model_name="deepseek-r1-distill-llama-70b",  # or your chosen Groq model
        api_key=GROQ_API_KEY,
        streaming=True,
    )
    system_template = """
    You are a strict and careful resume evaluator. Use the rubric below to assess whether each resume in a batch meets the stated job requirements.
    Rubrics:
    {rubric}
    Each rubric contains:
    - "must_have": mandatory qualifications (e.g., degree type, specialization, institution recognition)
    - "optional": preferred but not required qualifications
    - "experience": expected teaching or industry experience
    - "notes": age limits, required registrations, or certifications
    ---
    Your task is to evaluate each resume **against its relevant rubric** and return a JSON object with this structure for each resume:

    {{
    "filename": "<original_filename>.pdf",
    "verdict": "Accepted", "Rejected", or "Unclear",
    "reasons": [
        "Clearly state the reasoning behind the verdict. Include missing, incomplete, or ambiguous points."
    ]
    }}
    ---
    ✅ VERDICT GUIDELINES:
    - **Accepted**:
    - All "must_have" criteria are explicitly mentioned and matched in the resume.
    - Closely matching field names are acceptable (e.g., "AI" ≈ "Artificial Intelligence", "ML" ≈ "Machine Learning").
    - Minor variation in formatting or synonyms is acceptable if the meaning is unambiguous.
    - **Unclear**:
    - Resume mentions a degree (e.g., MS) but doesn’t specify if it's **First Division**.
    - The **HEC recognition** or **PEC registration** is not explicitly stated or implied.
    - A relevant degree is present but the **specialization/field is vaguely worded** or ambiguous.
    - Any required experience is partially stated, unclear, or inferred but not explicitly mentioned.
    - **Rejected**:
    - Important "must_have" fields are **clearly missing or contradicted**.
    - Degree level does not meet the required threshold (e.g., only a BS when MS/PhD is required).
    - Resume explicitly states a disqualifying condition (e.g., "3rd Division").
   ---
    📌 FORMAT RULES:
    - Return a valid **JSON array** of such resume evaluations.
    - Do **not** include markdown formatting, code blocks, or extra commentary.
    - Do **not** group resumes — return one JSON object per resume, each inside the array.
    ---
    Example:
    [
    {{
        "filename": "john_cv.pdf",
        "verdict": "Unclear",
        "reasons": [
        "MS is mentioned but division is not specified",
        "Degree field stated as 'Data Technology', unclear if it matches 'Data Science'",
        "No mention of HEC recognition"
        ]
    }}, 
    {{ ... }}
    ]
    ---
    Begin evaluation with the following batch of resumes:
    """

    system_message = SystemMessagePromptTemplate.from_template(system_template)

    human_template = "Evaluate the following batch of resumes:\n\n{resumes}"  # resumes will be a stringified list of dicts
    human_message = HumanMessagePromptTemplate.from_template(human_template)


    prompt = ChatPromptTemplate.from_messages([system_message, human_message])
    chain = prompt | llm 
    
    def event_stream(rubric_names):
        results_accumulator = []
        filenames = list(resume_data.keys())
        if isinstance(rubric_names, str):
            try:
                rubric_names = json.loads(rubric_names)
            except Exception:
                rubric_names = [rubric_names]
        batch_size = 1 if len(rubric_names) > 1 else 2

        # Group filenames into batches of 5
        for i in range(0, len(filenames), batch_size):
            batch = filenames[i:i + batch_size]
            batch_items = []

            # Extract and prepare resume data
            for filename in batch:
                try:
                    file_bytes = resume_data[filename]
                    save_path = os.path.join(UPLOAD_DIR, filename)
                    with open(save_path, 'wb') as f:
                        f.write(file_bytes)

                    with open(save_path, 'rb') as f:
                        text = extract_text_from_pdf(f)

                    batch_items.append({
                        "filename": filename,
                        "resume": text
                    })

                    # Notify frontend this file has started processing
                    yield f"data: {json.dumps({'filename': filename, 'status': 'start'})}\n\n"

                except Exception as e:
                    yield f"data: {json.dumps({'filename': filename, 'error': str(e)})}\n\n"

            if not batch_items:
                continue  # skip empty batches

            # Prepare stringified batch JSON
            batch_payload = json.dumps(batch_items)

            response = ""
            try:
                for chunk in chain.stream({
                    "rubric": json.dumps(rubrics),
                    "resumes": batch_payload
                }):
                    response += chunk.content
                    # You could stream partials here if needed per batch

                # Try parsing JSON array of responses
                matches = re.search(r"\[\s*{[\s\S]*?}\s*]", response)


                if matches:
                    parsed_array = json.loads(matches.group(0))
                    for result in parsed_array:
                        yield f"data: {json.dumps({
                            'filename': result.get('filename'),
                            'verdict': result.get('verdict'),
                            'reasons': result.get('reasons', [])
                        })}\n\n"
                        results_accumulator.append({
                            "CV Name": result.get("filename"),
                            "Verdict": result.get("verdict"),
                            "Reasons": "\n".join(result.get("reasons", [])),
                            "Rubric Name": ", ".join(rubric_names)

                        })
                else:
                    # Fallback: cannot parse array
                    for item in batch_items:
                        yield f"data: {json.dumps({
                            'filename': item['filename'],
                            'verdict': 'Rejected',
                            'reasons': ['Could not parse JSON from model response']
                        })}\n\n"


            

            except Exception as e:
                for item in batch_items:
                    yield f"data: {json.dumps({'filename': item['filename'], 'error': str(e)})}\n\n"

        report_dir = os.path.join(BASE_DIR, 'uploads', 'reports')
        os.makedirs(report_dir, exist_ok=True)

        filename = f"resume_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        excel_path = os.path.join(report_dir, filename)

        df = pd.DataFrame(results_accumulator)
        df.to_excel(excel_path, index=False)

        yield f"data: {json.dumps({'download_link': f'/resume/download-report/{filename}'})}\n\n"
        yield "event: end\ndata: done\n\n"





    return Response(event_stream(rubric_names=rubric_names), mimetype='text/event-stream')


@resume_bp.route('/download-report/<filename>', methods=['GET'])
def download_report(filename):
    report_path = os.path.join(BASE_DIR, 'uploads', 'reports', filename)
    if not os.path.exists(report_path):
        return "File not found", 404
    return send_file(report_path, as_attachment=True)

# Route for the main page
@resume_bp.route('/', methods=['GET'])
def index():
    return render_template('index.html')


