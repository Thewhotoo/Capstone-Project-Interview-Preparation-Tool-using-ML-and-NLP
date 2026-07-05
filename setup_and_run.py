# Simple Setup & Testing Script
# Just run this file to test everything!

import os
import sys
import subprocess

def run_command(cmd, description):
    """Run a command and show progress"""
    print(f"\n{'='*60}")
    print(f"📍 {description}")
    print(f"{'='*60}")
    result = os.system(cmd)
    if result == 0:
        print(f"✅ Success: {description}")
    else:
        print(f"❌ Failed: {description}")
    return result == 0

# Step 1: Install basic dependencies
print("\n" + "="*60)
print("🔧 STEP 1: Installing Dependencies")
print("="*60)

packages = [
    "flask",
    "werkzeug",
    "sentence-transformers",
    "transformers",
    "torch",
    "joblib",
    "scikit-learn",
    "pandas",
    "numpy",
    "faiss-cpu",
    "pdfplumber",
    "python-docx",
]

for pkg in packages:
    print(f"Installing {pkg}...")
    os.system(f"pip install -q {pkg}")

print("\n✅ Dependencies installed!")

# Step 2: Navigate to project
print("\n" + "="*60)
print("📁 STEP 2: Project Structure Check")
print("="*60)

project_root = r"c:\Users\Surya Srikhar\OneDrive\Documents\Desktop\Capstone_project\Project"
os.chdir(project_root)

folders = ["rag_system", "main_cap", "resume_classifier", "Roberta"]
for folder in folders:
    if os.path.exists(folder):
        print(f"✅ {folder}/ found")
    else:
        print(f"❌ {folder}/ NOT found")

# Step 3: Start Flask Server
print("\n" + "="*60)
print("🚀 STEP 3: Starting Flask Server")
print("="*60)

flask_dir = os.path.join(project_root, "main_cap", "cap")
print(f"\nStarting server from: {flask_dir}")
print("Keep this window open while testing in another terminal!")
print("\n" + "="*60)

os.chdir(flask_dir)
os.system("python app.py")
