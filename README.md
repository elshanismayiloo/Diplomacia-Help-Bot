# Diplomacia Profit Calculator - Telegram Bot

Bu bot Diplomacia oyununda hər resurs (🦌🪙🛢⚗️) üzrə mənfəəti,
ROI-ni və ən sərfəli fabriki hesablayır. Hər istifadəçi botla **öz** məxfi
söhbətində danışır, öz balans/istehsal rəqəmlərini yazır və nəticəni alır -
başqa istifadəçilər bunu görmür.

## Fayllar
- `calculator.py` - saf riyazi hesablama (Telegram-dan asılı deyil, test edilə bilər)
- `bot.py` - Telegram bot (sual-cavab axını)
- `requirements.txt` - lazımi Python paketləri

## Qurulma addımları

### 1. Bot yaradın (BotFather ilə)
1. Telegram-da `@BotFather`-ə yazın
2. `/newbot` göndərin, bota ad verin
3. Sizə bir **token** verəcək (məs: `123456:ABC-DEF...`) - bunu saxlayın

### 2. Kompüterinizdə işə salın
```bash
cd diplomacia_bot
pip install -r requirements.txt

# Linux/Mac:
export TELEGRAM_BOT_TOKEN="sizin_token_burada"
# Windows (cmd):
set TELEGRAM_BOT_TOKEN=sizin_token_burada

python bot.py
```
Bot işə düşdü. Telegram-da botunuzu tapıb `/start` yazın.

### 3. 24/7 işləməsi üçün (server üzərində)
Kompüteriniz sönəndə bot da dayanır. Daimi işləməsi üçün pulsuz/ucuz
seçimlər:
- **Railway.app** və ya **Render.com** - GitHub-a kodu yükləyib qoşursunuz,
  `TELEGRAM_BOT_TOKEN`-i "environment variable" kimi əlavə edirsiniz.
- Ucuz VPS (məs. DigitalOcean, Hetzner) üzərində `python bot.py`-i
  `systemd` və ya `screen`/`tmux` ilə arxa planda saxlamaq.

Mobil APK variantına ehtiyac yoxdur - istifadəçilər öz Telegram
tətbiqindən birbaşa istifadə edəcək, bu daha sadə və genişlənə bilən yoldur.

## Hesablama məntiqi (qısa)
- 1 çalışma = 95 💊 net xərc (100-dən 5-i pulsuz regenerasiya olunur)
- 5 💊 = 1 💎 nisbəti ilə, 1 çalışma = 19 💎
- Cəmi çalışma sayı = (💊 + 💎×5) / 95
- 1 çalışmanın M-lə maya dəyəri = paket qiyməti / paketdəki 💎 × 19
- Hər resurs üçün: istehsal, gəlir (M), xərc (M), xalis mənfəət, ROI%,
  həmçinin "pis/orta/yaxşı" bazar ssenariləri və break-even qiymət.

## Genişləndirmə fikirləri
- Nəticələri şəkil/cədvəl (məs. PNG) kimi göndərmək
- İstifadəçinin əvvəlki dəyərlərini yadda saxlamaq (verilənlər bazası)
  ki, hər dəfə hər şeyi yenidən yazmasın
- Bir neçə dildə (AZ/EN/RU) dəstək
