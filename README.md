# Diplomacia Profit Calculator - Telegram Bot

Bu bot Diplomacia oyununda hər resurs (🦌🪙🛢⚗️) üzrə mənfəəti,
ROI-ni və ən sərfəli fabriki hesablayır. Hər istifadəçi botla **öz** məxfi
söhbətində danışır, öz balans/istehsal rəqəmlərini yazır və nəticəni alır -
başqa istifadəçilər bunu görmür.

## Yeniliklər (bu yeniləmədə)

- **Yaddaş/profil:** Bot indi hər istifadəçinin son daxil etdiyi balansı
  (💊/💎) və hər resurs üçün fabrik istehsalını (adi + bonuslu fabrikin
  bonussuz halı) yadda saxlayır. Növbəti hesablamada bu rəqəmlər soruşulanda
  bot "✅ Əvvəlki: ..." düyməsi ilə köhnə dəyəri təklif edir - istəsən bir
  toxunuşla təsdiqləyirsən, istəsən "✏️ Yeni yaz" ilə yenisini yazırsan.
  Bazar qiymətləri (tez dəyişdiyi üçün) yadda saxlanmır, hər dəfə təzədən
  soruşulur.
- **Alt düymələr düzəldildi:** "🚀 Başla", "❓ Kömək", "❌ Ləğv et" düymələri
  artıq çılpaq "/start" kimi görünmür - yalnız təmiz mətni göstərir, arxa
  planda uyğun əmri işə salır, istənilən mərhələdə (rəqəm gözlənilən yerdə
  belə) düzgün işləyir.
- **Bug düzəlişi:** Bonuslu fabrik üçün bazar qiymətini "keç" edəndə
  (📊 nəticə mərhələsində) hesablama xəta verib çökürdü (`price_now=None`
  ilə vurma xətası) - bu, testlə aşkarlandı və düzəldildi.

## Fayllar

- `calculator.py` - saf riyazi hesablama (Telegram-dan asılı deyil, test edilə bilər)
- `bot.py` - Telegram bot (sual-cavab axını + istifadəçi profili/yaddaşı)
- `telegraph_setup.py` - "/help" üçün Telegraph təlimat səhifəsini avtomatik yaradır
- `step1.jpg` ... `step5.jpg` - təlimat məqaləsində istifadə olunan şəkillər
- `requirements.txt` - lazımi Python paketləri (dəyişməyib)
- `Procfile` - hostinq platforması üçün başlatma əmri

## /help əmri necə işləyir

Bot ilk dəfə işə düşəndə (`TELEGRAPH_HELP_URL` mühit dəyişəni yoxdursa) avtomatik
olaraq Telegraph-da (telegra.ph) 5 addımlı, şəkilli bir təlimat səhifəsi yaradır və
bunu Railway-in "Logs" bölməsinə yazır. `/help` yazan (və ya "❓ Kömək" düyməsini
basan) istifadəçiyə bu səhifənin linki (düymə ilə) və qısa mətn xülasəsi göndərilir.

**Tövsiyə:** ilk uğurlu deploy-dan sonra Railway-in "Logs" bölməsində `Telegraph təlimat səhifəsi yaradıldı: https://telegra.ph/...` sətrini tapıb,
həmin linki Railway-də **Variables** bölməsinə `TELEGRAPH_HELP_URL` adı ilə
əlavə et. Bu, hər yenidən başlamada (deploy) təzə səhifə yaranmasının qarşısını
alır və köhnə linkin işləməyə davam etməsini təmin edir.

## Profil/yaddaş məlumatı haradasa saxlanır?

Bot `bot_persistence.pkl` adlı bir fayla yazır (işlədiyi qovluqda). Bu fayl
sayəsində bot yenidən başladılanda (məs. çökmə/restart) istifadəçilərin
balans/istehsal profili və hətta yarımçıq qalan söhbətlər itmir.

⚠️ **Diqqət:** Railway/Render kimi platformalarda fayl sistemi adətən
"ephemeral"dır - yəni hər **yeni deploy**-da sıfırlanır. Profillərin
deploy-lar arası da qalmasını istəyirsənsə, platformanın **persistent
volume/disk** funksiyasını qoşub `bot_persistence.pkl`-i həmin diskə
yazdırmaq lazımdır (Railway-də "Volumes", Render-də "Disks").

## Qurulma addımları

### 1. Bot yaradın (BotFather ilə)

1. Telegram-da `@BotFather`-ə yazın
2. `/newbot` göndərin, bota ad verin
3. Sizə bir **token** verəcək (məs: `123456:ABC-DEF...`) - bunu saxlayın

### 2. Kompüterinizdə işə salın

```
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

## Genişləndirmə fikirləri (hələ edilməyib)

- Nəticələri şəkil/cədvəl (məs. PNG) kimi göndərmək
- Bir neçə dildə (AZ/TR/EN/RU/PT/ID/ES/FR/DE) dəstək
- İcma orta bazar qiyməti (paylaşılan, anonim toplanan qiymətlər)
- Inline mode (`@BotAdı 50000 40k` yazaraq qrup söhbətlərində sürətli nəticə)
- Mini App
