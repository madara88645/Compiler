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

### 🎨 Modern UI
A completely redesigned, distraction-free desktop interface:
- **Clean Layout**: Focused purely on input and output.
- **Live Mode**: Real-time feedback and generation as you type.
- **Diagnostics**: Auto-detects risks, ambiguity, and missing context.

### 📉 Token Optimization (New!)
Save money and context window space. The **"Optimize"** feature uses AI to compress your prompt by **20-30%** without losing any meaning, logic, or variables.
- view a **Diff** of changes before applying.
- preserving code blocks and key constraints.

---

## 🛠️ Installation & Usage

1. **Clone and Install**:
   ```bash
   git clone https://github.com/madara88645/Compiler.git
   cd Compiler
   pip install -r requirements.txt
   ```

2. **Setup API Key**:
   Create a `.env` file in the root directory:
   ```env
   OPENAI_API_KEY=sk-your-key-here
   OPENAI_BASE_URL=https://api.deepseek.com
   ```

3. **Run the UI**:
   ```bash
   python ui_desktop.py
   ```

---

## 🧩 Workflow

1. **Type your idea** in the "Prompt" box.
   * *Example: "Create a python script to scrape data from a website, handle errors, and save to CSV."*
2. **Click "Generate"** (or use `Ctrl+Enter`).
   * The system generates specific System and User prompts in seconds.
3. **Review & Refine**:
   * Check the **System Prompt** tab for the persona.
   * Check the **Plan** tab for the logic.
   * Use **"Optimize"** if the prompt feels too long.
4. **Copy & Go**:
   * Click "Copy" and paste it into your favorite LLM (ChatGPT, Claude, etc.).

---

## 📦 Project Structure

* `app/llm_engine/`: **Core Logic**. Handles DeepSeek interaction (`client.py`) and prompt templates.
* `ui_desktop.py`: **The Interface**. Tkinter-based modern GUI.
* `app/heuristics/`: **Safety Net**. Local algorithms for risk detection and offline analysis.

---

## 🤝 Contributing

This is the `feature/pruned-version` branch, focused on simplicity and performance.
1. Fork the repo.
2. Create your feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes.
4. Open a Pull Request.

---
*Built with ❤️ for Prompt Engineers.*
