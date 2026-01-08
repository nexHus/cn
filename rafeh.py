import pandas as pd
import requests
from bs4 import BeautifulSoup

# ---- STEP 1: Your published HTML link ----
url = "https://docs.google.com/spreadsheets/u/0/d/e/2PACX-1vQszxfRLXyD5VJZ3GS3hLGavcyxA9AKQp-4eOFQFqWNG5fpaSFL4XhJ0tzN0AzCwrYrrxZu7lEJwdXh/pubhtml?gid=1665573613&single=true"

# ---- STEP 2: Download HTML ----
response = requests.get(url)
soup = BeautifulSoup(response.text, "lxml")

# ---- STEP 3: Extract table ----
table = soup.find("table")

# ---- STEP 4: Read into pandas ----
df = pd.read_html(str(table))[0]

# ---- STEP 5: Save to CSV and Excel ----
df.to_csv("sheet_data.csv", index=False, encoding="utf-8")
df.to_excel("sheet_data.xlsx", index=False)

print("✅ Done! Files saved as sheet_data.csv and sheet_data.xlsx")