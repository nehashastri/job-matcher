# Setup

## Prerequisites
- Windows 10/11
- Chrome installed
- Pixi package manager (https://pixi.sh)
- OpenAI API key
- LinkedIn credentials

## Install
```powershell
cd "d:\Projects\Job List\job_scraper"
pixi -C project_config install
```

## Configure
1. Create your env file
   ```powershell
   Copy-Item project_config/.env.template .env
   ```
2. Fill required keys (minimum)
   ```
   OPENAI_API_KEY=sk-...
   LINKEDIN_EMAIL=you@example.com
   LINKEDIN_PASSWORD=your_password
   OPENAI_MODEL=gpt-4o-mini
   MATCH_SCORE_THRESHOLD=8
   POLL_INTERVAL_MINUTES=30
   ```
3. Provide inputs
   - `data/resume.docx` (your resume)
   - `data/roles.json` (roles + locations + filters)
   - `data/company_blocklist.json` (optional blocklist)

## Gmail Email Notifications Setup

To receive email alerts when jobs are matched, you need to set up Gmail App Passwords:

### Step 1: Enable 2-Factor Authentication
1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Navigate to **2-Step Verification**
3. Follow the prompts to enable 2FA (required for app passwords)

### Step 2: Create App Password
1. Visit [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   - Or: Google Account → Security → 2-Step Verification → App passwords (at bottom)
2. Select app: **Mail**
3. Select device: **Other (Custom name)** → enter "Job Scraper"
4. Click **Generate**
5. Google will display a 16-character password (e.g., `abcd efgh ijkl mnop`)
6. **Copy this immediately** - you won't see it again!

### Step 3: Update `.env` File
Add these lines to your `.env`:
```
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=yourapppasswordhere
EMAIL_FROM=your-email@gmail.com
EMAIL_TO=your-email@gmail.com
ENABLE_EMAIL_NOTIFICATIONS=true
```

**Notes:**
- Use the 16-character app password (remove spaces) in `SMTP_PASSWORD`
- Do NOT use your regular Gmail password
- Set `ENABLE_EMAIL_NOTIFICATIONS=false` to disable emails

## Chrome Profile Setup

To enable faster LinkedIn login and reduce CAPTCHA issues, you can copy your existing Chrome profile:

### Step 1: Locate Your Chrome Profile
1. Open Chrome and go to `chrome://version/`
2. Find the **Profile Path** (e.g., `C:\Users\YourUsername\AppData\Local\Google\Chrome\User Data\Default`)
3. Close all Chrome instances before copying

### Step 2: Copy Your Chrome Profile
1. Open File Explorer and navigate to your Chrome User Data folder
2. Copy the `Default` profile folder (or any named profile you use regularly):
   ```powershell
   Copy-Item "C:\Users\YourUsername\AppData\Local\Google\Chrome\User Data\Default" `
     -Destination "D:\Projects\Job List\job_scraper\data\chrome_profile" -Recurse
   ```
3. Update your `.env` file with:
   ```
   CHROME_PROFILE_PATH=D:\Projects\Job List\job_scraper\data\chrome_profile
   ```

### Step 3: Verify Setup
Run a test to ensure the profile loads correctly:
```powershell
pixi -C project_config run python ../scripts/test_linkedin_login.py
```

**Benefits:**
- Preserves saved passwords and autofill data
- Reduces CAPTCHA challenges
- Maintains LinkedIn session cookies
- Speeds up repeated runs

**Notes:**
- The profile copy is local and won't affect your regular Chrome browser
- If login fails, verify the profile path and ensure all Chrome instances are closed
- You can regenerate the copy anytime by following these steps again

## Resume Management

### Adding Your Resume
1. Save your resume as a Word document (`.docx` format, NOT `.doc`)
2. Copy it to: `D:\Projects\Job List\job_scraper\data\resume.docx`
   ```powershell
   Copy-Item "C:\Path\To\Your\Resume.docx" "D:\Projects\Job List\job_scraper\data\resume.docx"
   ```
3. Verify extraction works:
   ```powershell
   pixi -C project_config run python ../scripts/test_resume_extraction.py
   ```

### Updating Your Resume
When you need to update your resume:
1. Save your updated resume as `.docx`
2. Simply **replace** the file at `data/resume.docx`
3. No need to restart the application - the resume is loaded fresh each time during the matching phase

**Tips:**
- Use Microsoft Word or Google Docs (download as .docx)
- The system extracts text from both paragraphs and tables
- Ensure your resume has actual text content (not just images or text boxes)
- Alternative path: Set `RESUME_PATH` in `.env` to point to a different location

## Run
```powershell
# Single pass over configured roles
pixi -C project_config run scrape

# Continuous polling (interval from .env)
pixi -C project_config run loop
```

## Outputs
- `data/jobs.xlsx` for accepted jobs
- `data/linkedin_connections.xlsx` for saved contacts
- `data/company_blocklist.json` and `data/roles.json` for inputs
- `logs/job_finder.log` (daily rotated) for execution logs

## Testing
- Using pixi task: `pixi -C project_config run test`
- Or directly: `pixi run python -m pytest`

## Troubleshooting
- Chrome/driver: ensure Chrome is installed; Selenium manages the driver.
- Login failures: recheck creds; solve any CAPTCHA manually.
- OpenAI errors: verify API key, quota, and network.
- Empty results: relax filters in `data/roles.json` or lower `MATCH_SCORE_THRESHOLD`.

## Related docs
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- Implementation and test plan: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
- Project map: [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
