import sqlite3
import os
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time

SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK")

class HackerOneScraper:
    def __init__(self):
        self.base_url = "https://hackerone.com/hacktivity/overview"
        self.query_params = {
            "queryString": 'asset_type:("Android: .apk" OR "Android: Play Store") AND severity_rating:("Medium" OR "Low" OR "High" OR "Critical") AND disclosed:true AND has_collaboration:false',
            "sortField": "latest_disclosable_activity_at",
            "sortDirection": "DESC",
            "pageIndex": "0"
        }

        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )

        self.conn = sqlite3.connect("reports.db")
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                url TEXT PRIMARY KEY
            )
        """)
        self.conn.commit()

    def setup_driver(self):
        return webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=self.chrome_options
        )

    def fetch_page(self, driver):
        url = f"{self.base_url}?{'&'.join([f'{k}={v}' for k, v in self.query_params.items()])}"
        driver.get(url)
        time.sleep(5)
        try:
            apply_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Apply')]"))
            )
            apply_button.click()
            time.sleep(5)
        except:
            pass
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        return driver.page_source

    def parse_hacktivity(self, html):
        soup = BeautifulSoup(html, "html.parser")
        reports = []
        items = soup.select("[data-testid='hacktivity-item']")
        for item in items:
            try:
                title = item.select_one("[data-testid='report-title'] span").text.strip()
                severity_elem = item.select_one("[data-testid='report-severity'] span.Tag-module_u1-tag__uUXBB")
                severity = severity_elem.text.strip() if severity_elem else "N/A"
                date_elem = item.select_one("[data-testid='report-disclosed-at'] span[title]")
                date = date_elem['title'] if date_elem else "N/A"
                program_elem = item.select_one("a[href*='hackerone.com/'] .Text-module_u1-text__9F21z")
                program = program_elem.text.strip() if program_elem else "N/A"
                link_elem = item.select_one("a[href*='/reports/']")
                url = f"https://hackerone.com{link_elem['href']}" if link_elem else "N/A"

                reports.append({
                    "title": title,
                    "severity": severity,
                    "date": date,
                    "program": program,
                    "url": url
                })
            except Exception as e:
                continue
        return reports

    def notify_slack(self, report):
        payload = {
            "text": f"*New Android Vulnerability Disclosed!*\n"
                    f"*Title:* {report['title']}\n"
                    f"*Severity:* {report['severity']}\n"
                    f"*Date:* {report['date']}\n"
                    f"*Program:* {report['program']}\n"
                    f"*Link:* {report['url']}"
        }
        if SLACK_WEBHOOK:
            requests.post(SLACK_WEBHOOK, json=payload)

    def update_markdown(self, all_reports):
        lines = [
            "# 📱 Disclosed Android Reports from HackerOne",
            f"_Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n",
            "| # | Title | Severity | Date | Program | URL |",
            "|---|-------|----------|------|---------|-----|"
        ]
        for i, r in enumerate(all_reports, 1):
            lines.append(
                f"| {i} | {r['title'].replace('|',' ')} | {r['severity']} | {r['date']} | {r['program'].replace('|',' ')} | [Link]({r['url']}) |"
            )
        with open("android-reports.md", "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def scrape(self):
        driver = self.setup_driver()
        html = self.fetch_page(driver)
        reports = self.parse_hacktivity(html)
        driver.quit()

        new_reports = []
        for r in reports:
            self.cursor.execute("SELECT 1 FROM reports WHERE url=?", (r["url"],))
            if not self.cursor.fetchone():
                self.cursor.execute("INSERT INTO reports (url) VALUES (?)", (r["url"],))
                self.conn.commit()
                new_reports.append(r)
                self.notify_slack(r)

        if reports:
            self.update_markdown(reports)

        print(f"✅ Found {len(new_reports)} new reports. Markdown updated.")
        return new_reports

def main():
    scraper = HackerOneScraper()
    scraper.scrape()

if __name__ == "__main__":
    main()
