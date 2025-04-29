

# **ResumeRubric AI** 🧠📄  
An intelligent resume evaluator that checks candidate resumes against multiple job-specific rubrics using LLMs via the Groq API.

---

## 🚀 Overview

**ResumeRubric AI** automates resume evaluation at scale. Upload multiple resumes and compare them against customizable hiring rubrics. It uses state-of-the-art language models (like `deepseek-r1-distill-llama-70b`) via LangChain & Groq for fast, AI-powered analysis and verdicts.

---

## 🔧 Features

- 📥 Batch resume uploads (up to 10 at a time)
- 📋 Supports multiple rubrics per evaluation
- 🧠 Uses advanced LLMs (Groq-hosted DeepSeek) via LangChain
- 📊 Verdict: `Accepted`, `Unclear`, or `Rejected` — with reasons
- 📎 Generates downloadable Excel reports
- 📤 Real-time streaming feedback to frontend
- 🧾 Rubric extraction from job ads supported (via additional endpoint)

---

## ⚠️ Limitations

- ❗ **Max resume size**: ~2000 words per resume (due to token limits in the LLM API)
- ⚙️ Best performance when evaluating **up to 10 resumes at once**
- 📌 Resume formats supported: **PDF only**
- 🌐 Requires stable internet for LLM API calls (Groq API)

---

## 🛠️ Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/zainkazmi786/ResumeRubric-AI.git
cd ResumeRubric-ai
```

### 2. Create and Activate a Virtual Environment
```bash
python -m venv myenv
myenv\Scripts\activate.ps1 # `source myenv/bin/activate` on Linux
```

### 3. Install Requirements
```bash
pip install -r requirements.txt
```

### 4. Create a `.env` File

In the root directory, create a `.env` file and add your **Groq API key**:
```env
GROQ_API_KEY=your_actual_groq_api_key
```

---

## ▶️ Running the App

### Start the Flask server:
```bash
python app.py
```

- Navigate to `http://127.0.0.1:5000` in your browser.
- Upload resumes and select rubrics for evaluation.

---

## 📁 Folder Structure

```
resume_checker/
├── uploads/
│   ├── resume_uploads/
│   └── reports/
├── Rubrics/
├── templates/
│   └── index.html
├── static/
│   └── scripts.js
├── resume_bp.py
├── rubric_bp.py
├── app.py
├── requirements.txt
└── .env  ← create this yourself
```

---

## 📎 Suggested Rubric Format

Each rubric should be a `.json` file containing job criteria, for example:

```json
{
  "must_have": [
    "PhD from HEC recognized Institution",
    "Field: Artificial Intelligence, Cyber Security"
  ],
  "optional": ["BS in Computer Science"],
  "experience": ["3 years teaching experience"],
  "notes": ["PEC registration", "Age limit: 40"]
}
```

---

