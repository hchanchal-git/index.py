import requests
import urllib3
import os
import base64
import json
from jira import JIRA

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

print("\n=== eGain Healthcheck → JIRA Comment + Attachments (WITH HAR) ===\n")

# ---------------- INPUTS ----------------
HOST = input("Enter eGain host (without https): ").strip()
JIRA_ID = input("Enter JIRA ID (CBU-xxxxx / ACTION-xxxxx): ").strip()

BASE_URL = f"https://{HOST}"

TRACE_DIR = "trace"
os.makedirs(TRACE_DIR, exist_ok=True)

# ---------------- HEALTHCHECK ENDPOINTS ----------------
ENDPOINTS = {
    "Index Healthcheck": "/system/ws/v11/monitoring/indexhealthcheck",
    "Cluster Status": "/system/profiles/profiles/services/manage/get-cluster-status",
    "Service Status": "/system/profiles/profiles/services/manage/status",
}

# ---------------- FETCH APIs ----------------
print("\n📡 Fetching eGain healthcheck endpoints...")

saved_files = []
comment_lines = []

for name, path in ENDPOINTS.items():
    url = BASE_URL + path
    print(f"➡️  Calling {url}")

    headers = {"Accept": "*/*"}

    try:
        r = requests.get(
            url,
            headers=headers,
            verify=False,
            timeout=30
        )
        status = r.status_code
        content = r.text
    except Exception as e:
        status = "ERROR"
        content = str(e)

    file_name = name.lower().replace(" ", "_") + ".txt"
    file_path = os.path.join(TRACE_DIR, file_name)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    saved_files.append(file_path)

    # ✅ STATUS FORMAT LOGIC
    if status == 200:
        status_text = "OK ✔️"
    elif status == 504:
        status_text = "ERROR ❌"
    else:
        status_text = str(status)

    comment_lines.append(
        f"*{name}*\n"
        f"- URL: {url}\n"
        f"- Status: {status_text}\n"
        f"- Attachment: {file_name}\n"
    )

# ---------------- HAR CAPTURE ----------------
def capture_har(host):
    print("\n🌐 Capturing network logs (HAR)...")

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--ignore-certificate-errors")

    chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = webdriver.Chrome(options=chrome_options)

    try:
        driver.get(f"https://{host}")

        logs = driver.get_log("performance")

        har_file = os.path.join(TRACE_DIR, "network_logs.har")

        with open(har_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2)

        print(f"✅ HAR captured: {har_file}")
        return har_file

    except Exception as e:
        print(f"❌ HAR capture failed: {e}")
        return None

    finally:
        driver.quit()

# Call HAR capture
har_file = capture_har(HOST)
if har_file:
    saved_files.append(har_file)

# ---------------- JIRA LOGIN ----------------
print("\n🔗 Connecting to Jira...")

jira_user = "hchanchal"
jira_server = "https://beetle.egain.com/"

encoded = os.environ.get("JIRA_PASS")
if not encoded:
    print("❌ JIRA_PASS environment variable not set")
    exit(1)

jira_pass = base64.b64decode(encoded).decode()

jira = JIRA(server=jira_server, basic_auth=(jira_user, jira_pass))
print("✅ Jira connected")

# ---------------- POST COMMENT ----------------
comment_body = (
    "h3. eGain Healthcheck Report\n\n"
    f"*Host:* {HOST}\n\n" +
    "\n".join(comment_lines) +
    "\n*Additional:* Full network HAR log attached.\n"
)

jira.add_comment(JIRA_ID, comment_body)
print("📝 JIRA comment added")

# ---------------- UPLOAD ATTACHMENTS ----------------
print("\n📎 Uploading files to JIRA...")

for file_path in saved_files:
    try:
        jira.add_attachment(issue=JIRA_ID, attachment=file_path)
        print(f"✅ Attached: {os.path.basename(file_path)}")
    except Exception as e:
        print(f"❌ Failed to attach {file_path}: {e}")

# ---------------- DONE ----------------
print("\n✅ COMPLETED SUCCESSFULLY")
print(f"📁 Local trace folder: {os.path.abspath(TRACE_DIR)}")
print(f"📎 Files uploaded to JIRA issue: {JIRA_ID}")
