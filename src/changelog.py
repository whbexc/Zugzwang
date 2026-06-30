# ZUGZWANG Changelog Definitions
# Contains version history and changes for the "What's New" dialog.

APP_VERSION = "1.1.0 Beta 2"

CHANGELOG = [
    {
        "version": "1.1.0 Beta 2",
        "date": "July 1, 2026",
        "label": "LATEST",
        "label_color": "#30D158",
        "changes": [
            {
                "type": "improved",
                "text": "85% Maps Scraper Speedup — Removed 120-second timeout delays on missing elements, reducing Google Maps latency drastically"
            },
            {
                "type": "improved",
                "text": "Unified Popup UI — Rewrote the Update Notification dialog to use the new premium draggable macOS-style aesthetic"
            },
            {
                "type": "fixed",
                "text": "Cover Letter Perfection — Tuned the PDF engine to use exactly 10pt fonts, single spacing, and optimized margins so generated Anschreiben always fit beautifully onto a single page"
            }
        ]
    },
    {
        "version": "1.1.0 Beta",
        "date": "June 26, 2026",
        "label": None,
        "label_color": None,
        "changes": [
            {
                "type": "new",
                "text": "Dynamic Anschreiben Personalization — automatically generate perfectly tailored and personalized cover letters for every single lead"
            },
            {
                "type": "new",
                "text": "Fail-Forward Batch Exports — seamlessly falls back to attaching your raw uploaded PDF for leads that exceed your daily custom PDF limit without halting the workflow"
            },
            {
                "type": "new",
                "text": "Auto-Clamped Broadcasting — mass email broadcasts now automatically clamp to your remaining limit instead of blocking the entire batch"
            },
            {
                "type": "improved",
                "text": "Ausbildung Engine Upgrade — completely refactored the extraction engine to support robust URL-based radius parameters and true infinite-scroll pagination"
            },
            {
                "type": "improved",
                "text": "Scraping Latency Optimizations — massively reduced search latency by stripping out legacy hardcoded delays and streamlining intelligent browser timeouts"
            },
            {
                "type": "improved",
                "text": "Intrusive Popup Removal — completely removed hard-blocking 'Activate Pro' dialogs from all export and email functions, replacing them with elegant banners"
            },
            {
                "type": "improved",
                "text": "Edit Page Redesign — comprehensive rewrite of the editor UI for better responsiveness, cleaner spacing, and strict adherence to the premium macOS dark theme"
            },
            {
                "type": "fixed",
                "text": "Data Mapping Accuracy — resolved a parsing bug where the lead's city was incorrectly displaying inside the company name field in the activity stream"
            },
            {
                "type": "fixed",
                "text": "Progress Monitor Stability — eliminated a UI race condition in the Monitor page to ensure the extraction progress bar accurately reaches 100% upon completion"
            },
            {
                "type": "fixed",
                "text": "Visual Polish — fixed dark artifacting behind popup text and resolved UI layout overflows across the Settings and Email Sender pages"
            }
        ]
    },
    {
        "version": "1.0.94",
        "date": "April 30, 2026",
        "label": None,
        "label_color": None,
        "changes": [
            {
                "type": "improved",
                "text": "Internal Build Tracking — ZUGZWANG now keeps a separate app build number so same-version hotfix releases can still be enforced through the updater"
            },
            {
                "type": "fixed",
                "text": "Upgrade State Reset — first launch after updating now refreshes stale local UI state automatically without touching scraped leads, sent-email history, or Pro activation"
            },
            {
                "type": "fixed",
                "text": "Settings Recovery Hardening — settings now save atomically with a backup file to protect Pro activation, Send drafts, and SMTP identity state from silent reset"
            },
            {
                "type": "fixed",
                "text": "Machine ID Recovery — if settings lose the stored machine identifier, ZUGZWANG now restores it from the persisted local machine ID file instead of falling back to an empty value"
            },
            {
                "type": "fixed",
                "text": "Send-State Protection — Send page persistence no longer wipes SMTP server settings during local edits or clear actions, preventing false 'SMTP Host not configured' failures"
            },
            {
                "type": "fixed",
                "text": "Launch Responsiveness — reduced startup/dashboard refresh pressure that could make Google Maps runs appear frozen or trigger temporary 'not responding' behavior on app launch"
            },
            {
                "type": "fixed",
                "text": "Recipient Queue Editing — inline email editing now uses a solid in-row editor so old text no longer bleeds through while typing"
            },
            {
                "type": "fixed",
                "text": "Recipient Queue Add Flow — manual recipient entry now uses a native app-styled dialog instead of the old system prompt"
            },
            {
                "type": "improved",
                "text": "Recipient Queue Controls — added icon actions for manual add, clear sent history, and smarter resend behavior when the composed message changes"
            },
            {
                "type": "fixed",
                "text": "Activity Log Cleanliness — internal startup and activation diagnostics no longer pollute the user-facing activity log"
            },
            {
                "type": "fixed",
                "text": "Jobsuche Flow Stability — Angebotsart, radius, and Detailansicht handling were hardened, with improved Kontakt panel / CAPTCHA recovery in detail pages"
            },
            {
                "type": "fixed",
                "text": "Headed Solver Reliability — duplicate CAPTCHA solver windows are now suppressed per job and shutdown is cleaner after manual solving"
            },
            {
                "type": "improved",
                "text": "Startup Upgrade Prompting — unsubscribed users now get a post-'What's New' activation prompt with recurring reminders while activated users stay quiet"
            },
            {
                "type": "fixed",
                "text": "Trial-to-Pro Transition — stale trial-capped search settings now recover correctly after activation instead of staying stuck at old free limits"
            },
        ]
    },
    {
        "version": "1.0.9b",
        "date": "April 22, 2026",
        "label": None,
        "label_color": None,
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
        "version": "1.1.0 Beta 2",
        "date": "1 يوليو 2026",
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
                "text": "تسريع خرائط جوجل بنسبة 85% — إزالة تأخيرات مهلة 120 ثانية على العناصر المفقودة، مما قلل من وقت انتظار الاستخراج بشكل جذري"
            },
            {
                "type": "improved",
                "text": "توحيد واجهة النوافذ المنبثقة — إعادة كتابة نافذة إشعار التحديث لاستخدام تصميم macOS الجديد الفاخر والقابل للسحب"
            },
            {
                "type": "fixed",
                "text": "مثالية خطاب التقديم — ضبط محرك PDF لاستخدام خطوط بحجم 10pt بالضبط، وتباعد مفرد، وهوامش محسّنة بحيث تتسع خطابات Anschreiben دائمًا بشكل جميل في صفحة واحدة"
            }
        ]
    },
    {
        "version": "1.1.0 Beta",
        "date": "26 يونيو 2026",
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
                "text": "تخصيص ديناميكي لخطاب التقديم — توليد خطابات تقديم مخصصة ومصاغة بذكاء لكل شركة تلقائياً وبكل احترافية"
            },
            {
                "type": "new",
                "text": "تصدير الدفعات بمرونة — يتخطى الحد اليومي عبر إرفاق سيرتك الذاتية الأصلية للعملاء المتبقين دون تعطيل سير العمل"
            },
            {
                "type": "new",
                "text": "تقييد البث الذكي — بث رسائل البريد يقوم تلقائياً بضبط الدفعة لتتناسب مع الحد المتبقي بدل حظر العملية بالكامل"
            },
            {
                "type": "improved",
                "text": "ترقية محرك Ausbildung — إعادة بناء محرك الاستخراج لدعم نطاقات البحث المستندة إلى الروابط والتمرير اللانهائي الحقيقي"
            },
            {
                "type": "improved",
                "text": "تسريع الاستخراج — تقليل كبير في وقت الانتظار من خلال إزالة التأخيرات القديمة وتحسين مهل المتصفح الذكية"
            },
            {
                "type": "improved",
                "text": "إزالة النوافذ المزعجة — إزالة نوافذ التفعيل المعرقلة من جميع وظائف التصدير واستبدالها بإشعارات أنيقة"
            },
            {
                "type": "improved",
                "text": "إعادة تصميم صفحة التحرير — إعادة كتابة واجهة المحرر لتحسين الاستجابة والالتزام بمظهر macOS الداكن الفاخر"
            },
            {
                "type": "fixed",
                "text": "دقة تعيين البيانات — حل مشكلة تقنية حيث كان اسم المدينة يظهر بالخطأ داخل حقل اسم الشركة في سجل النشاط"
            },
            {
                "type": "fixed",
                "text": "استقرار شريط التقدم — القضاء على خلل برمجي في صفحة المراقبة لضمان وصول شريط الاستخراج إلى 100% بدقة"
            },
            {
                "type": "fixed",
                "text": "تحسينات بصرية — إصلاح المربعات الداكنة خلف النصوص المنبثقة وحل مشكلة تجاوز وتداخل العناصر في صفحة الإعدادات"
            }
        ]
    },
    {
        "version": "1.0.94",
        "date": "30 أبريل 2026",
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
                "text": "تتبع رقم البناء الداخلي — أصبح لدى ZUGZWANG الآن رقم build منفصل حتى يمكن فرض إصلاحات بنفس رقم النسخة الظاهر عبر أداة التحديث"
            },
            {
                "type": "fixed",
                "text": "إعادة ضبط حالة الترقية — أول تشغيل بعد التحديث يجدد حالة الواجهة المحلية القديمة تلقائياً بدون المساس بالعملاء المستخرجين أو سجل الإرسال أو تفعيل Pro"
            },
            {
                "type": "fixed",
                "text": "تحرير قائمة المستلمين — محرر البريد داخل السطر أصبح يستخدم حقلاً معتماً بالكامل حتى لا يبقى النص القديم ظاهراً أثناء الكتابة"
            },
            {
                "type": "fixed",
                "text": "إضافة مستلم يدوياً — إدخال البريد اليدوي أصبح يستخدم نافذة داخلية منسجمة مع تصميم التطبيق بدل النافذة النظامية القديمة"
            },
        ]
    },
    {
        "version": "1.0.9b",
        "date": "22 أبريل 2026",
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
