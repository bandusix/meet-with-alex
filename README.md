# Meet With ALEX - Interview Scheduler 🚀

[🇨🇳 简体中文文档 (Chinese Version)](./README_zh.md)

This is a Geek-style automated interview scheduling system. Candidates can select their preferred time slots through this portal, and the system will automatically generate a dedicated video meeting link via the Feishu API and write it into the interviewer's (ALEX) Feishu calendar.

**🌐 Live Demos:**
- [Deployed on Vercel](https://meet-with-alex.vercel.app/)
- [Deployed on Railway](https://meet-with-alex-production.up.railway.app)

## Core Features
- 💻 **Geek / Hacker UI**: Based on the GitHub Dark Mode color palette and Fira Code monospace font, simulating a terminal command-line interactive experience.
- 📅 **Automated Calendar Sync**: Integrates with the Feishu Open Platform to automatically create events with dedicated video meeting links in the calendar.
- ☁️ **Cloud-Native Ready**: Works out of the box, pre-configured for Vercel (Serverless Functions) and Railway environments.

---

## Prerequisites (Feishu Permission Configuration)
Before deploying, ensure you have created a "Custom App" on the Feishu Open Platform ([open.feishu.cn](https://open.feishu.cn/)) and obtained the following information:
1. **App ID** (`FEISHU_APP_ID`)
2. **App Secret** (`FEISHU_APP_SECRET`)
3. **User ID** (`FEISHU_USER_ID`) - Your personal Feishu open_id

**⚠️ Required Feishu API Scopes (Must be enabled and published):**
- Read and update video meeting information (`vc:meeting`)
- Schedule video meetings (`vc:reserve`)
- Read and update user's calendar and events (`calendar:calendar`)
- Create calendar events (`calendar:calendar.event:create`)
- Read user's user ID (`contact:user.employee_id:readonly`)

*(Note: After checking the permissions, you MUST click "Version Management & Release" to create and publish a new version. Permissions will only take effect after the version is approved and released.)*

---

## Deployment Guide ☁️

This project supports one-click deployment to mainstream cloud hosting platforms. **Vercel** or **Railway** are recommended.

### Option A: Deploy to Vercel (Recommended)
The root directory of this project already contains a `vercel.json` file, which Vercel can directly recognize as a Python Serverless project.

1. Log in to [Vercel](https://vercel.com/).
2. Click **"Add New"** -> **"Project"** in the top right corner.
3. Find and Import your `meet-with-alex` repository from the Git Repository list.
4. Expand the **Environment Variables** section and add the following three variables sequentially:
   - Name: `FEISHU_APP_ID` | Value: *Your Feishu App ID*
   - Name: `FEISHU_APP_SECRET` | Value: *Your Feishu App Secret*
   - Name: `FEISHU_USER_ID` | Value: *Your Feishu Open ID*
5. Click **Deploy**.
6. Wait for about 1-2 minutes. Once the deployment is complete, Vercel will assign a domain like `meet-with-alex.vercel.app`, and it's ready to use!

### Option B: Deploy to Railway
The root directory contains a `railway.toml` file. Railway will automatically build and start FastAPI using Nixpacks.

1. Log in to [Railway](https://railway.app/).
2. Click **"New Project"**, and select **"Deploy from GitHub repo"**.
3. Choose your `meet-with-alex` repository.
4. Click on the project card to enter the settings, then switch to the **Variables** panel.
5. Click **"New Variable"** and add the same three Feishu environment variables as mentioned in the Vercel section (`FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_USER_ID`).
6. Switch to the **Settings** panel, scroll to the **Networking** section, and click **"Generate Domain"**.
7. Wait for the build to finish, click the generated public domain, and you're good to go!

---

## Local Development & Testing
If you want to run or modify this project locally:

1. Clone the repository:
   ```bash
   git clone https://github.com/bandusix/meet-with-alex.git
   cd meet-with-alex
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and fill in your Feishu credentials:
   ```bash
   cp .env.example .env
   ```

4. Start the server:
   ```bash
   python main.py
   ```
   Then visit `http://localhost:8000` in your browser to preview.

---

## Changelog

### v1.3.1 (Latest)
- 💼 **Job Title Expansion**: Updated all interview event descriptions, meeting topics, and UI copy to support recruiting for both `Product Manager` and `Intern` roles, expanding from the previous intern-only focus.

### v1.3.0
- 📄 **Resume Upload Integration**: Added an optional file upload field in the frontend for candidates to upload their PDF resumes (up to 5MB).
- 📎 **Feishu Calendar Attachment**: The system now automatically uploads the candidate's resume to Feishu Drive and binds it directly to the corresponding interview calendar event. Interviewers can access the resume instantly before the meeting.

### v1.2.1
- ⏰ **Timezone Fix**: Explicitly specified the `Asia/Shanghai` timezone when generating event timestamps. This resolves an issue where cloud platforms (like Vercel or Railway) running in UTC would inadvertently shift evening interviews (e.g., 21:00) to the next morning (05:00).

### v1.2.0
- 💼 **Job Title Update**: Updated all interview event descriptions and email templates to reflect the specific role: `TCL FALCON Overseas Product Operation Intern`.
- 📅 **Enhanced Feishu Calendar Sync**: 
  - Switched from fallback mechanisms to the official Feishu primary calendar integration, utilizing the application's Bot capability.
  - 📧 **Automated Email Invitations**: The candidate's email is now dynamically added as a `third_party` attendee to the Feishu event, triggering an automated and professional calendar invite email directly to the candidate's inbox.
  - 👀 **Transparent Attendee List**: Enabled the `can_see_others` attribute so candidates can see the interviewer (ALEX) in the meeting details.

### v1.1.1
- 🐛 **Bug Fix**: Fixed a critical issue where candidate names with Chinese characters caused a `'latin-1' codec can't encode characters` error when interacting with the Feishu API. Requests are now properly encoded in UTF-8.

### v1.1.0
- ✨ **Smart Conflict Prevention**: Integrated Feishu's Free/Busy API (`calendar/v4/freebusy/list`). The system now intelligently checks the interviewer's existing calendar events. Any time slots that overlap with existing meetings will be automatically disabled (grayed out with a strike-through) to prevent double-booking.
- 🌍 **Internationalization**: Fully migrated the user interface to English to accommodate a broader range of PM candidates.
- 🎨 **UI Enhancements**: Added an inspiring welcome message (`> Welcome, all brilliant PM candidates...`) while maintaining the core Geek/Hacker terminal aesthetic.

### v1.0.0
- 🎉 Initial release.
- 📅 Feishu API integration for automatic video meeting generation and calendar event creation.
- 💻 Geek/Hacker style UI with terminal-like interactions and Fira Code monospace font.
- 🍪 Client-side state persistence using Cookies for checking and managing existing bookings.
- ☁️ Ready for Vercel and Railway deployment.

---
*Powered by ALEX*