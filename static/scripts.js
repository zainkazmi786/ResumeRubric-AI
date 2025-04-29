// DOM Elements
const navResume = document.getElementById('navResume');
const navRubric = document.getElementById('navRubric');
const resumeChecker = document.getElementById('resumeChecker');
const rubricManager = document.getElementById('rubricManager');
const rubricCheckboxes = document.getElementById('rubricCheckboxes');
const resumeForm = document.getElementById('resumeForm');
const rubricForm = document.getElementById('rubricForm');
const resumeFiles = document.getElementById('resumeFiles');
const rubricFile = document.getElementById('rubricFile');
const rubricName = document.getElementById('rubricName');
const statusMessage = document.getElementById('statusMessage');
const rubricStatusMessage = document.getElementById('rubricStatusMessage');
const resultsContainer = document.getElementById('resultsContainer');
const savedRubrics = document.getElementById('savedRubrics');

// Base URL - changed to relative path for Flask integration
const API_URL = '';

// Navigation
navResume.addEventListener('click', () => {
  navResume.classList.add('active');
  navRubric.classList.remove('active');
  resumeChecker.classList.add('active-section');
  rubricManager.classList.remove('active-section');
});

navRubric.addEventListener('click', () => {
  console.log("clicked")
  navRubric.classList.add('active');
  navResume.classList.remove('active');
  rubricManager.classList.add('active-section');
  resumeChecker.classList.remove('active-section');
});

// File input display
resumeFiles.addEventListener('change', updateFileInfo);
rubricFile.addEventListener('change', updateFileInfo);

function updateFileInfo(e) {
  const fileInfoEl = e.target.nextElementSibling;
  const files = e.target.files;
  
  if (files.length === 0) {
    fileInfoEl.textContent = 'No files selected';
  } else if (files.length === 1) {
    fileInfoEl.textContent = `Selected: ${files[0].name}`;
  } else {
    fileInfoEl.textContent = `Selected ${files.length} files`;
  }
}

// Load rubrics
async function loadRubrics() {
  try {
    const responses = await Promise.all([
      fetch(`${API_URL}/resume/rubrics`),
      fetch(`${API_URL}/rubric/list`)
    ]);
    
    const [resumeRubrics, rubricList] = await Promise.all(
      responses.map(res => res.json())
    );
    
    // Update rubric checkboxes
    rubricCheckboxes.innerHTML = '';
    if (resumeRubrics.length === 0) {
      rubricCheckboxes.innerHTML = '<p>No rubrics available</p>';
    } else {
      function formatRubricLabel(rubric) {
        const parts = rubric.split('_');
        const prefix = parts.shift(); // e.g., "PAFIAST"
        const rest = parts.join(' ').replace(/\bof\b/g, 'of'); // preserve "of" lowercase if needed
        return `${rest} - ${prefix}`;
      }
      resumeRubrics.forEach(rubric => {
        const checkboxItem = document.createElement('div');
        checkboxItem.className = 'checkbox-item';
        checkboxItem.innerHTML = `
          <input type="checkbox" id="rubric-${rubric}" name="rubrics" value="${rubric}">
          <label for="rubric-${rubric}">${formatRubricLabel(rubric)}</label>
        `;
        rubricCheckboxes.appendChild(checkboxItem);
      });
    }
    
    // Update saved rubrics list
    savedRubrics.innerHTML = '';
    if (rubricList.length === 0) {
      savedRubrics.innerHTML = '<li>No rubrics uploaded yet</li>';
    } else {
      rubricList.forEach(rubric => {
        const listItem = document.createElement('li');
        listItem.textContent = rubric;
        savedRubrics.appendChild(listItem);
      });
    }
  } catch (error) {
    console.error('Error loading rubrics:', error);
    rubricCheckboxes.innerHTML = '<p class="error">Failed to load rubrics</p>';
    savedRubrics.innerHTML = '<li class="error">Failed to load rubrics</li>';
  }
}

