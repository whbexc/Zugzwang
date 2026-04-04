# ZUGZWANG Changelog Definitions
# Contains version history and changes for the "What's New" dialog.

APP_VERSION = "1.0.4"

CHANGELOG = [
    {
        "version": "1.0.4",
        "date": "April 4, 2026",
        "label": "LATEST",
        "label_color": "#30D158",
        "changes": [
            {
                "type": "improved",
                "text": "10x-20x Performance Boost — concurrent website crawling and optimized Jobsuche/Ausbildung scrapers"
            },
            {
                "type": "fixed",
                "text": "Eliminated Jobsuche CAPTCHA false-positives — now checks for real element visibility"
            },
            {
                "type": "new",
                "text": "Remote Security Engine — real-time kill-switch and discord telemetry integration"
            },
            {
                "type": "improved",
                "text": "Smoother scraping — removed legacy hardcoded delays across all search modules"
            },
            {
                "type": "fixed",
                "text": "Resolved Python SyntaxWarnings in Ausbildung and Azubiyo scrapers"
            },
        ]
    },
    {
        "version": "1.0.3",
        "date": "April 3, 2026",
        "label": None,
        "label_color": None,
        "changes": [
            {
                "type": "improved",
                "text": "Ultra-reliable search history — pops up every time you click the field"
            },
            {
                "type": "improved",
                "text": "Comprehensive Guidance — Hover tooltips added to all search and dashboard elements"
            },
            {
                "type": "improved",
                "text": "Refined Results — renamed 'PUBLISHED' column to 'BEGINN' for better apprenticeship clarity"
            },
            {
                "type": "fixed",
                "text": "Fixed Search Page initialization error (RuntimeError)"
            },
            {
                "type": "fixed",
                "text": "Resolved dashboard rendering glitches and item overlap"
            },
        ]
    },
    {
        "version": "1.0.2",
        "date": "April 1, 2026",
        "label": None,
        "label_color": None,
        "changes": [
            {
                "type": "new",
                "text": "Smart search history — re-run past searches instantly"
            },
            {
                "type": "new",
                "text": "Live toast notifications for scrape progress"
            },
            {
                "type": "new",
                "text": "Drag-to-reorder recipient queue in Send page"
            },
            {
                "type": "improved",
                "text": "Aubi-Plus scraper now 10x faster using in-page fetch()"
            },
            {
                "type": "improved",
                "text": "Cookie modal auto-dismissed — no more blocked sessions"
            },
            {
                "type": "fixed",
                "text": "WIPE DATA and RESET buttons now render correctly"
            },
            {
                "type": "fixed",
                "text": "Settings page no longer scrolls out of viewport"
            },
        ]
    },
    {
        "version": "1.0.1",
        "date": "March 2026",
        "label": None,
        "label_color": None,
        "changes": [
            {
                "type": "new",
                "text": "Email Broadcast page with SMTP engine"
            },
            {
                "type": "new",
                "text": "Runtime Monitor with live activity stream"
            },
            {
                "type": "improved",
                "text": "Statistics table with source and city filters"
            },
            {
                "type": "fixed",
                "text": "Browser session no longer crashes on cookie modals"
            },
        ]
    },
    {
        "version": "1.0.0",
        "date": "February 2026",
        "label": "INITIAL",
        "label_color": "#8E8E93",
        "changes": [
            {
                "type": "new",
                "text": "Initial release — Ausbildung.de + Aubi-Plus scrapers"
            },
            {
                "type": "new",
                "text": "Google Maps business extraction"
            },
            {
                "type": "new",
                "text": "Lead database with Excel export"
            },
        ]
    }
]

