# NetMovi Telegram Bot

`NetMovi` is a Telegram bot that lets users request movies by code. The bot uses a private channel to store movie posts and replies to users with the correct movie when they send the code.

## Features

- Mandatory channel subscription check
- Movie storage via private channel captions
- Multi-language support: Uzbek, Russian, English
- Private channel only the admin can post to
- Users send a movie code to get the movie back

## Setup

1. Create a bot with BotFather and copy the token.
2. Add the bot to both channels: the announcement channel and the private movie channel.
3. Give the bot permission to read messages in the private movie channel.
4. Rename or copy `.env.example` to `.env` and fill the values.

Example `.env` values:

```env
BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ
MANDATORY_CHANNEL=@your_mandatory_channel_username_or_id
PRIVATE_MOVIE_CHANNEL=-1001234567890
ADMIN_USER_ID=123456789
```

5. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

6. Run the bot:

```bash
python bot.py
```

## How it works

- When you post a movie to the private channel, include a unique movie code in the caption.
- The bot saves the movie code and file info locally.
- A user sends the movie code in private chat.
- Bot checks subscription to the mandatory channel and sends the movie if the code matches.

## Notes

- Add the bot to the private channel as admin or with rights to read channel posts.
- The bot only processes `channel_post` updates from the private movie channel.
- Use a unique code in the caption, like `MOVI123`, `KOD456`, or `NETMOVI789`.
