from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from services import extract_text_from_image, analyze_ingredients_parallel

app = FastAPI()

@app.post("/analyze")
async def analyze_food(file: UploadFile = File(...)):
    # 1. Run the Vision AI
    extracted_data = await extract_text_from_image(file)
    
    # 2. Run the Analysis AIs (Scientist vs Critic)
    analysis, summary = await analyze_ingredients_parallel(extracted_data)
    
    return {
        "summary": summary,
        "analysis": analysis
    }

@app.get("/", response_class=HTMLResponse)
async def main():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>EcoScan | Greenwash Detector</title>
        <style>
            :root {
                --bg-color: #0f1715; /* Deep swamp green/black */
                --card-bg: #1a2624;
                --text-main: #e2e8f0;
                --text-muted: #94a3b8;
                --accent-green: #10b981;
                --accent-red: #ef4444;
                --accent-yellow: #f59e0b;
                --glow: 0 0 20px rgba(16, 185, 129, 0.3);
            }

            body {
                font-family: 'Inter', -apple-system, sans-serif;
                background-color: var(--bg-color);
                color: var(--text-main);
                margin: 0;
                padding: 20px;
                display: flex;
                flex-direction: column;
                align-items: center;
                min-height: 100vh;
            }

            /* --- Typography --- */
            h2 {
                font-weight: 800;
                font-size: 2rem;
                margin-bottom: 0.5rem;
                background: linear-gradient(to right, #10b981, #34d399);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                letter-spacing: -0.05em;
            }

            p.subtitle {
                color: var(--text-muted);
                font-size: 0.9rem;
                margin-top: 0;
                margin-bottom: 2rem;
            }

            /* --- Scan Button (The Hero) --- */
            .upload-container {
                position: relative;
                width: 100%;
                max-width: 400px;
                margin-bottom: 30px;
            }

            .btn {
                background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                color: white;
                border: none;
                padding: 18px;
                border-radius: 16px;
                font-size: 1.1rem;
                font-weight: 600;
                width: 100%;
                cursor: pointer;
                transition: transform 0.2s, box-shadow 0.2s;
                box-shadow: var(--glow);
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 10px;
            }

            .btn:active { transform: scale(0.96); }

            /* Invisible file input covering the button */
            input[type=file] {
                position: absolute;
                top: 0; left: 0;
                width: 100%; height: 100%;
                opacity: 0;
                cursor: pointer;
            }

            /* --- Witty Summary Box --- */
            #witty-summary {
                display: none;
                background: linear-gradient(135deg, #2d3836, #1a2624);
                padding: 20px;
                border-radius: 16px;
                border: 1px solid #3d4f4d;
                color: #a7f3d0;
                font-style: italic;
                font-size: 1.1rem;
                text-align: center;
                margin-bottom: 25px;
                width: 100%;
                max-width: 400px;
                box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5);
                animation: slideUp 0.5s ease-out;
            }

            /* --- Ingredient Cards --- */
            #results {
                width: 100%;
                max-width: 400px;
                display: flex;
                flex-direction: column;
                gap: 12px;
            }

            .item {
                background: var(--card-bg);
                padding: 16px;
                border-radius: 12px;
                border-left: 5px solid transparent; /* The colored strip */
                animation: fadeIn 0.4s ease-out forwards;
                opacity: 0;
                transform: translateY(10px);
                transition: background 0.2s;
            }

            .item strong {
                display: block;
                font-size: 1.05rem;
                margin-bottom: 4px;
                color: white;
            }

            .item span {
                font-size: 0.9rem;
                color: var(--text-muted);
                line-height: 1.4;
            }

            /* Status Colors */
            .item.RED { border-left-color: var(--accent-red); }
            .item.YELLOW { border-left-color: var(--accent-yellow); }
            .item.GREEN { border-left-color: var(--accent-green); }

            .item.RED strong { color: #fca5a5; }
            .item.GREEN strong { color: #6ee7b7; }

            /* --- Loading Spinner --- */
            #loading {
                display: none;
                margin-top: 30px;
            }
            .spinner {
                width: 40px;
                height: 40px;
                border: 4px solid #1a2624;
                border-top: 4px solid #10b981;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }

            /* --- Animations --- */
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            @keyframes fadeIn { to { opacity: 1; transform: translateY(0); } }
            @keyframes slideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        </style>
    </head>
    <body>

        <h2>EcoScan 🌿</h2>
        <p class="subtitle">Exposing greenwashing, one label at a time.</p>
        
        <div class="upload-container">
            <button class="btn">
                <span>📷</span> Scan Product
            </button>
            <input type="file" id="fileInput" accept="image/*" capture="environment" onchange="upload()">
        </div>

        <div id="loading">
            <div class="spinner"></div>
            <p style="color: #64748b; font-size: 0.9rem; margin-top: 10px;">Analyzing Environmental Impact...</p>
        </div>

        <div id="witty-summary"></div>
        <div id="results"></div>

        <script>
        async function upload() {
            const fileInput = document.getElementById("fileInput");
            const file = fileInput.files[0];
            if(!file) return;
            
            // UI Reset
            document.getElementById("loading").style.display = "flex";
            document.getElementById("loading").style.flexDirection = "column";
            document.getElementById("loading").style.alignItems = "center";
            document.getElementById("results").innerHTML = "";
            document.getElementById("witty-summary").style.display = "none";
            
            let formData = new FormData();
            formData.append("file", file);
            
            try {
                let response = await fetch('/analyze', {method: "POST", body: formData});
                let data = await response.json();
                
                document.getElementById("loading").style.display = "none";
                
                // 1. Show Summary
                let summaryBox = document.getElementById("witty-summary");
                if (data.summary) {
                    summaryBox.innerText = '"' + data.summary + '"';
                    summaryBox.style.display = "block";
                }

                // 2. Show List Items with Staggered Animation
                let html = "";
                data.analysis.forEach((item, index) => {
                    // We add 'style' to stagger the animation delay
                    let delay = index * 0.1; 
                    html += `
                    <div class="item ${item.status}" style="animation-delay: ${delay}s">
                        <strong>${item.name}</strong>
                        <span>${item.explanation}</span>
                    </div>`;
                });
                document.getElementById("results").innerHTML = html;

            } catch (e) {
                alert("Error analyzing image. Please try again.");
                document.getElementById("loading").style.display = "none";
                console.error(e);
            }
            
            // Clear input so we can select same file again if needed
            fileInput.value = "";
        }
        </script>
    </body>
    </html>
    """