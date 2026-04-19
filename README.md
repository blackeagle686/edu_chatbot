# 🎓 Wasla

> **The First Implementation Project Built with the [IRYM SDK](file:///home/tlk/Documents/Projects/IEEE_comp/IRYM_sdk/README.md).**

Welcome to **Wasla**, a powerful, multi-modal AI assistant designed to revolutionize how students interact with course materials. This project serves as the flagship demonstration of the **IRYM SDK**'s capabilities in RAG (Retrieval-Augmented Generation) and VLM (Vision-Language Models).

---

## ✨ Key Features

- **📚 AI-Powered Course Assistant**: Ask questions about your study materials and get instant, accurate answers powered by the IRYM RAG pipeline.
- **👁️ Vision-Language Processing**: Upload images of scientific diagrams, handwritten notes, or textbook pages for instant AI analysis.
- **💎 Premium Glassmorphism UI**: A stunning, modern, and fully responsive interface built with Bootstrap 5.
- **🚀 One-Click Colab Deployment**: Fully optimized to run on Google Colab with automated `ngrok` tunneling.
- **🧠 Context-Aware Memory**: Remembers your conversation history for a seamless learning experience.

---

## 🛠️ Tech Stack

- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python)
- **AI Core**: [IRYM SDK](file:///home/tlk/Documents/Projects/IEEE_comp/IRYM_sdk/) (Integrated RAG & VLM)
- **Frontend**: Bootstrap 5, Vanilla CSS (Glassmorphism), JavaScript
- **Deployment**: `pyngrok` (Google Colab Support)

---

## 🚀 Quick Start (Google Colab)

1. **Clone/Upload** the `EducationalChatbot` folder to your Colab environment.
2. **Set your Ngrok Key** (Optional but recommended):
   ```python
   import os
   os.environ["NGROK_AUTH_TOKEN"] = "your_token_here"
   ```
3. **Run the script**:
   ```bash
   %cd EducationalChatbot
   !python run_on_colab.py
   ```
4. **Learn!** Click the generated public URL and start chatting.

---

## 🏗️ Built with IRYM SDK

This project leverages the modular architecture of the **IRYM SDK**:
- `RAGPipeline`: For efficient document ingestion and retrieval.
- `VLMPipeline`: For advanced multi-modal visual reasoning.
- `LifecycleManager`: For robust service initialization and shutdown.

---

Made with ❤️ by the IRYM Team.
