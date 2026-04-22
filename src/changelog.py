# ZUGZWANG Changelog Definitions
# Contains version history and changes for the "What's New" dialog.

APP_VERSION = "1.0.9b"

CHANGELOG = [
    {
        "version": "1.0.9b",
        "date": "April 22, 2026",
        "label": "LATEST",
        "label_color": "#30D158",
        "changes": [
            {
                "type": "new",
                "text": "Sender Profiles — saved multiple Gmail sender identities with instant autocomplete and password autofill"
            },
            {
                "type": "new",
                "text": "Startup Pro Prompt — free users now see a launch-time upgrade dialog with a direct path to activation"
            },
            {
                "type": "improved",
                "text": "Broadcast Draft Persistence — Send page now preserves SMTP setup, queue, subject, body, interval, and attachments across cache cleanup"
            },
            {
                "type": "improved",
                "text": "Gmail Delivery Stability — each Gmail recipient now uses a fresh SMTP session to reduce Windows 10 disconnect issues"
            },
            {
                "type": "improved",
                "text": "Update Intelligence — developer builds like 1.0.9b no longer show false downgrade popups when GitHub is still on 1.0.9"
            },
            {
                "type": "improved",
                "text": "Google Maps Search Resilience — added direct search-URL fallback when packaged builds fail to submit the Maps search box"
            },
            {
                "type": "improved",
                "text": "Google Maps Startup Flow — packaged builds now go straight to the direct Maps search URL instead of wasting time on unreliable UI submit fallbacks"
            },
            {
                "type": "improved",
                "text": "Maps Category Extraction — Google Maps business-type buttons like 'Pflegeheim' and 'Plastischer Chirurg' now populate the Job / Category column"
            },
            {
                "type": "improved",
                "text": "Update Check Quiet Mode — offline or DNS lookup failures no longer spam false updater errors when GitHub cannot be reached"
            },
            {
                "type": "fixed",
                "text": "Stop Responsiveness — manual broadcast stop now interrupts long waits instead of hanging until the next delay finishes"
            },
            {
                "type": "fixed",
                "text": "Cached AppData Cleanup — reset stale local settings without touching scraped leads, SMTP credentials, or saved send drafts"
            },
            {
                "type": "fixed",
                "text": "Settings Cleanup Reliability — locked live log files are skipped safely and cleanup no longer runs SQLite operations on the main thread"
            },
            {
                "type": "fixed",
                "text": "License Persistence — machine ID now saves correctly and Pro activation is flushed immediately to survive app restart"
            },
            {
                "type": "fixed",
                "text": "Recipient Queue Editing — Send page emails can now be corrected inline with a double-click instead of delete-and-readd"
            },
            {
                "type": "fixed",
                "text": "Recipient Queue Editor Rendering — inline email editing no longer draws duplicated overlapping text inside the queue"
            },
        ]
    },
    {
        "version": "1.0.9",
        "date": "April 20, 2026",
        "label": None,
        "label_color": None,
        "changes": [
            {
                "type": "improved",
                "text": "Ausbildung.de Pagination — native infinite scroll support for limitless lead extraction"
            },
            {
                "type": "fixed",
                "text": "Progress Indicators — resolved an update queue glitch where complete runs appeared stuck at 10%"
            },
            {
                "type": "fixed",
                "text": "Radius Accuracy — search URLs now perfectly match their configured catchment area"
            },
        ]
    },
    {
        "version": "1.0.8",
        "date": "April 18, 2026",
        "label": None,
        "label_color": None,
        "changes": [
            {
                "type": "improved",
                "text": "Main Thread Performance — eliminated 10s-30s UI freezes during active scraping sessions"
            },
            {
                "type": "improved",
                "text": "Database Stability — migrated heavy SQLite operations to non-blocking background workers"
            },
            {
                "type": "new",
                "text": "macOS 'Obsidian' Dark Theme — applied globally via a native QProxyStyle for a cohesive experience"
            },
            {
                "type": "improved",
                "text": "Settings UI Polish — streamlined layout and removed redundant email configuration fields"
            },
        ]
    },
    {
        "version": "1.0.7",
        "date": "April 14, 2026",
        "label": None,
        "label_color": None,
        "changes": [
            {
                "type": "new",
                "text": "Persistent Outreach Tracking—auto-skips duplicate emails across application restarts"
            },
            {
                "type": "improved",
                "text": "Broadcast Monitor UI—fully restored elegant card-based monitoring with console-style logs"
            },
            {
                "type": "fixed",
                "text": "Engine Stability—hardened background signals to prevent 'Signal deleted' crashes during I/O"
            },
            {
                "type": "improved",
                "text": "Activity Control—added clear-log and copy-log utilities for better troubleshooting"
            },
        ]
    },
    {
        "version": "1.0.6",
        "date": "April 6, 2026",
        "label": None,
        "label_color": None,
        "changes": [
            {
                "type": "improved",
                "text": "Azubiyo Scraper Performance — implemented concurrent batched extraction for maximum speed"
            },
            {
                "type": "improved",
                "text": "Dashboard Data Reliability — synchronized startup sequence for perfect leads and metrics loading"
            },
            {
                "type": "fixed",
                "text": "Search History Crash — fixed UI unpacking error related to the new radius field"
            },
            {
                "type": "fixed",
                "text": "Dashboard Initialization — resolved a race condition causing intermittent startup crashes"
            },
        ]
    },
    {
        "version": "1.0.4",
        "date": "April 4, 2026",
        "label": None,
        "label_color": None,
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
        "version": "1.0.9b",
        "date": "22 أبريل 2026",
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
                "type": "new",
                "text": "ملفات تعريف المرسل — حفظ عدة هويات Gmail مع إكمال تلقائي فوري وملء تلقائي لكلمة مرور التطبيق"
            },
            {
                "type": "new",
                "text": "نافذة ترقية عند التشغيل — المستخدم التجريبي يرى الآن نافذة تفعيل عند بدء التطبيق مع مسار مباشر للترقية"
            },
            {
                "type": "improved",
                "text": "استمرارية مسودة البث — صفحة الإرسال تحفظ إعدادات SMTP وقائمة المستلمين والعنوان والمحتوى والفاصل الزمني والمرفقات حتى بعد تنظيف الكاش"
            },
            {
                "type": "improved",
                "text": "استقرار إرسال Gmail — كل مستلم في Gmail يستخدم الآن جلسة SMTP جديدة لتقليل انقطاعات Windows 10"
            },
            {
                "type": "improved",
                "text": "ذكاء التحديث — الإصدارات التطويرية مثل 1.0.9b لم تعد تعرض تنبيهات تحديث خاطئة عندما يكون GitHub ما زال على 1.0.9"
            },
            {
                "type": "improved",
                "text": "مرونة بحث خرائط Google — تمت إضافة مسار مباشر عبر رابط البحث عندما تفشل النسخة المجمعة في إرسال مربع بحث الخرائط"
            },
            {
                "type": "improved",
                "text": "استخراج فئة خرائط Google — أزرار نوع النشاط مثل 'Pflegeheim' و 'Plastischer Chirurg' تملأ الآن عمود الوظيفة / الفئة"
            },
            {
                "type": "fixed",
                "text": "استجابة الإيقاف — إيقاف البث اليدوي يقطع فترات الانتظار الطويلة فوراً بدل التعليق حتى ينتهي التأخير"
            },
            {
                "type": "fixed",
                "text": "تنظيف AppData المؤقت — إعادة ضبط الإعدادات المحلية القديمة بدون المساس بالعملاء المستخرجين أو بيانات SMTP أو مسودات الإرسال"
            },
            {
                "type": "fixed",
                "text": "موثوقية تنظيف الإعدادات — يتم تخطي ملفات السجل المقفلة بأمان ولم تعد عمليات SQLite تعمل على الخيط الرئيسي"
            },
            {
                "type": "fixed",
                "text": "استمرارية الترخيص — يتم الآن حفظ معرف الجهاز بشكل صحيح مع حفظ التفعيل فوراً حتى يبقى وضع Pro بعد إعادة تشغيل التطبيق"
            },
            {
                "type": "fixed",
                "text": "تحرير قائمة المستلمين — يمكن الآن تصحيح البريد الإلكتروني داخل صفحة الإرسال بالنقر المزدوج بدل الحذف ثم الإضافة من جديد"
            },
        ]
    },
    {
        "version": "1.0.9",
        "date": "20 أبريل 2026",
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
                "text": "تصفح صفحات Ausbildung.de — دعم التمرير اللانهائي لاستخراج عدد غير محدود من العملاء"
            },
            {
                "type": "fixed",
                "text": "مؤشرات التقدم — حل خلل في طابور التحديث كان يجعل المهام المكتملة تظهر عالقة عند 10%"
            },
            {
                "type": "fixed",
                "text": "دقة نطاق البحث — روابط البحث تتطابق الآن تماماً مع النطاق الجغرافي المحدد"
            },
        ]
    },
    {
        "version": "1.0.8",
        "date": "18 أبريل 2026",
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
                "text": "أداء الخيط الرئيسي — القضاء على تجمد الواجهة من 10 إلى 30 ثانية أثناء الاستخراج النشط"
            },
            {
                "type": "improved",
                "text": "استقرار قاعدة البيانات — نقل عمليات SQLite الثقيلة إلى عمال خلفية غير معرقلين"
            },
            {
                "type": "new",
                "text": "مظهر macOS الداكن 'Obsidian' — تم تطبيقه في جميع أنحاء التطبيق لتجربة متناسقة"
            },
            {
                "type": "improved",
                "text": "تحسين واجهة الإعدادات — تبسيط التخطيط وإزالة حقول تكوين البريد الإلكتروني الزائدة"
            },
        ]
    },
    {
        "version": "1.0.7",
        "date": "14 أبريل 2026",
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
                "text": "تتبع التواصل المستمر — يتخطى تلقائيًا رسائل البريد الإلكتروني المكررة عبر إعادة تشغيل التطبيق"
            },
            {
                "type": "improved",
                "text": "واجهة مراقب البث — استعادة المراقبة الأنيقة القائمة على البطاقات مع سجلات بنمط الكونسول"
            },
            {
                "type": "fixed",
                "text": "استقرار المحرك — تحصين الإشارات الخلفية لمنع تعطل 'حذف الإشارة' أثناء الإدخال/الإخراج"
            },
            {
                "type": "improved",
                "text": "التحكم في النشاط — إمكانية مسح السجل ونسخه لتحسين استكشاف الأخطاء وإصلاحها"
            },
        ]
    },
    {
        "version": "1.0.6",
        "date": "6 أبريل 2026",
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
                "text": "أداء مستخرج Azubiyo — تنفيذ استخراج الدفعات المتزامنة لأقصى سرعة"
            },
            {
                "type": "improved",
                "text": "موثوقية بيانات لوحة التحكم — مزامنة تسلسل بدء التشغيل لتحميل مثالي للعملاء والمقاييس"
            },
            {
                "type": "fixed",
                "text": "إصلاح تعطل سجل البحث — معالجة خطأ في واجهة المستخدم يتعلق بحقل نطاق البحث الجديد"
            },
            {
                "type": "fixed",
                "text": "إصلاح تهيئة لوحة التحكم — معالجة مشكلة تسببت في تعطل التطبيق عند بدء التشغيل"
            },
        ]
    },
    {
        "version": "1.0.4",
        "date": "4 أبريل 2026",
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
