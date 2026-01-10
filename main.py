from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from services import extract_text_from_image, analyze_ingredients_parallel

app = FastAPI()

@app.post("/analyze")
async def analyze_food(file: UploadFile = File(...)):
    extracted_data = await extract_text_from_image(file)
    analysis, summary = await analyze_ingredients_parallel(extracted_data)
    return {
        "summary": summary,
        "analysis": analysis
    }

@app.get("/", response_class=HTMLResponse)
async def main():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Greenwash Checker</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <style>
            body { 
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                background-color: #121212; 
                color: #e0e0e0; 
                margin: 0; 
                padding: 20px; 
                text-align: center;
            }
            h2 { color: #ffffff; margin-bottom: 10px; }
            
            /* Mobile Camera Button */
            .upload-btn-wrapper {
                position: relative;
                overflow: hidden;
                display: inline-block;
                margin-top: 20px;
                width: 100%;
            }
            .btn {
                border: 2px solid #03dac6;
                color: #121212;
                background-color: #03dac6;
                padding: 15px 20px;
                border-radius: 30px;
                font-size: 18px;
                font-weight: bold;
                width: 100%;
                cursor: pointer;
            }
            .upload-btn-wrapper input[type=file] {
                font-size: 100px;
                position: absolute;
                left: 0;
                top: 0;
                opacity: 0;
                width: 100%;
                height: 100%;
                cursor: pointer;
            }

            /* Results Styling */
            #witty-summary {
                font-size: 1.2em;
                font-style: italic;
                color: #bb86fc;
                margin: 20px 0;
                padding: 10px;
                border: 1px dashed #bb86fc;
                border-radius: 10px;
                display: none;
            }
            .item { 
                padding: 15px; 
                margin: 10px 0; 
                border-radius: 12px; 
                color: #000; 
                text-align: left;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            }
            .RED { background-color: #cf6679; color: white; }
            .YELLOW { background-color: #f1c40f; color: black; }
            .GREEN { background-color: #2ecc71; color: white; }
            
            strong { display: block; font-size: 1.1em; margin-bottom: 4px; }
            
            #loading { font-size: 1.5em; color: #03dac6; display: none; margin-top: 20px;}
        </style>
    </head>
    <body>
        <h2>Greenwash Checker 🕵️‍♂️</h2>
        <p>Scan ingredients to catch the lies.</p>
        
        <div class="upload-btn-wrapper">
            <button class="btn">📸 Scan Product</button>
            <input type="file" id="fileInput" accept="image/*" capture="environment" onchange="upload()">
        </div>

        <div id="loading">Analyzing... 🧠</div>
        <div id="witty-summary"></div>
        <div id="results"></div>

        <script>
        async function upload() {
            let file = document.getElementById("fileInput").files[0];
            if(!file) return;
            
            document.getElementById("loading").style.display = "block";
            document.getElementById("results").innerHTML = "";
            document.getElementById("witty-summary").style.display = "none";
            
            let formData = new FormData();
            formData.append("file", file);
            
            try {
                let response = await fetch('/analyze', {method: "POST", body: formData});
                let data = await response.json();
                
                document.getElementById("loading").style.display = "none";
                
                // Show Witty Summary
                let summaryBox = document.getElementById("witty-summary");
                summaryBox.innerText = '"' + data.summary + '"';
                summaryBox.style.display = "block";
                
                // Show Items
                let html = "";
                data.analysis.forEach(item => {
                    html += `<div class="item ${item.status}">
                        <strong>${item.name}</strong>
                        ${item.explanation}
                    </div>`;
                });
                document.getElementById("results").innerHTML = html;
            } catch (e) {
                alert("Error analyzing image. Please try again.");
                document.getElementById("loading").style.display = "none";
            }
        }
        </script>
    </body>
    </html>
    """