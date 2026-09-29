# Naukri Auto-Applier Bot

## Prerequisites
1. You must have **Python** installed on your laptop (download from python.org).
2. During Python installation, make sure to check the box that says **"Add Python to PATH"**.

## Setup Instructions
1. Open a terminal (Command Prompt or PowerShell) and navigate to the folder where you extracted these files.
   ```
   cd path\to\naukri_bot
   ```

2. Install the required Python libraries by running:
   ```
   pip install -r requirements.txt
   ```

3. Install the browser automation tool (Playwright) by running:
   ```
   python -m playwright install chromium
   ```

## How to Use
1. Open the `config.json` file in a text editor (like Notepad).
2. Change the `keywords`, `location`, and `experience` to match your own profile. Save the file.
3. Run the bot from the terminal:
   ```
   python main.py
   ```
4. **Important:** The very first time you run it, a browser window will open and wait for 30 seconds. **Use this time to manually log into your Naukri account.** 
5. After you log in once, your session is saved! The bot will automatically start searching and applying. For future runs, you won't need to log in again.
