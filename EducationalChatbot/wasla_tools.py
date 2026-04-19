import os
import uuid
import re
from datetime import datetime

class WaslaToolKit:
    """
    Core toolset for document generation and structured output processing.
    Handles PDF, DOCX, Markdown and Plan generation.
    """
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def _safe_filename(self, filename: str, ext: str) -> str:
        # Remove potentially dangerous characters
        safe_name = re.sub(r'[^\w\s\.-]', '', filename).strip().replace(" ", "_")
        if not safe_name:
            safe_name = "generated_document"
        if not safe_name.lower().endswith(ext.lower()):
            safe_name += ext
        return f"{uuid.uuid4().hex[:8]}_{safe_name}"

    def generate_markdown(self, content: str, filename: str) -> str:
        """Saves content as a Markdown file."""
        unique_name = self._safe_filename(filename, ".md")
        path = os.path.join(self.output_dir, unique_name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return unique_name

    def generate_pdf(self, content: str, filename: str) -> str:
        """Converts Markdown/Text content to PDF using fpdf2."""
        try:
            from fpdf import FPDF
        except ImportError:
            # Fallback to plain text file if fpdf not installed, 
            # though user said they will install it.
            return self.generate_markdown(f"PDF Generation failed (fpdf2 not installed). Content:\n\n{content}", filename + ".txt")

        unique_name = self._safe_filename(filename, ".pdf")
        path = os.path.join(self.output_dir, unique_name)
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # Add a header
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, filename.replace(".pdf", "").replace("_", " ").title(), ln=True, align='C')
        pdf.ln(5)
        
        # Process content (basic markdown-to-pdf logic)
        pdf.set_font("Arial", size=11)
        
        # Simple cleanup of markdown bold/italic for basic PDF
        clean_content = content.replace("**", "").replace("__", "").replace("#", "")
        
        for line in clean_content.split('\n'):
            # Handle UTF-8 characters by encoding/decoding if necessary or just replace common ones
            # fpdf1.7/2 needs specific handling for unicode, here we do a safe approach
            line = line.encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 8, line)
            
        pdf.output(path)
        return unique_name

    def generate_docx(self, content: str, filename: str) -> str:
        """Converts content to a Word Document using python-docx."""
        try:
            from docx import Document
            from docx.shared import Pt
        except ImportError:
            return self.generate_markdown(f"DOCX Generation failed (python-docx not installed). Content:\n\n{content}", filename + ".txt")

        unique_name = self._safe_filename(filename, ".docx")
        path = os.path.join(self.output_dir, unique_name)
        
        doc = Document()
        doc.add_heading(filename.replace(".docx", "").replace("_", " ").title(), 0)
        
        # Basic parsing for lines
        for line in content.split('\n'):
            if line.startswith('### '):
                doc.add_heading(line[4:], level=3)
            elif line.startswith('## '):
                doc.add_heading(line[3:], level=2)
            elif line.startswith('# '):
                doc.add_heading(line[2:], level=1)
            else:
                doc.add_paragraph(line)
        
        doc.save(path)
        return unique_name

    def generate_plan(self, topic: str, details: str) -> str:
        """Specialized tool for creating a structured study plan."""
        # This is a helper that formats the input into a nice MD/PDF structure
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        plan_content = f"""# Study Plan: {topic}
Generated on: {timestamp}

## Overview
{details}

## Structured Timeline
| Phase | Focus Area | Estimated Time |
|-------|------------|----------------|
| 1     | Foundations| 2 Hours        |
| 2     | Deep Dive  | 4 Hours        |
| 3     | Practice   | 3 Hours        |
| 4     | Review     | 1 Hour         |

---
*Created by Wasla Master AI Assistant*
"""
        return self.generate_markdown(plan_content, f"Plan_{topic.replace(' ', '_')}")

    def generate_cv(self, content: str, filename: str) -> str:
        """Specialized tool for generating a professional CV/Resume."""
        try:
            from fpdf import FPDF
        except ImportError:
            return self.generate_markdown(f"CV Generation failed (fpdf2 not installed). Content:\n\n{content}", filename + ".txt")

        unique_name = self._safe_filename(filename, ".pdf")
        path = os.path.join(self.output_dir, unique_name)
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # --- Professional Header ---
        pdf.set_fill_color(139, 0, 0) # Dark Red (Primary)
        pdf.rect(0, 0, 210, 40, 'F')
        
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'B', 24)
        
        # Try to extract Name from first line
        lines = content.split('\n')
        name = "CURRICULUM VITAE"
        if lines and len(lines[0]) < 50:
            name = lines[0].strip().replace('#', '').upper()
            lines = lines[1:] # Remove name from body
            
        pdf.set_y(15)
        pdf.cell(0, 10, name, ln=True, align='C')
        
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 10, "Generated by Wasla AI Professional Career Suite", ln=True, align='C')
        
        # --- Body ---
        pdf.set_text_color(30, 30, 30)
        pdf.set_y(50)
        
        for line in lines:
            line = line.strip()
            if not line:
                pdf.ln(2)
                continue
                
            if line.startswith('### ') or line.startswith('## ') or line.startswith('# '):
                # Section Header
                section_name = line.replace('#', '').strip().upper()
                pdf.ln(5)
                pdf.set_font("Arial", 'B', 12)
                pdf.set_draw_color(139, 0, 0)
                pdf.set_line_width(0.5)
                pdf.cell(0, 8, section_name, ln=True)
                pdf.line(pdf.get_x(), pdf.get_y(), 200, pdf.get_y())
                pdf.ln(2)
            else:
                # Regular text
                pdf.set_font("Arial", size=10)
                # Handle basic bullet points
                if line.startswith('- ') or line.startswith('* '):
                    pdf.set_x(15)
                    line = chr(149) + " " + line[2:]
                
                # Encode for latin-1 safely
                line = line.encode('latin-1', 'replace').decode('latin-1')
                pdf.multi_cell(0, 6, line)
                
        pdf.output(path)
        return unique_name

    @staticmethod
    def extract_tags(text: str, tag_name: str) -> list:
        """Extracts content from specific XML-like tags."""
        pattern = rf'<{tag_name}(?:\s+filename="([^"]+)")?>([\s\S]*?)(?:</{tag_name}>|$)'
        matches = []
        for match in re.finditer(pattern, text, re.IGNORECASE):
            matches.append({
                "attr": match.group(1),
                "content": match.group(2).strip(),
                "raw": match.group(0)
            })
        return matches
