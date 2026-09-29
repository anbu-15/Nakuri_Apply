import json
import time
import os
import urllib.request
import urllib.parse
import datetime
import csv
from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import print as rprint

# Initialize Rich Console
console = Console()

CONFIG_FILE = "config.json"
USER_DATA_DIR = "./playwright_profile"
REPORTS_DIR = "Job_Reports"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "keywords": ["Software Engineer"],
            "location": "Chennai",
            "experience": 0,
            "max_pages": 2,
            "job_age_days": 3,
            "ignore_companies": [],
            "strict_title_match": [],
            "required_skills": [],
            "telegram_bot_token": "",
            "telegram_chat_id": ""
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4)
        console.print(f"[dim yellow]Created default '{CONFIG_FILE}'. Modify it to customize your search filters.[/dim yellow]")
        return default_config
        
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def setup_logging():
    now = datetime.datetime.now()
    month_year = now.strftime("%B-%Y")
    day_str = now.strftime("%d-%m-%Y")
    
    report_dir = os.path.join(REPORTS_DIR, month_year, day_str)
    os.makedirs(report_dir, exist_ok=True)
    
    applied_file = os.path.join(report_dir, "applied.csv")
    skipped_file = os.path.join(report_dir, "skipped.csv")
    
    # Initialize headers if file is new
    if not os.path.exists(applied_file):
        with open(applied_file, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(["Time", "Search Keyword", "Job Title", "Company", "Job URL"])
            
    if not os.path.exists(skipped_file):
        with open(skipped_file, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(["Time", "Search Keyword", "Job Title", "Company", "Skip Reason", "Job URL"])
            
    return applied_file, skipped_file

def log_csv(filepath, data_row):
    with open(filepath, 'a', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow(data_row)

def send_telegram_message(token, chat_id, text):
    """Sends a summary message to your Telegram"""
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({'chat_id': chat_id, 'text': text}).encode('utf-8')
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req)
        console.print("[dim green] -> Sent Telegram notification![/dim green]")
    except Exception as e:
        console.print(f"[dim red] -> Failed to send Telegram notification: {e}[/dim red]")

def check_and_prompt_login(page):
    """Checks if logged into Naukri, and pauses if login is needed."""
    try:
        page.goto("https://www.naukri.com/", timeout=60000)
        time.sleep(3)
        login_btn = page.locator("a:has-text('Login'), button:has-text('Login')").first
        if login_btn.count() > 0 and login_btn.is_visible():
            console.print("\n[bold red]⚠️ WARNING: You do not appear to be logged in to Naukri![/bold red]")
            console.print("[yellow]Please log in to your Naukri account in the browser window that just opened.[/yellow]")
            console.print("[cyan]Waiting up to 60 seconds for you to log in...[/cyan]\n")
            
            for _ in range(60):
                time.sleep(1)
                if not (login_btn.count() > 0 and login_btn.is_visible()):
                    console.print("[bold green]✅ Login detected! Continuing...[/bold green]\n")
                    return
            console.print("[yellow]Continuing script... If not logged in, apply actions may fail.[/yellow]\n")
    except Exception:
        pass

def run():
    config = load_config()
    keywords_list = config.get("keywords", ["Software Engineer"])
    location = config.get("location", "Chennai")
    experience = config.get("experience", 0)
    max_pages = config.get("max_pages", 2)
    job_age_days = config.get("job_age_days", 3)
    ignore_companies = [c.lower() for c in config.get("ignore_companies", [])]
    tg_token = config.get("telegram_bot_token", "")
    tg_chat_id = config.get("telegram_chat_id", "")

    strict_titles = [t.lower() for t in config.get("strict_title_match", [])]
    required_skills = [s.lower() for s in config.get("required_skills", [])]

    # Setup CSV files
    applied_csv, skipped_csv = setup_logging()

    total_applied = 0
    
    # Dashboard Header
    console.clear()
    console.print(Panel.fit(
        f"[bold blue]🚀 NAUKRI AUTO-BOT v2.1[/bold blue]\n\n"
        f"[cyan]Target Roles:[/cyan] {', '.join(keywords_list)}\n"
        f"[cyan]Location:[/cyan] {location}    |    [cyan]Experience:[/cyan] {experience} yrs\n"
        f"[cyan]Filters:[/cyan] Max {max_pages} pages, Last {job_age_days} days jobs only\n"
        f"[cyan]Reports:[/cyan] Saving logs to '{REPORTS_DIR}'", 
        border_style="blue",
        title="[bold yellow]Terminal Dashboard[/bold yellow]"
    ))

    with sync_playwright() as p:
        with console.status("[bold magenta]Waking up browser and checking Naukri session...", spinner="dots"):
            context = p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = context.pages[0] if context.pages else context.new_page()
            check_and_prompt_login(page)

        for keyword in keywords_list:
            console.print(f"\n[bold yellow]► SEARCHING FOR:[/bold yellow] [bold white]{keyword}[/bold white]")
            keyword_slug = keyword.replace(" ", "-").lower()
            loc_slug = location.replace(" ", "-").lower()

            for current_page in range(1, max_pages + 1):
                if current_page == 1:
                    search_url = f"https://www.naukri.com/{keyword_slug}-jobs-in-{loc_slug}?experience={experience}"
                else:
                    search_url = f"https://www.naukri.com/{keyword_slug}-jobs-in-{loc_slug}-{current_page}?experience={experience}"
                
                if job_age_days > 0:
                    search_url += f"&jobAge={job_age_days}"
                
                with console.status(f"[cyan]Loading Page {current_page} of {max_pages}..."):
                    page.goto(search_url, timeout=60000)
                    page.wait_for_load_state("networkidle")
                    job_cards = page.locator(".srp-jobtuple-wrapper, div.cust-job-tuple, article.jobTuple")
                    time.sleep(4) 
                    count = job_cards.count()
                
                if count == 0:
                    console.print(f"[bold red]❌ No jobs found on page {current_page}. Moving on.[/bold red]")
                    break

                console.print(f"[bold green]✓ Found {count} jobs on page {current_page}.[/bold green]\n")

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(bar_width=40),
                    TaskProgressColumn(),
                    console=console
                ) as progress:
                    
                    task = progress.add_task(f"[cyan]Applying...[/cyan]", total=count)
                    
                    for i in range(count):
                        title = "Unknown Job"
                        job_url = "No URL"
                        new_page = None
                        try:
                            card = job_cards.nth(i)
                            title_elem = card.locator("a.title, a.title-line").first
                            title = title_elem.inner_text(timeout=2000).strip() if title_elem.count() > 0 else f"Job {i+1}"
                            
                            comp_elem = card.locator("a.comp-name, a.subTitle, .company-name").first
                            company = comp_elem.inner_text(timeout=2000).strip() if comp_elem.count() > 0 else "Unknown"
                            
                            card_text = card.inner_text(timeout=2000).lower()
                            display_title = (title[:35] + '..') if len(title) > 35 else title
                            
                            # Extract URL from the card early
                            if title_elem.count() > 0:
                                href = title_elem.get_attribute("href")
                                if href:
                                    job_url = href if href.startswith("http") else "https://www.naukri.com" + href
                            
                            progress.update(task, description=f"[cyan]Evaluating:[/cyan] [white]{display_title}[/white]")
                            time_now = datetime.datetime.now().strftime("%H:%M:%S")
                            
                            # 1. Ignore Companies Filter
                            is_ignored = any(ignored in company.lower() for ignored in ignore_companies)
                            if is_ignored:
                                console.print(f"  [yellow]⏭️ SKIPPED:[/yellow] {company} is in ignore list.")
                                log_csv(skipped_csv, [time_now, keyword, title, company, "Ignored Company", job_url])
                                progress.advance(task)
                                continue
                                
                            # 2. Strict Title Match Filter
                            if strict_titles:
                                title_lower = title.lower()
                                if not any(st in title_lower for st in strict_titles):
                                    console.print(f"  [yellow]⏭️ SKIPPED:[/yellow] Irrelevant title ({display_title})")
                                    log_csv(skipped_csv, [time_now, keyword, title, company, "Irrelevant Title", job_url])
                                    progress.advance(task)
                                    continue
                            
                            # 3. Required Skills Match Filter
                            if required_skills:
                                has_skill = any(rs in card_text for rs in required_skills)
                                if not has_skill:
                                    console.print(f"  [yellow]⏭️ SKIPPED:[/yellow] Missing key skills ({', '.join(required_skills)})")
                                    log_csv(skipped_csv, [time_now, keyword, title, company, "Missing Skills", job_url])
                                    progress.advance(task)
                                    continue
                            
                            # Open job detail page cleanly
                            if job_url != "No URL":
                                new_page = context.new_page()
                                new_page.goto(job_url, timeout=45000, wait_until="domcontentloaded")
                            else:
                                with context.expect_page(timeout=10000) as new_page_info:
                                    title_elem.click()
                                new_page = new_page_info.value
                                new_page.wait_for_load_state("domcontentloaded")
                            
                            time.sleep(2)
                            actual_url = new_page.url
                            
                            # Locate apply button on job page
                            apply_elem = new_page.locator("#apply-button, button.apply-button, button:has-text('Apply'), a:has-text('Apply')").first
                            
                            if apply_elem.count() > 0 and apply_elem.is_visible():
                                elem_text = apply_elem.inner_text(timeout=2000).strip().lower()
                                
                                # Check if already applied
                                if "applied" in elem_text:
                                    console.print(f"  [cyan]ℹ️ ALREADY APPLIED:[/cyan] {display_title} @ [dim]{company}[/dim]")
                                    log_csv(skipped_csv, [time_now, keyword, title, company, "Already Applied", actual_url])
                                # Check if external company site link
                                elif "company site" in elem_text or "employer website" in elem_text or "external" in elem_text:
                                    console.print(f"  [yellow]⏭️ SKIPPED:[/yellow] External company site link")
                                    log_csv(skipped_csv, [time_now, keyword, title, company, "External Apply Link", actual_url])
                                else:
                                    # Click Apply
                                    apply_elem.click(force=True, timeout=5000)
                                    time.sleep(4) # Wait for application API & drawer updates
                                    
                                    # Check post-click status
                                    # 1. Check if button text changed to 'Applied' or if 'Applied' message is shown
                                    applied_indicator = new_page.locator("button:has-text('Applied'), a:has-text('Applied'), .apply-message:has-text('Applied'), text=/applied successfully|application submitted/i").first
                                    
                                    is_applied_now = False
                                    try:
                                        if applied_indicator.count() > 0 and applied_indicator.is_visible():
                                            is_applied_now = True
                                    except Exception:
                                        pass
                                    
                                    # Fallback check on button text
                                    if not is_applied_now:
                                        try:
                                            btn_text_after = apply_elem.inner_text(timeout=1000).strip().lower()
                                            if "applied" in btn_text_after:
                                                is_applied_now = True
                                        except Exception:
                                            pass
                                            
                                    if is_applied_now:
                                        console.print(f"  [bold green]✅ APPLIED:[/bold green] {display_title} @ [dim]{company}[/dim]")
                                        log_csv(applied_csv, [time_now, keyword, title, company, actual_url])
                                        total_applied += 1
                                    else:
                                        # Check if an actual interactive questionnaire (with input fields/questions) appeared
                                        questionnaire_container = new_page.locator(".chatbot_Drawer, .custom-questions-modal, .chatbot-container").first
                                        has_interactive_questions = False
                                        try:
                                            if questionnaire_container.count() > 0 and questionnaire_container.is_visible():
                                                inputs = questionnaire_container.locator("input, select, textarea, button:has-text('Save'), button:has-text('Submit'), button:has-text('Next')")
                                                if inputs.count() > 0:
                                                    has_interactive_questions = True
                                        except Exception:
                                            pass
                                            
                                        if has_interactive_questions:
                                            console.print(f"  [yellow]⏭️ SKIPPED:[/yellow] Questionnaire Modal Detected ({display_title})")
                                            log_csv(skipped_csv, [time_now, keyword, title, company, "Manual Questionnaire Required", actual_url])
                                        else:
                                            # Default assumption: If no questionnaire input blocking it, application went through
                                            console.print(f"  [bold green]✅ APPLIED:[/bold green] {display_title} @ [dim]{company}[/dim]")
                                            log_csv(applied_csv, [time_now, keyword, title, company, actual_url])
                                            total_applied += 1
                            else:
                                # Check if already applied text exists elsewhere on the page
                                page_applied = new_page.locator("text=/already applied|applied on/i").first
                                if page_applied.count() > 0 and page_applied.is_visible():
                                    console.print(f"  [cyan]ℹ️ ALREADY APPLIED:[/cyan] {display_title} @ [dim]{company}[/dim]")
                                    log_csv(skipped_csv, [time_now, keyword, title, company, "Already Applied", actual_url])
                                else:
                                    console.print(f"  [dim white]➖ SKIPPED:[/dim white] No direct apply button ({display_title})")
                                    log_csv(skipped_csv, [time_now, keyword, title, company, "No Apply Button", actual_url])
                            
                            if new_page and not new_page.is_closed():
                                new_page.close()
                            time.sleep(2) 
                            
                        except Exception as e:
                            error_msg = str(e).split('\n')[0]
                            console.print(f"  [bold red]❌ ERROR:[/bold red] {title[:20]}... -> {error_msg}")
                            log_csv(skipped_csv, [datetime.datetime.now().strftime("%H:%M:%S"), keyword, title, "Unknown", f"Error: {error_msg}", job_url])
                            try:
                                if new_page and not new_page.is_closed():
                                    new_page.close()
                            except Exception:
                                pass
                                
                        progress.advance(task)
                
                time.sleep(3)

        console.print("\n")
        console.print(Panel.fit(
            f"[bold green]🎉 BOT FINISHED![/bold green]\n\n"
            f"Jobs Successfully Applied Today: [bold cyan]{total_applied}[/bold cyan]\n"
            f"Logs saved in: [yellow]{REPORTS_DIR}/[/yellow]",
            border_style="green",
            title="[bold yellow]Summary[/bold yellow]"
        ))
        
        if total_applied > 0:
            send_telegram_message(tg_token, tg_chat_id, f"✅ Naukri Bot Finished!\n\nSuccessfully applied to {total_applied} jobs today for {location}.")
            
        context.close()

if __name__ == "__main__":
    run()