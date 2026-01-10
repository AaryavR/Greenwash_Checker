from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from services import extract_text_from_image, analyze_ingredients_parallel

app = FastAPI()

@app.post("/analyze")
async def analyze_food(file: UploadFile = File(...)):
    extracted_data = await extract_text_from_image(file)
    analysis, logistics, summary = await analyze_ingredients_parallel(extracted_data)
    
    return {
        "summary": summary,
        "analysis": analysis,
        "logistics": logistics
    }

@app.get("/", response_class=HTMLResponse)
async def main():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>EcoScan | Multi-Category Auditor</title>
        <link href="https://fonts.googleapis.com/css2?family=Courier+Prime:wght@400;700&family=Inter:wght@400;600&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-color: #0f1715; 
                --card-bg: #1a2624;
                --text-main: #e2e8f0;
                --accent-green: #10b981;
                --accent-red: #ef4444;
                --accent-yellow: #f59e0b;
                --glow: 0 0 15px rgba(16, 185, 129, 0.4);
            }

            body {
                font-family: 'Inter', sans-serif;
                background-color: var(--bg-color);
                color: var(--text-main);
                margin: 0;
                padding: 20px;
                display: flex;
                flex-direction: column;
                align-items: center;
                min-height: 100vh;
            }

            h2, h3 {
                font-family: 'Courier Prime', monospace;
                color: var(--accent-green);
                text-shadow: 0 0 10px rgba(16, 185, 129, 0.2);
                margin-bottom: 5px;
            }

            p.subtitle { color: #94a3b8; margin-top: 0; font-size: 0.9rem; }

            /* --- Cyberpunk Button --- */
            .upload-container { width: 100%; max-width: 400px; margin: 20px 0; position: relative; }
            
            .btn {
                background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                color: white;
                border: none;
                padding: 16px;
                border-radius: 12px;
                font-family: 'Courier Prime', monospace;
                font-weight: bold;
                font-size: 1.1rem;
                width: 100%;
                cursor: pointer;
                box-shadow: var(--glow);
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 10px;
            }
            
            input[type=file] {
                position: absolute; top: 0; left: 0;
                width: 100%; height: 100%;
                opacity: 0; cursor: pointer;
            }

            /* --- Logistics Badge --- */
            #logistics-card {
                display: none;
                width: 100%; max-width: 400px;
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 15px;
                margin-bottom: 20px;
                font-family: 'Courier Prime', monospace;
                color: #94a3b8;
                font-size: 0.9rem;
            }
            #logistics-card span { color: white; font-weight: bold; }

            /* --- Summary --- */
            #witty-summary {
                display: none;
                width: 100%; max-width: 400px;
                background: linear-gradient(135deg, #2d3836, #1a2624);
                padding: 20px;
                border-radius: 12px;
                border-left: 4px solid var(--accent-green);
                color: #a7f3d0;
                font-style: italic;
                margin-bottom: 20px;
                box-sizing: border-box;
            }

            /* --- Results List --- */
            #results { width: 100%; max-width: 400px; display: flex; flex-direction: column; gap: 10px; }
            
            .item {
                background: var(--card-bg);
                padding: 15px;
                border-radius: 8px;
                border-left: 4px solid #555;
            }
            .item.RED { border-left-color: var(--accent-red); }
            .item.YELLOW { border-left-color: var(--accent-yellow); }
            .item.GREEN { border-left-color: var(--accent-green); }
            
            .item strong { display: block; color: white; font-family: 'Courier Prime', monospace; margin-bottom: 4px; }
            .item span { font-size: 0.85rem; color: #94a3b8; }

            /* --- Loader --- */
            #loading { display: none; margin-top: 30px; text-align: center; color: var(--accent-green); font-family: 'Courier Prime', monospace; }
        </style>
    </head>
    <body>

        <h2>EcoScan v2.1</h2>
        <p class="subtitle">Multi-Category Auditor</p>
        
        <div class="upload-container">
            <button class="btn">🚀 INITIATE AUDIT</button>
            <input type="file" id="fileInput" accept="image/*" capture="environment" onchange="upload()">
        </div>

        <div id="loading">Running Deep Audit...<br>Please Wait</div>

        <div id="witty-summary"></div>
        
        <div id="logistics-card">
            📍 Origin: <span id="origin-val">--</span><br>
            🌍 Verdict: <span id="origin-roast">--</span>
        </div>

        <div id="results"></div>

        <script>
        async function upload() {
            const fileInput = document.getElementById("fileInput");
            const file = fileInput.files[0];
            if(!file) return;
            
            document.getElementById("loading").style.display = "block";
            document.getElementById("results").innerHTML = "";
            document.getElementById("witty-summary").style.display = "none";
            document.getElementById("logistics-card").style.display = "none";
            
            let formData = new FormData();
            formData.append("file", file);
            
            try {
                let response = await fetch('/analyze', {method: "POST", body: formData});
                let data = await response.json();
                
                document.getElementById("loading").style.display = "none";
                
                // 1. Show Summary
                if (data.summary) {
                    let box = document.getElementById("witty-summary");
                    box.innerText = '"' + data.summary + '"';
                    box.style.display = "block";
                }

                // 2. Show Logistics
                if (data.logistics) {
                    document.getElementById("origin-val").innerText = data.logistics.origin || "Unknown";
                    document.getElementById("origin-roast").innerText = data.logistics.roast || "--";
                    document.getElementById("logistics-card").style.display = "block";
                }

                // 3. Show Ingredients
                let html = "";
                data.analysis.forEach((item) => {
                    html += `
                    <div class="item ${item.status}">
                        <strong>${item.name}</strong>
                        <span>${item.explanation}</span>
                    </div>`;
                });
                document.getElementById("results").innerHTML = html;

            } catch (e) {
                alert("Audit Failed.");
                document.getElementById("loading").style.display = "none";
            }
            fileInput.value = "";
        }
        </script>
    </body>
    </html>
    """