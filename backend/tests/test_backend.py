import requests
import os
import sys

BASE_URL = "http://localhost:8000"
API_V1_STR = "/api/v1"

def test_root():
    print("\n--- Testing Root Endpoint ---")
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

def test_upload_pdf(file_path):
    print(f"\n--- Testing PDF Upload: {file_path} ---")
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
    
    url = f"{BASE_URL}{API_V1_STR}/document/upload"
    files = {'file': (os.path.basename(file_path), open(file_path, 'rb'), 'application/pdf')}
    
    try:
        response = requests.post(url, files=files)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

def test_query(message):
    print(f"\n--- Testing RAG Query: '{message}' ---")
    url = f"{BASE_URL}{API_V1_STR}/chat/query"
    data = {"message": message}
    
    try:
        response = requests.post(url, json=data)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Test Root
    test_root()
    
    # Test Query (should work even without docs, but might return empty/generic)
    test_query("Hello, what is this system about?")
    
    # Check if a PDF path was provided as an argument
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        test_upload_pdf(pdf_path)
        # Query again after upload
        test_query("What does the uploaded document say?")
    else:
        print("\nNote: To test PDF upload, run: python test_backend.py path/to/your/document.pdf")
