# Prompt Compiler (Pruned & Modernized)

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

**Prompt Compiler** is a powerful tool that transforms messy natural language ideas into structured, optimized System Instructions and User Prompts.

> **✨ New in v2.0**: Now powered by **DeepSeek** for superior reasoning, with a fully modernized UI and AI-driven Token Optimization.

---

## 🚀 Key Features

### 🧠 DeepSeek Integration
The engine now uses **DeepSeek-V3** to analyze your intent. It automatically generates:
- **System Prompts**: Expertly crafted personas and constraints.
- **User Prompts**: Structured and clear task definitions.
- **Execution Plans**: Step-by-step logic for complex tasks.

### 🎨 Modern Web UI (New!)
A premium Next.js 14 + TailwindCSS interface:
- **Clean Layout**: A split-screen editor aimed at focus.
- **DeepSeek Live Mode**: Auto-compiles your prompt as you type.
- **Diagnostics**: Real-time health checks for your prompt structure.
- **Dark Mode**: By default, because we are developers.

### 📉 Token Optimization
Save money and context window space. The **"Magic Optimize"** feature uses AI to compress your prompt by **20-30%** without losing any meaning, logic, or variables.

---

## 🛠️ Installation & Usage

1. **Clone and Install**:
   ```bash
   git clone https://github.com/madara88645/Compiler.git
   cd Compiler
   # Install Backend
   pip install -r requirements.txt
   # Install Frontend
   cd web && npm install && cd ..
   ```

2. **Setup API Key**:
   Copy the example environment file and add your API key:
   ```bash
   cp .env.example .env
   ```
   Then edit `.env` and replace `sk-your-deepseek-key-here` with your actual DeepSeek API key.
   
   ⚠️ **Security Warning**: Never commit your `.env` file with actual API keys to version control!
   
   Optional: Add the DeepSeek base URL if needed:
   ```env
   OPENAI_API_KEY=sk-your-actual-key
   OPENAI_BASE_URL=https://api.deepseek.com
   ```

3. **Run the App (One-Click)**:
   Double-click `start_app.bat` (Windows).

   *Or manually:*
   ```bash
   # Terminal 1
   python -m uvicorn api.main:app --reload --port 8080

   # Terminal 2
   cd web && npm run dev
   ```

---

## 🧩 Workflow

1. **Type your idea** in the "Input" box.
   * *Example: "Create a python script to scrape data from a website, handle errors, and save to CSV."*
2. **Click "Generate"** or enable **Live Mode**.
   * DeepSeek V3 will analyze your intent and produce a structured prompt.
3. **Review**:
   * **System**: The persona and constraints.
   * **Plan**: The step-by-step logic.
   * **Expanded**: The final combined prompt ready for use.
4. **Copy**:
   * Click the "Copy" icon in the output area.

---

## 📦 Project Structure

* `web/`: **Frontend**. Next.js 14, React, TailwindCSS.
* `api/`: **Backend**. FastAPI, Pydantic, Uvicorn.
* `app/llm_engine/`: **Intelligence**. DeepSeek client, HybridCompiler.
* `start_app.bat`: **Launcher**. Convenience script for dev environment.
* `app/heuristics/`: **Safety Net**. Local algorithms for risk detection and offline analysis.

---



---
*Built with ❤️ for Prompt Engineers.*
