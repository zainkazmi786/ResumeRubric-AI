import os, json, requests
import re
from flask import Blueprint, request, jsonify, render_template
from PyPDF2 import PdfReader

rubric_bp = Blueprint('rubric', __name__, url_prefix='/rubric')

def safe_filename(name):
    """Remove unsafe characters from file names."""
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name)

# Configuration
UPLOAD_DIR = os.path.join(os.getcwd(), 'uploads', 'rubric_uploads')
RUBRIC_DIR = os.path.join(os.getcwd(), 'Rubrics')
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RUBRIC_DIR, exist_ok=True)  # Ensure Rubrics directory exists

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"  # or "mixtral-8x7b", "llama3-70b-8192", etc.

def extract_text_from_pdf(fp):
    reader = PdfReader(fp)
    return "\n".join(page.extract_text() or '' for page in reader.pages)

def call_groq_api(prompt):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            { "role": "user", "content": prompt }
        ],
        "temperature": 0.0
    }
    
    response = requests.post(GROQ_API_URL, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

@rubric_bp.route('/', methods=['POST'])
def upload_rubric():
    name = request.form.get('name')
    file = request.files.get('rubric')
    if not name or not file:
        return jsonify(status='Name and file are required'), 400

    raw_path = os.path.join(UPLOAD_DIR, f"{name}_raw.pdf")
    file.save(raw_path)

    with open(raw_path, 'rb') as f:
        text = extract_text_from_pdf(f)

    prompt = f"""
    You are a highly precise assistant. Your task is to extract a detailed hiring rubric from the following faculty advertisement text.

    You must strictly output a **valid JSON object** with the following structure and rules:

    🔹 Top-level keys = Exact Job Titles as written (e.g., "Assistant Professor - School of Computing Sciences")

    🔹 For each job title, include:

    - "must_have": [
    A list of mandatory qualifications. Use structured phrases like:
    - "Degree: PhD or MS (First Division, 18 years of education) from an HEC recognized Institution"
    - "Field of study must be one of: Artificial Intelligence, Data Science, Cyber Security"
    ]

    - "optional": [
    A list of preferred (but not mandatory) qualifications, degrees, certifications, or fields.
    Prefix these with "Preferred:" or "Recommended:" to make it explicit.
    ]

    - "experience": [
    Specific teaching or industry experience, e.g.,
    - "3 years university teaching experience in relevant field"
    - "5 years professional R&D experience"
    ]

    - "notes": [
    Any extra conditions such as:
    - "Age limit: 40 years"
    - "PEC registration required"
    - "HEC recognized degree mandatory"
    - "No 3rd Division allowed in academic record"
    ]

    📌 Extraction Instructions:

    - Map degree names precisely. Capture combinations like "PhD or First Division MS" accurately.
    - List all specializations as written. Do not shorten field names (e.g., use "Robotics and Automation" not just "Robotics").
    - If both Assistant Professor and Lecturer are grouped, split into two separate keys using job titles as written.
    - If teaching/research experience is stated as an alternative depending on degree level, list both in the "experience" array.

    ⚠️ OUTPUT FORMAT:

    - Return only a valid JSON object.

    ---

    ✅ Sample Output Format:

    {{
    "Assistant Professor - Artificial Intelligence": {{
        "must_have": [
        "Degree: PhD or First Division MS (18 years) from HEC recognized Institution",
        "Field of study must be one of: Artificial Intelligence, Machine Learning"
        ],
        "optional": [
        "Preferred: BS in Computer Science or Software Engineering",
        "Recommended: Certification in Data Analytics"
        ],
        "experience": [
        "2 years university-level teaching experience"
        ],
        "notes": [
        "Age limit: 40 years",
        "PEC registration required"
        ]
    }},
    "Lecturer - Computing Sciences": {{
        "must_have": [
        "Degree: MS (First Division, 18 years) from HEC recognized Institution",
        "Field of study must be one of: Cyber Security, Data Sciences"
        ],
        "optional": [],
        "experience": [],
        "notes": [
        "No 3rd Division allowed throughout academic career",
        "Age limit: 35 years"
        ]
    }}
    }}

    ---

    Here is the advertisement text:

    {text}
    """



    try:
        response_content = call_groq_api(prompt)
        print("GROQ Response:\n", response_content)

        rubric_data = json.loads(response_content)

    except json.JSONDecodeError:
        print("Initial JSON decode failed. Attempting regex fallback...")

        # Match content within ```json ... ```
        json_match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", response_content)
        if json_match:
            cleaned_json = json_match.group(1)
            try:
                rubric_data = json.loads(cleaned_json)
            except json.JSONDecodeError as e:
                print("Regex JSON decode also failed.")
                print("✖️ GROQ Response (trimmed):\n", cleaned_json[:500])
                return jsonify(status=f'Failed to parse rubric JSON: {str(e)}'), 500
        else:
            # Try to match any JSON-like structure
            json_match = re.search(r"\{[\s\S]*?\}", response_content)
            if json_match:
                cleaned_json = json_match.group(0)
                try:
                    rubric_data = json.loads(cleaned_json)
                except json.JSONDecodeError as e:
                    print("✖️ Final JSON decode also failed.")
                    print("GROQ Raw Response:\n", response_content)
                    return jsonify(status=f'Failed to parse rubric JSON: {str(e)}'), 500
            else:
                print("✖️ No JSON block matched.")
                print("GROQ Raw Response:\n", response_content)
                return jsonify(status='No JSON object found in model response'), 500
    except requests.RequestException as e:
        return jsonify(status=f'Groq API error: {str(e)}'), 500

    # Save each rubric (per job) as separate file
    saved = []
    for job_title, rubric in rubric_data.items():
        clean_name = safe_filename(job_title.replace(' - ', '_').replace(' ', '_'))
        filename = f"{name}_{clean_name}.json"
        full_path = os.path.join(RUBRIC_DIR, filename)
        with open(full_path, 'w') as f:
            json.dump(rubric, f, indent=2)
        saved.append(filename)

    return jsonify(status='Rubrics saved', files=saved)

@rubric_bp.route('/list', methods=['GET'])
def list_rubrics():
    files = [f[:-5] for f in os.listdir(RUBRIC_DIR) if f.endswith('.json')]
    return jsonify(files)