// Submit resume form
resumeForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  document.getElementById('excelDownload').style.display = 'none';
  document.getElementById('excelDownload').innerHTML = '';


  resultsContainer.innerHTML = '';
  showMessage(statusMessage, 'Checking resumes...', 'info');

  const selectedRubrics = Array.from(
    document.querySelectorAll('input[name="rubrics"]:checked')
  ).map(el => el.value);
  
  const files = resumeFiles.files;
  
  if (selectedRubrics.length === 0 || files.length === 0) {
    showMessage(statusMessage, 'Please select at least one rubric and upload resumes.', 'error');
    return;
  }
  
  const formData = new FormData();
  selectedRubrics.forEach(rubric => {
    formData.append('rubric_names[]', rubric);  // key matches Flask: request.form.getlist('rubric_names[]')
  });
  Array.from(files).slice(0, 10).forEach(file => {
    formData.append('resumes', file);
  });

  try {
    const response = await fetch(`${API_URL}/resume/langchain-stream`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok || !response.body) throw new Error("Streaming error");

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    const resultBoxes = {};
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop(); // keep incomplete part

      for (const chunk of parts) {
        if (!chunk.startsWith("data: ")) continue;

        const raw = chunk.replace("data: ", "").trim();
        if (!raw) continue;

        const data = JSON.parse(raw);
        const { filename, status, partial, verdict, reasons, error } = data;
        if (data.download_link) {
          const excelDiv = document.getElementById('excelDownload');
          excelDiv.style.display = 'block';
          excelDiv.innerHTML = `
            <a href="${data.download_link}" class="btn btn-success" download>
              ⬇ Download Excel Report
            </a>
          `;
        }

        if (filename && !resultBoxes[filename]) {
          const box = document.createElement('div');
          box.id = `res-${filename}`;
          box.className = 'result-box';
          box.innerHTML = `<h3>${filename}</h3><div class="result-body"><p class="status">Starting...</p></div>`;
          resultsContainer.appendChild(box);
          resultBoxes[filename] = box.querySelector('.result-body');
        }

        const container = resultBoxes[filename];

        if (status === "start") {
          container.querySelector('.status').textContent = "Evaluating...";
        }

        if (partial) {
          let p = container.querySelector('.stream') || document.createElement('pre');
          p.className = 'stream';
          p.textContent += partial;
          container.appendChild(p);
        }

        if (verdict) {
          container.innerHTML = `
            <p><strong>Verdict:</strong> ${verdict}</p>
            <ul>${(reasons || []).map(reason => `<li>${reason}</li>`).join('')}</ul>
          `;
        }

        if (error) {
          container.innerHTML = `<p class="error">❌ ${error}</p>`;
        }
      }
    }

    showMessage(statusMessage, 'Resume evaluation completed.', 'success');

  } catch (err) {
    console.error(err);
    showMessage(statusMessage, `Error: ${err.message}`, 'error');
  }
});


// Submit rubric form
rubricForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const name = rubricName.value.trim();
  const file = rubricFile.files[0];
  
  if (!name || !file) {
    showMessage(rubricStatusMessage, 'Please enter a name and select a file', 'error');
    return;
  }
  
  showMessage(rubricStatusMessage, 'Uploading...', 'info');
  
  const formData = new FormData();
  formData.append('name', name);
  formData.append('rubric', file);
  
  try {
    const response = await fetch(`${API_URL}/rubric`, {
      method: 'POST',
      body: formData
    });
    
    const data = await response.json();
    
    if (response.ok) {
      showMessage(rubricStatusMessage, `✅ ${data.status}`, 'success');
      rubricName.value = '';
      rubricFile.value = '';
      rubricFile.nextElementSibling.textContent = 'No file selected';
      
      // Reload rubrics
      loadRubrics();
    } else {
      showMessage(rubricStatusMessage, `❌ ${data.status}`, 'error');
    }
  } catch (error) {
    console.error('Error uploading rubric:', error);
    showMessage(rubricStatusMessage, `Error: ${error.message}`, 'error');
  }
});

// Helper function to show messages
function showMessage(element, message, type = 'info') {
  element.textContent = message;
  element.className = 'status-message';
  element.classList.add(type);
  
  // Auto hide success messages after 5 seconds
  if (type === 'success') {
    setTimeout(() => {
      element.textContent = '';
      element.className = 'status-message';
    }, 5000);
  }
}

// Display results
function displayResults(results) {
  resultsContainer.innerHTML = '';
  
  if (results.length === 0) {
    resultsContainer.innerHTML = '<p>No results to display</p>';
    return;
  }
  
  // Group results by filename
  const resultsByFile = {};
  
  results.forEach(result => {
    if (!resultsByFile[result.filename]) {
      resultsByFile[result.filename] = [];
    }
    resultsByFile[result.filename].push(result);
  });
  
  // Create result items
  for (const [filename, fileResults] of Object.entries(resultsByFile)) {
    const resultItem = document.createElement('div');
    resultItem.className = 'result-item';
    
    // Determine overall verdict
    const allAccepted = fileResults.every(r => r.verdict.toLowerCase() === 'accepted');
    if (allAccepted) {
      resultItem.classList.add('accepted');
    } else {
      resultItem.classList.add('rejected');
    }
    
    // Create header
    const header = document.createElement('h4');
    header.innerHTML = `
      ${filename} 
      <span class="verdict ${allAccepted ? 'accepted' : 'rejected'}">
        ${allAccepted ? 'ACCEPTED' : 'REJECTED'}
      </span>
    `;
    resultItem.appendChild(header);
    
    // Create results for each rubric
    fileResults.forEach(result => {
      const rubricResult = document.createElement('div');
      rubricResult.innerHTML = `<strong>Rubric: ${result.rubric}</strong> - 
                               <span class="verdict ${result.verdict.toLowerCase() === 'accepted' ? 'accepted' : 'rejected'}">
                                 ${result.verdict}
                               </span>`;
      
      if (result.reasons && result.reasons.length > 0) {
        const reasonsList = document.createElement('ul');
        reasonsList.className = 'reason-list';
        
        result.reasons.forEach(reason => {
          const reasonItem = document.createElement('li');
          reasonItem.textContent = reason;
          reasonsList.appendChild(reasonItem);
        });
        
        rubricResult.appendChild(reasonsList);
      }
      
      resultItem.appendChild(rubricResult);
    });
    
    resultsContainer.appendChild(resultItem);
  }
}

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
  loadRubrics();
});