# DU Bill Fetcher Bot 🤖

نظام آلي لجلب فواتير du مع حل CAPTCHA التلقائي

## المميزات ✨

- ✅ جلب الفواتير من موقع du تلقائياً
- ✅ حل CAPTCHA التلقائي باستخدام 2Captcha
- ✅ واجهة ويب سهلة الاستخدام
- ✅ نظام إدارة جلسات آمن
- ✅ دعم اللغة العربية والإنجليزية

## المتطلبات 📋

- Python 3.7+
- Flask
- Requests
- Selenium (اختياري)

## التثبيت 🚀

```bash
pip install -r requirements.txt
```

## التشغيل ▶️

```bash
python server.py
```

الموقع سيكون متاحاً على: `http://localhost:5000`

## متغيرات البيئة 🔐

```
CAPTCHA_API_KEY=your_2captcha_api_key
PORT=5000
```

## الملفات الرئيسية 📁

- `server.py` - الخادم الرئيسي
- `du_bot.py` - البوت الذكي لجلب الفواتير
- `index.html` - الواجهة الرئيسية (عربي)
- `index_en.html` - الواجهة الرئيسية (إنجليزي)
- `admin.html` - لوحة التحكم الإدارية

## API Endpoints 🔌

### جلب الفاتورة
```
POST /api/bill/fetch
Content-Type: application/json

{
  "phone": "971501234567"
}
```

### الحصول على CAPTCHA
```
GET /api/bill/captcha
```

### حل CAPTCHA
```
POST /api/bill/solve-captcha
Content-Type: application/json

{
  "image": "base64_encoded_image"
}
```

## الترخيص 📄

MIT License

## التطوير 👨‍💻

تم بناء هذا المشروع بواسطة Manus AI

---

**ملاحظة:** هذا المشروع مخصص للاستخدام الشخصي فقط.
