# Manhwa Bot

A Discord bot for searching, tracking, and managing your manhwa/manga reading list directly from Discord using the Comick API.

## Features

- **Search Manhwa** - Find any manhwa using `/search`
- **Track Series** - Add manhwa to your personal tracking list with `/add_manhwas`
- **Automatic Notifications** - Get automatic DM alerts when new chapters release for tracked series
- **Manage List** - View tracked series with `/list_manhwas` or remove them with `/remove_manhwas`
- **Local Storage** - All data stored locally in SQLite (no cloud dependency)

## Prerequisites

Before you start, you'll need:

- Python 3.8 or higher
- A Discord bot token (create one at [Discord Developer Portal](https://discord.com/developers/applications))
- A Discord server where you have permission to add bots

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Coverst-ux/Manhwa-Bot.git
   cd Manhwa-Bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up your bot token**
   - Create a `.env` file in the project root
   - Add your Discord bot token:
     ```
     DISCORD_TOKEN=your_bot_token_here
     ```

4. **Run the bot**
   ```bash
   python main.py
   ```

The bot should now be online in your Discord server.

## Usage

Once the bot is running, use these commands in Discord:

| Command | Description |
|---------|-------------|
| `/search {query}` | Search for a manhwa by title |
| `/add_manhwas {manhwa}` | Add a manhwa to your tracking list |
| `/remove_manhwas {manhwa}` | Remove a manhwa from your tracking list |
| `/list_manhwas` | View all manhwa you're currently tracking |

## Project Status

**Current Features:**
- ✅ Search functionality
- ✅ Manual tracking (add/remove/list)
- ✅ Automatic chapter update notifications
- ✅ Local SQLite storage

**Planned Features:**
- 🔄 Rich embeds with cover images and series info
- 🔄 Web dashboard for tracking (future)

## Configuration

The bot stores all data locally in SQLite. No additional configuration is required beyond setting your bot token.

## Troubleshooting

**Bot not showing up in Discord?**
- Verify your bot token is correct in the `.env` file
- Ensure the bot has permission to send messages in your server
- Check that the bot is actually invited to your server

**Commands not working?**
- Make sure you're using slash commands (start with `/`)
- The bot needs "Send Messages" and "Embed Links" permissions

## Support

If you encounter issues, check the code or open an issue on GitHub.

## License

This project is open source and available under the MIT License.