# Fantasy Hockey Agent

This project provides tools and an AI-powered agent to help you dominate your Yahoo Fantasy Hockey league:

## Setup Instructions

### 1. Create a Yahoo Developer Application

To use the Yahoo Fantasy API, you need to create a Yahoo Developer application:

1. Go to [Yahoo Developer Apps](https://developer.yahoo.com/apps/create/)
2. Sign in with your Yahoo account
3. Click "Create an App"
4. Fill in the application details
5. Click "Create App"
6. You'll receive a **Client ID** and **Client Secret** - save these!

### 2. Find Your League ID

To find your league ID:

1. Go to your Yahoo Fantasy Hockey league
2. Look at the URL - it should look like: `https://hockey.fantasysports.yahoo.com/hockey/12345`
3. The number at the end (e.g., `12345`) is your League ID

### 3. Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your credentials:
   ```
   YAHOO_CLIENT_ID=your_client_id_from_step_1
   YAHOO_CLIENT_SECRET=your_client_secret_from_step_1
   LEAGUE_ID=your_league_id_from_step_2
   GAME_KEY=nhl
   ```

### 4. Get an Anthropic API Key (for AI Agent)

1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Sign up or log in
3. Navigate to API Keys
4. Create a new API key
5. Add it to your `.env` file as `ANTHROPIC_API_KEY`

### 5. Configure Email (for AI Agent)

The AI agent sends recommendations via email.

**Option A: Mailtrap (Recommended for Testing)**

Mailtrap captures emails without sending them - perfect for testing:

1. Go to [Mailtrap.io](https://mailtrap.io/) and create a free account
2. Create an inbox or use the default one
3. Click on your inbox and go to "SMTP Settings"
4. Copy the credentials and add to your `.env` file:
   ```
   EMAIL_FROM=test@example.com  # Can be any email
   EMAIL_TO=recipient@example.com  # Can be any email
   EMAIL_PASSWORD=your_mailtrap_password
   SMTP_SERVER=sandbox.smtp.mailtrap.io
   SMTP_PORT=2525
   ```
5. View captured emails in your Mailtrap inbox

**Option B: Gmail (For Real Emails)**

1. Enable 2-factor authentication on your Google account
2. Generate an App Password:
   - Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
   - Select "Mail" and your device
   - Copy the generated password
3. Add to your `.env` file:
   ```
   EMAIL_FROM=your_email@gmail.com
   EMAIL_TO=your_email@gmail.com
   EMAIL_PASSWORD=your_gmail_app_password
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   ```

### 6. Install Dependencies

Install all required packages:

```bash
# Activate virtual environment (if not already)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 7. First-Time Authentication

Both scripts require Yahoo OAuth authentication:

```bash
# Activate virtual environment (if not already activated)
source venv/bin/activate

# Run either script for first-time authentication
python get_available_players.py
```

**First Run**: The first time you run the script, it will:
1. Open a browser window for Yahoo OAuth authentication
2. Ask you to log in to Yahoo and authorize the application
3. Redirect to your redirect URI with an authorization code
4. You may need to copy the full URL from the browser and paste it back into the terminal
5. Save the access token for future use (in `token.json`)

**Subsequent Runs**: Both scripts will use the saved token automatically.

### Running the Agent

```bash
# Activate virtual environment
source venv/bin/activate

# Run the agent
python fantasy_hockey_agent.py
```

## Contributing

This is a personal project, but feel free to fork and customize for your needs!

## License

This project is for personal use. Please respect Yahoo's API terms of service and rate limits.
