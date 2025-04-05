from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
from datetime import datetime
import pandas as pd

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
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    def setup_driver(self):
        try:
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=self.chrome_options
            )
            return driver
        except Exception as e:
            print(f"Error setting up driver: {e}")
            return None

    def fetch_page(self, driver, is_first_page=True):
        try:
            if is_first_page:
                url = f"{self.base_url}?{'&'.join([f'{k}={v}' for k, v in self.query_params.items()])}"
                driver.get(url)
                time.sleep(5)
                try:
                    apply_button = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'Button-module_u1-button--primary') and contains(., 'Apply')]"))
                    )
                    apply_button.click()
                    time.sleep(5)
                except:
                    pass
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='hacktivity-item']"))
            )
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            return driver.page_source
        except Exception as e:
            print(f"Error fetching page: {e}")
            return None

    def parse_hacktivity(self, html_content):
        if not html_content:
            return []
        soup = BeautifulSoup(html_content, 'html.parser')
        results = []
        report_items = soup.select("[data-testid='hacktivity-item']")
        for item in report_items:
            try:
                title_elem = item.select_one("[data-testid='report-title'] span.line-clamp-2")
                title = title_elem.text.strip() if title_elem else 'N/A'
                severity_elem = item.select_one("[data-testid='report-severity'] span.Tag-module_u1-tag__uUXBB")
                severity = severity_elem.select_one(".Tag-module_u1-tag__content-wrapper--truncate__hvhWG").text.strip() if severity_elem else 'N/A'
                date_elem = item.select_one("[data-testid='report-disclosed-at'] span[title]")
                date = date_elem['title'] if date_elem and 'title' in date_elem.attrs else 'N/A'
                program_elem = item.select_one("a[href*='hackerone.com/'] .Text-module_u1-text__9F21z.Text-module_u1-text--400__IEa8y")
                program = program_elem.text.strip() if program_elem else 'N/A'
                link_elem = item.select_one("a[href*='/reports/']")
                url = f"https://hackerone.com{link_elem['href']}" if link_elem and link_elem.get('href') else 'N/A'
                results.append({
                    'title': title,
                    'severity': severity,
                    'date': date,
                    'program': program,
                    'url': url
                })
            except Exception as e:
                print(f"Error parsing item: {e}")
                continue
        return results

    def scrape(self):
        driver = self.setup_driver()
        if not driver:
            return []
        all_results = []
        page_number = 1
        try:
            while True:
                html_content = self.fetch_page(driver, is_first_page=(page_number == 1))
                if not html_content:
                    break
                page_results = self.parse_hacktivity(html_content)
                all_results.extend(page_results)
                try:
                    next_button = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "pagination-next-page"))
                    )
                    if "Button-module_u1-button--disabled__5xjy2" in next_button.get_attribute("class"):
                        break
                    next_button.click()
                    time.sleep(5)
                    page_number += 1
                except:
                    break
        finally:
            driver.quit()
        return all_results

def main():
    scraper = HackerOneScraper()
    results = scraper.scrape()
    if not results:
        print("No reports found")
        return
    markdown_lines = [
        "# \ud83d\udcf1 Disclosed Android Reports from HackerOne\n",
        f"_Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n",
        "| # | Title | Severity | Date | Program | URL |",
        "|---|-------|----------|------|---------|-----|"
    ]
    for i, report in enumerate(results, 1):
        markdown_lines.append(
            f"| {i} | {report['title'].replace('|', ' ')} | {report['severity']} | {report['date']} | {report['program'].replace('|', ' ')} | [Link]({report['url']}) |"
        )
    with open("android-reports.md", "w", encoding="utf-8") as f:
        f.write("\n".join(markdown_lines))
    print(f"\n✅ Saved {len(results)} Android reports to 'android-reports.md'")
    try:
        df = pd.DataFrame(results)
        df.index += 1
        df.to_excel("android-reports.xlsx", index_label="No.")
        print(f"✅ Saved {len(results)} Android reports to 'android-reports.xlsx'")
    except Exception as e:
        print(f"❌ Failed to save Excel file: {e}")

if __name__ == "__main__":
    main()
