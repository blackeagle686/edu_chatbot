# Wasla Educational Chatbot

> **The Flagship Implementation Project for the [IRYM SDK](file:///home/tlk/Documents/Projects/IEEE_comp/IRYM_sdk/README.md).**

The **Wasla Educational Chatbot** is a sophisticated, multi-modal AI assistant designed to transform how students and educators interact with course materials. This project demonstrates the state-of-the-art capabilities of the **IRYM SDK**, specifically in Retrieval-Augmented Generation (RAG) and Vision-Language Modeling (VLM).

---

## Core Capabilities

- **AI-Powered Course Assistant**: Instant, accurate answers sourced directly from study materials using the IRYM RAG pipeline.
- **Vision-Language Processing**: Seamless analysis of scientific diagrams, handwritten notes, and textbook pages via VLM.
- **Premium UI/UX**: A modern, responsive interface featuring glassmorphism and an intuitive user flow.
- **Context-Aware Semantic Memory**: Intelligent session persistence that remembers historical context for continuous learning.
- **Rapid Deployment**: Optimized for cloud environments with built-in Google Colab and Ngrok support.

---

## Technical Architecture

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Bootstrap](https://img.shields.io/badge/bootstrap-%238511FA.svg?style=for-the-badge&logo=bootstrap&logoColor=white)
![CSS3](https://img.shields.io/badge/css3-%231572B6.svg?style=for-the-badge&logo=css3&logoColor=white)

- **AI Engine**: [IRYM SDK](file:///home/tlk/Documents/Projects/IEEE_comp/IRYM_sdk/) (Integrated RAG & VLM)
- **Deployment**: `pyngrok` (Google Colab Tunneling)
- **Environment**: Python 3.9+

---

## Deployment (Google Colab)

1. **Environment Setup**: Clone or upload the `EducationalChatbot` directory to your Colab workspace.
2. **Configuration**: Set your Ngrok authentication token (recommended for persistent URLs):
   ```python
   import os
   os.environ["NGROK_AUTH_TOKEN"] = "your_token_here"
   ```
3. **Execution**:
   ```bash
   %cd EducationalChatbot
   !python run_on_colab.py
   ```
4. **Access**: Open the generated public URL to launch the assistant.

---

## Built with IRYM SDK

This project serves as a reference implementation for the following **IRYM SDK** modules:
- `RAGPipeline`: Document ingestion, vector storage, and semantic retrieval.
- `VLMPipeline`: Multi-modal reasoning for image-based queries.
- `LifecycleManager`: Standardized service initialization and resource management.

---

Developed by the Wasla Engineering Team.
