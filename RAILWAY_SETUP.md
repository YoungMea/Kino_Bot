# NetMovi Telegram Bot - Railway Deploy

## 1. GitHub-ga push qiling:

```bash
cd /home/youngmea/kinobot2
git init
git add .
git commit -m "NetMovi Bot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/kinobot2
git push -u origin main
```

## 2. Railway-ga deploy:

1. https://railway.app ga boring
2. GitHub bilan login qiling
3. "New Project" → "Deploy from GitHub"
4. kinobot2 repo tanlang
5. Authorize qiling

## 3. Environment Variables qo'shing:

Railway dashboard-da "Variables" tab:
- `BOT_TOKEN` = your_bot_token
- `MANDATORY_CHANNEL` = @channel_or_-1001234567890
- `PRIVATE_MOVIE_CHANNEL` = -1001234567890
- `ADMIN_USER_ID` = your_id

## 4. Deploy:

Auto-deploy bo'ladi, yoki "Deploy" tugmasini bosing.

## 5. Logs ko'rish:

Dashboard-da "Deployments" → "Logs" tab

---

**Railway Free:**
- $5/oy bepul credit
- 24/7 uptime
- Unlimited restart
- Perfect telegram bot uchun
