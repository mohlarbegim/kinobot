#!/usr/bin/env python
"""
Start script for Railway deployment.
Runs both Django (gunicorn) and the Telegram bot concurrently.
"""
import os
import sys
import subprocess
import signal
import time
import urllib.request
import urllib.error

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

PORT = os.getenv('PORT', '8000')

# RUN_MODE: qaysi jarayonlar ishga tushishini belgilaydi.
#   'both' (default) - gunicorn (web/admin) + Telegram bot birga (bitta xizmatli setup)
#   'web'            - faqat gunicorn (admin panel/health). Bot ishga tushmaydi -> BOT_TOKEN shart emas.
#   'bot'            - faqat Telegram bot. Gunicorn yo'q (healthcheck kerak bo'lmagan xizmat uchun).
RUN_MODE = os.getenv('RUN_MODE', 'both').lower()
if RUN_MODE not in ('both', 'web', 'bot'):
    print(f"WARNING: noma'lum RUN_MODE={RUN_MODE!r} - 'both' ishlatiladi")
    RUN_MODE = 'both'

# Global process references for cleanup
bot_process = None
gunicorn_process = None


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    print("Shutting down...")
    if bot_process:
        bot_process.terminate()
    if gunicorn_process:
        gunicorn_process.terminate()
    sys.exit(0)


def check_environment():
    """Check required environment variables"""
    print("Checking environment variables...")

    required_vars = ['BOT_TOKEN']
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        print(f"WARNING: Missing environment variables: {missing}")

    # Show configured variables (masked)
    bot_token = os.getenv('BOT_TOKEN', '')
    admins = os.getenv('ADMINS', '')
    db_url = os.getenv('DATABASE_URL', '')

    print(f"  BOT_TOKEN: {'***' + bot_token[-10:] if len(bot_token) > 10 else '(not set)'}")
    print(f"  ADMINS: {admins if admins else '(not set)'}")
    print(f"  DATABASE_URL: {'configured (PostgreSQL)' if db_url else 'using SQLite'}")
    print(f"  PORT: {PORT}")

    # BOT_TOKEN yo'q bo'lsa bot baribir ishga tushmaydi (Bot(token='') xato beradi).
    # "Web sog'lom, bot o'lik" holatiga tushmaslik uchun shu yerda to'xtaymiz.
    return not missing


def check_database_connection():
    """Check database connection before starting"""
    print("Checking database connection...")
    try:
        import django
        django.setup()
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        print("Database connection: OK")
        return True
    except Exception as e:
        print(f"Database connection ERROR: {e}")
        print("Continuing anyway - bot may have limited functionality")
        return False


def run_migrations():
    """Run Django migrations"""
    print("Running migrations...")
    try:
        result = subprocess.run(
            [sys.executable, 'manage.py', 'migrate', '--noinput'],
            capture_output=True,
            text=True,
            timeout=120  # 2 daqiqa timeout
        )
        if result.returncode == 0:
            print("Migrations completed successfully!")
            if result.stdout:
                # Faqat yangi migratsiyalarni ko'rsatish
                for line in result.stdout.split('\n'):
                    if 'Applying' in line or 'No migrations' in line:
                        print(f"  {line}")
            return True
        else:
            print(f"Migration warning: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("Migration timeout - continuing anyway")
        return False
    except Exception as e:
        print(f"Migration error: {e}")
        return False

def wait_for_gunicorn(max_retries=30):
    """Wait for gunicorn to be ready"""
    for i in range(max_retries):
        time.sleep(1)

        # Check if gunicorn process is still running
        if gunicorn_process.poll() is not None:
            # Get exit code
            exit_code = gunicorn_process.returncode
            print(f"ERROR: Gunicorn exited with code {exit_code}")
            return False

        # Try to connect to health endpoint
        try:
            response = urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health/', timeout=2)
            if response.status == 200:
                print(f"Gunicorn ready after {i+1} seconds!")
                return True
        except Exception:
            print(f"Waiting for gunicorn... ({i+1}/{max_retries})")

    print("WARNING: Gunicorn may not be fully ready")
    return True  # Continue anyway

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("=" * 50)
    print(f"Starting KinoBot Services... (RUN_MODE={RUN_MODE})")
    print("=" * 50)

    run_web = RUN_MODE in ('both', 'web')
    run_bot = RUN_MODE in ('both', 'bot')

    # Bot ishga tushadigan rejimlarda BOT_TOKEN majburiy
    if run_bot:
        env_ok = check_environment()
        if not env_ok:
            print("FATAL: BOT_TOKEN o'rnatilmagan - bot ishga tusha olmaydi. To'xtatildi.")
            sys.exit(1)
    else:
        print("RUN_MODE=web: bot ishga tushirilmaydi (faqat gunicorn/admin).")

    # Check database connection
    db_ok = check_database_connection()

    # Migratsiyalar faqat bot/both rejimida bajariladi. web rejimi migratsiya qilmaydi -
    # aks holda web va bot bir vaqtda migrate qilib poyga (race) bo'lishi mumkin.
    # Migratsiyalarni bot xizmati boshqaradi.
    if db_ok and run_bot:
        run_migrations()
    elif not db_ok:
        print("Skipping migrations due to database connection issues")
    else:
        print("RUN_MODE=web: migratsiyalar o'tkazib yuborildi (bot xizmati bajaradi).")

    # Gunicorn (web/both) - health check uchun BIRINCHI ishga tushadi
    if run_web:
        print(f"\nStarting Django/Gunicorn on port {PORT}...")
        gunicorn_process = subprocess.Popen(
            [
                sys.executable, '-m', 'gunicorn',
                'config.wsgi:application',
                '--bind', f'0.0.0.0:{PORT}',
                '--workers', '1',
                '--threads', '2',
                '--timeout', '120',
                '--access-logfile', '-',
                '--error-logfile', '-',
                '--capture-output',
                '--enable-stdio-inheritance',
            ],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        if not wait_for_gunicorn():
            print("Failed to start gunicorn!")
            sys.exit(1)

    # Bot (bot/both)
    if run_bot:
        print("\nStarting Telegram bot...")
        bot_process = subprocess.Popen(
            [sys.executable, '-m', 'bot.main'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

    print("=" * 50)
    print("All services started!")
    print("=" * 50)

    # Ishlab turgan jarayon(lar)ni kuzatamiz. Biri o'lsa, xato kodi bilan chiqamiz ->
    # Railway qayta ishga tushiradi. Aks holda bot o'lsa ham gunicorn /health/ ga javob
    # berib "healthy" qolardi va bot jimgina o'lik bo'lardi.
    exit_code = 0
    while True:
        if run_web and gunicorn_process.poll() is not None:
            print(f"Gunicorn to'xtadi (code={gunicorn_process.returncode}).")
            exit_code = gunicorn_process.returncode or 1
            break
        if run_bot and bot_process.poll() is not None:
            print(f"Bot jarayoni to'xtadi (code={bot_process.returncode}).")
            exit_code = bot_process.returncode or 1
            break
        time.sleep(5)

    if bot_process and bot_process.poll() is None:
        bot_process.terminate()
    if gunicorn_process and gunicorn_process.poll() is None:
        gunicorn_process.terminate()

    sys.exit(exit_code)
