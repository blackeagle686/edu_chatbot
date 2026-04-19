#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import ast
import re

# Configuration
POLL_INTERVAL = 10  # Seconds
EXCLUDE_DIRS = {".git", "__pycache__", "venv", "node_modules", "data", "uploads"}

class SmartPush:
    def __init__(self, interval=POLL_INTERVAL):
        self.interval = interval
        self.last_status = ""

    def run_command(self, cmd):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return None

    def get_changed_files(self):
        # Check for modified, deleted, or untracked files
        status = self.run_command("git status --porcelain")
        if not status:
            return []
        
        files = []
        for line in status.split("\n"):
            if line:
                # Format: XY filename (X is staged, Y is unstaged)
                # We care about any change
                files.append(line[3:])
        return files

    def analyze_python_file(self, file_path):
        """Uses AST to find names of functions and classes in the file."""
        try:
            with open(file_path, "r") as f:
                tree = ast.parse(f.read())
            
            nodes = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    nodes.append(("func", node.name, node.lineno))
                elif isinstance(node, ast.ClassDef):
                    nodes.append(("class", node.name, node.lineno))
            return nodes
        except Exception:
            return []

    def get_semantic_message(self, changed_files):
        """Generates a message based on file types and AST analysis."""
        if not changed_files:
            return "chore: trivial updates"

        # Stage changes first to analyze the diff
        self.run_command("git add .")
        diff = self.run_command("git diff --cached")
        
        summary_parts = []
        
        # Group by type
        py_files = [f for f in changed_files if f.endswith(".py")]
        web_files = [f for f in changed_files if f.endswith((".html", ".css", ".js"))]
        doc_files = [f for f in changed_files if f.endswith((".md", ".txt"))]
        conf_files = [f for f in changed_files if f.endswith((".env", ".yml", ".json", ".sh"))]

        # 1. Analyze Python logic
        for f in py_files:
            basename = os.path.basename(f).replace(".py", "")
            nodes = self.analyze_python_file(f)
            
            # Simple heuristic: look for added/modified lines in diff and match with AST
            file_diff = self.run_command(f"git diff --cached {f}")
            changed_lines = re.findall(r"@@ -\d+,\d+ \+(\d+),", file_diff)
            
            affected_nodes = []
            if changed_lines:
                start_line = int(changed_lines[0])
                # Find the closest function/class definition above the change
                for n_type, n_name, n_line in sorted(nodes, key=lambda x: x[2], reverse=True):
                    if n_line <= start_line:
                        affected_nodes.append(n_name)
                        break
            
            if affected_nodes:
                summary_parts.append(f"refactor({basename}): update {affected_nodes[0]}")
            else:
                summary_parts.append(f"fix({basename}): update logic")

        # 2. Analyze Web changes
        if web_files:
            pages = [os.path.basename(f) for f in web_files]
            summary_parts.append(f"style: update {', '.join(pages)}")

        # 3. Analyze Docs
        if doc_files:
            summary_parts.append("docs: update documentation")

        # 4. Analyze Config
        if conf_files:
            summary_parts.append("chore: update configuration")

        if not summary_parts:
            return f"chore: auto-update {len(changed_files)} files"

        # Combine first part as the main message
        return summary_parts[0]

    def start(self):
        print(f"[*] SmartPush started (Polling: {self.interval}s)...")
        print("[*] Press Ctrl+C to exit.")
        
        try:
            while True:
                changed_files = self.get_changed_files()
                
                if changed_files:
                    print(f"[*] Changes detected in: {', '.join(changed_files)}")
                    
                    # Generate semantic message
                    msg = self.get_semantic_message(changed_files)
                    print(f"[*] Generated commit: {msg}")
                    
                    # Finalize Git operations
                    self.run_command(f'git commit -m "{msg}"')
                    push_res = self.run_command("git push")
                    
                    if push_res is not None:
                        print("[+] Push successful. Resuming watch...")
                    else:
                        print("[!] Push failed. Check your connection or branch state.")
                
                time.sleep(self.interval)
        except KeyboardInterrupt:
            print("\n[*] SmartPush stopped.")

if __name__ == "__main__":
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else POLL_INTERVAL
    watcher = SmartPush(interval)
    watcher.start()
