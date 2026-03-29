# eFootball Turnir Telegram Bot

Aiogram 3.x, SQLite va Pillow kutubxonalari asosida yaratilgan professional eFootball turnir boshqaruv boti.

## Xususiyatlar

- 🏆 FSM orqali turnir yaratish (admin panel)
- 📝 O'yinchilarni ro'yxatdan o'tkazish
- 💳 To'lov skrinshotini tasdiqlash
- 🎲 Avtomatik qura (Play-off va Guruh bosqichi)
- 🖼️ Pillow orqali chiroyli bracket grafika (ECL uslubida)
- ⚽ Natija yuborish va tasdiqlash
- ⚠️ Nizo hal etish (admin orqali)

## Fayl strukturasi

```
efootball-bot/
├── main.py                    # Asosiy ishga tushirish fayli
├── requirements.txt           # Python kutubxonalari
├── .env.example               # Muhit o'zgaruvchilari namunasi
├── bot/
│   ├── config.py              # Konfiguratsiya
│   ├── states.py              # FSM holatlari
│   ├── handlers/
│   │   ├── admin_handlers.py  # Admin handlerlari
│   │   ├── user_handlers.py   # Foydalanuvchi handlerlari
│   │   └── common_handlers.py # Umumiy handlerlar
│   ├── keyboards/
│   │   ├── admin_kb.py        # Admin klaviaturalari
│   │   └── user_kb.py         # Foydalanuvchi klaviaturalari
│   ├── db/
│   │   ├── database.py        # Ma'lumotlar bazasi ulanishi
│   │   ├── tournaments.py     # Turnir CRUD
│   │   ├── participants.py    # Ishtirokchi CRUD
│   │   └── matches.py         # O'yin CRUD
│   └── utils/
│       ├── bracket_generator.py # Pillow orqali grafika
│       └── draw_utils.py        # Qura yordamchi funksiyalari
├── data/                      # SQLite ma'lumotlar bazasi (avtomatik yaratiladi)
└── fonts/                     # Ixtiyoriy TTF shriftlar
```

## O'rnatish va ishga tushirish

1. **Muhit o'zgaruvchilarini sozlash:**
   ```bash
   cp .env.example .env
   # .env faylini tahrirlang:
   # BOT_TOKEN=BotFather dan olingan token
   # ADMIN_IDS=Telegram ID raqamlaringiz (vergul bilan)
   ```

2. **Kutubxonalarni o'rnatish:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Botni ishga tushirish:**
   ```bash
   python main.py
   ```

## Admin ID ni topish

@userinfobot ga /start yuboring — u sizning Telegram ID raqamingizni beradi.

## Foydalanish

### Admin:
1. `/admin` — Admin panelga kirish
2. `🏆 Turnir yaratish` — FSM orqali yangi turnir
3. `▶️ Qabulni ochish` — Ro'yxatdan o'tishni faollashtirish
4. Kelgan to'lov skrinshotlarini tasdiqlash/rad etish
5. `🎲 Qurani boshlash` — Bracket yaratish va grafika
6. Nizo bo'lsa — admin hal qiladi

### O'yinchi:
1. `/start` — Botni ishga tushirish
2. `📝 Ro'yxatdan o'tish` — Game ID, jamoa nomi, telefon kiritish
3. To'lovli turnirda: to'lov skrinshoti yuborish
4. `📊 Mening o'yinlarim` — O'yinlarni ko'rish
5. `📤 Natija yuborish` — Hisob va skrinshot yuborish
6. Raqib natijani tasdiqlaydi