CHANGELOG_AR = [
    {
        "version": "1.0.4",
        "date": "4 أبريل 2026",
        "label": "الأحدث",
        "label_color": "#30D158",
        "type_labels": {
            "new": "جديد",
            "improved": "مُحسَّن",
            "fixed": "مُصلَّح",
            "removed": "مُزال"
        },
        "changes": [
            {
                "type": "improved",
                "text": "زيادة الأداء 10-20 مرة — زحف متزامن للمواقع وتحسين محركات البحث في Jobsuche و Ausbildung"
            },
            {
                "type": "fixed",
                "text": "إلغاء تنبيهات CAPTCHA الخاطئة — يعتمد الآن على الرؤية الفعلية للعناصر"
            },
            {
                "type": "new",
                "text": "محرك الأمان عن بعد — دمج مفتاح الإيقاف الفوري وتنبيهات Discord"
            },
            {
                "type": "improved",
                "text": "استخراج أكثر سلاسة — إزالة فترات التأخير القديمة في جميع وحدات البحث"
            },
            {
                "type": "fixed",
                "text": "إصلاح تحذيرات لغة Python في مستخرجات Ausbildung و Azubiyo"
            },
        ]
    },
    {
        "version": "1.0.3",
        "date": "3 أبريل 2026",
        "label": None,
        "label_color": None,
        "type_labels": {
            "new": "جديد",
            "improved": "مُحسَّن",
            "fixed": "مُصلَّح",
            "removed": "مُزال"
        },
        "changes": [
            {
                "type": "improved",
                "text": "موثوقية سجل البحث — تظهر القائمة المنسدلة الآن في كل نقرة"
            },
            {
                "type": "improved",
                "text": "تعليمات توضيحية شاملة (Tooltips) في جميع أنحاء الصفحة"
            },
            {
                "type": "improved",
                "text": "تحسين النتائج — تغيير اسم عمود 'تاريخ النشر' إلى 'تاريخ البدء' (Beginn)"
            },
            {
                "type": "fixed",
                "text": "إصلاح خطأ التهيئة (RuntimeError) في صفحة البحث"
            },
            {
                "type": "fixed",
                "text": "معالجة أخطاء عرض لوحة التحكم وتداخل العناصر"
            },
        ]
    },
    {
        "version": "1.0.2",
        "date": "أبريل 2026",
        "label": None,
        "label_color": None,
        "type_labels": {
            "new": "جديد",
            "improved": "مُحسَّن",
            "fixed": "مُصلَّح",
            "removed": "مُزال"
        },
        "changes": [
            {
                "type": "new",
                "text": "سجل بحث ذكي — أعد تشغيل عمليات البحث السابقة على الفور"
            },
            {
                "type": "new",
                "text": "إشعارات منبثقة مباشرة لتقدم الاستخراج"
            },
            {
                "type": "new",
                "text": "سحب وإفلات لإعادة ترتيب قائمة المستلمين في صفحة الإرسال"
            },
            {
                "type": "improved",
                "text": "مستخرج Aubi-Plus الآن أسرع 10 مرات باستخدام تقنية الجلب داخل الصفحة"
            },
            {
                "type": "improved",
                "text": "إخفاء نوافذ ملفات تعريف الارتباط تلقائيًا — لا مزيد من الجلسات المحظورة"
            },
            {
                "type": "fixed",
                "text": "زري مسح البيانات وإعادة الضبط يعرضان الآن بشكل صحيح"
            },
            {
                "type": "fixed",
                "text": "صفحة الإعدادات لم تعد تخرج عن إطار العرض"
            },
        ]
    },
    {
        "version": "1.0.1",
        "date": "مارس 2026",
        "label": None,
        "label_color": None,
        "type_labels": {
            "new": "جديد",
            "improved": "مُحسَّن",
            "fixed": "مُصلَّح",
            "removed": "مُزال"
        },
        "changes": [
            {
                "type": "new",
                "text": "صفحة بث البريد الإلكتروني مع محرك SMTP للتسويق المباشر"
            },
            {
                "type": "new",
                "text": "مراقب التشغيل مع بث نشاط حي ومباشر"
            },
            {
                "type": "improved",
                "text": "جدول الإحصائيات مزود بفلاتر المصدر والمدينة"
            },
            {
                "type": "fixed",
                "text": "جلسة المتصفح لم تعد تتوقف عند قفل ملفات تعريف الارتباط"
            },
        ]
    },
    {
        "version": "1.0.0",
        "date": "فبراير 2026",
        "label": "الإصدار الأولي",
        "label_color": "#8E8E93",
        "type_labels": {
            "new": "جديد",
            "improved": "مُحسَّن",
            "fixed": "مُصلَّح",
            "removed": "مُزال"
        },
        "changes": [
            {
                "type": "new",
                "text": "النسخة الأولى — برامج استخراج Ausbildung.de + Aubi-Plus"
            },
            {
                "type": "new",
                "text": "استخراج تفاصيل مسارات العمل من خرائط جوجل"
            },
            {
                "type": "new",
                "text": "قاعدة بيانات متكاملة للعملاء المحتملين مع ميزة تصدير Excel"
            },
        ]
    }
]
