import logging
import os
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from telegram.error import NetworkError, BadRequest
import requests
import re
import numpy as np
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from collections import defaultdict
import matplotlib.pyplot as plt
from functools import lru_cache
import json
import time


# ===== Config =====
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'isi dengan token')
GOOGLE_SCRIPT_URL = os.getenv('GOOGLE_SCRIPT_URL', "isi dengan script url")
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', '')
CURRENT_VERSION = "1.0"

# ===== Logging Setup =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ===== Rate Limiting =====
user_last_message = defaultdict(float)
MESSAGE_COOLDOWN = 2  # detik

# ===== Helper Functions =====
def check_internet() -> bool:
    """Check internet connection"""
    try:
        requests.get('https://google.com', timeout=5)
        return True
    except:
        return False

@lru_cache(maxsize=1)
def get_cached_data(force_refresh: bool = False) -> list:
    """Get cached data with optional force refresh"""
    if force_refresh:
        get_cached_data.cache_clear()
    try:
        response = requests.get(GOOGLE_SCRIPT_URL + "?action=getData", timeout=10)
        response.raise_for_status()
        return response.json()
    except:
        return []

def get_month_name(month_num: int) -> str:
    """Get month name from month number (1-12)"""
    months = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", 
              "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    return months[month_num - 1] if 1 <= month_num <= 12 else ""

def normalize_category(kategori: str) -> str:
    """Normalize category name by converting to lowercase and stripping whitespace"""
    return (kategori or "Lainnya").strip().lower()

def log_command(command_name: str, user_id: int):
    """Log command usage"""
    logger.info(f"Command: {command_name} used by user_id={user_id}")

def log_received(update: Update):
    """Log received message"""
    user_id = update.effective_user.id
    text = update.message.text if update.message else ''
    logger.info(f"Message received from user_id={user_id}: {text[:50]}... (length: {len(text)})")

def log_sent(text: str, user_id: int):
    """Log sent message"""
    logger.info(f"Message sent to user_id={user_id}: {text[:50]}... (length: {len(text)})")

# ===== Backup Function =====
async def backup_data(context: CallbackContext):
    """Periodic data backup"""
    try:
        data = get_cached_data()
        backup_file = f"backup_{datetime.now().strftime('%Y%m%d')}.json"
        with open(backup_file, 'w') as f:
            json.dump(data, f)
        logger.info(f"Backup created: {backup_file}")
    except Exception as e:
        logger.error(f"Backup failed: {e}")

# ===== Update Checker =====
async def check_updates(context: CallbackContext):
    """Check for updates"""
    if not ADMIN_CHAT_ID:
        return
        
    try:
        req = requests.get("https://api.github.com/repos/username/repo/releases/latest", timeout=10)
        latest_version = req.json()['tag_name']
        if latest_version > CURRENT_VERSION:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"⚠️ New version available: {latest_version}"
            )
    except:
        pass

# ===== Chart Generator =====
def generate_chart(data: list) -> BytesIO:
    """
    Generate daily expense chart from data
    
    Args:
        data: List of expense records
        
    Returns:
        BytesIO: PNG image buffer
    """
    try:
        daily_totals = defaultdict(float)
        for item in data:
            tanggal = item.get("tanggal", "").strip()
            if not tanggal:
                continue
            nominal_raw = str(item.get("nominal", "")).replace(".", "").replace(",", "").strip()
            nominal = float(nominal_raw) if nominal_raw.isdigit() else 0
            if nominal > 0:
                daily_totals[tanggal] += nominal

        sorted_data = sorted(daily_totals.items(), key=lambda x: datetime.strptime(x[0], "%d-%m-%Y"))
        dates = [datetime.strptime(tgl, "%d-%m-%Y") for tgl, _ in sorted_data]
        amounts = [jumlah for _, jumlah in sorted_data]

        fig, ax = plt.subplots(figsize=(14, 6))
        bars = ax.bar(dates, amounts, color="#4285F4")

        for bar, amount in zip(bars, amounts):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"Rp{int(amount):,}".replace(",", "."),
                    ha='center', va='bottom', fontsize=8)

        ax.set_ylabel("Nominal")
        ax.set_title("Grafik Pengeluaran Harian")
        ax.tick_params(axis='x', rotation=45)
        ax.set_ylim(0, max(amounts) * 1.2 if amounts else 1)

        import matplotlib.dates as mdates
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%m-%Y'))

        fig.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        return buffer
    finally:
        plt.close('all')

# ===== Commands =====
async def start(update: Update, context: CallbackContext) -> None:
    log_received(update)
    await update.message.reply_text("Halo! Kirim data dengan format: nominal, kategori, keterangan.")
    log_sent("Halo! Kirim data dengan format: nominal, kategori, keterangan.", update.effective_user.id)

async def help_command(update: Update, context: CallbackContext) -> None:
    log_received(update)
    help_text = (
        "*Panduan Penggunaan Bot* \n"
        "\n• Format pengeluaran:"
        "\n    nominal, kategori, keterangan"
        "\n   `50.000, Makanan, Makan siang`"
        "\n   `50000, Makanan, Makan siang`"
        "\n\n• Perintah yang tersedia:"
        "\n    /info - Melihat detail pengeluaran"
        "\n    /pdf - Mendapatkan laporan dalam format PDF"
        "\n    /grafik - Menampilkan grafik pengeluaran harian"
        "\n\n• Analisis Kategori:"
        "\n    /kategori - Diagram pie persentase pengeluaran per kategori"
        "\n        Contoh: `/kategori` (bulan saat ini)"
        "\n        `/kategori 04/2025` untuk April 2025"
        "\n        Menampilkan:"
        "\n        - Distribusi persentase per kategori"
        "\n        - Nominal total per kategori"
        "\n        - Warna berbeda untuk setiap kategori"
        "\n"
        "\n     /topkategori - 5 kategori pengeluaran tertinggi"
        "\n        Contoh: `/topkategori` (bulan saat ini)"
        "\n         `/topkategori 05/2025` untuk Mei 2025"
        "\n        Menampilkan:"
        "\n        - Grafik batang horizontal"
        "\n        - 5 kategori dengan pengeluaran terbesar"
        "\n        - Nominal total per kategori"
        "\n        - Warna gradient biru"
        "\n\n• Filter Waktu:"
        "\n    Semua command analisis mendukung filter bulan/tahun:"
        "\n    - Format: MM/YYYY (contoh: 04/2025)"
        "\n    - Jika tidak ditentukan, akan menggunakan bulan saat ini"
    )

    await update.message.reply_text(help_text, parse_mode='Markdown')
    log_sent("Mengirim panduan penggunaan bot.", update.effective_user.id)

async def handle_message(update: Update, context: CallbackContext) -> None:
    # Rate limiting
    current_time = time.time()
    if current_time - user_last_message[update.effective_user.id] < MESSAGE_COOLDOWN:
        await update.message.reply_text("⏳ Harap tunggu sebentar sebelum mengirim pesan lagi")
        return
    user_last_message[update.effective_user.id] = current_time

    log_received(update)
    user_id = update.effective_user.id

    try:
        if not check_internet():
            await update.message.reply_text("⚠️ Tidak ada koneksi internet")
            return

        text = update.message.text
        if len(text.split(", ")) != 3:
            await update.message.reply_text("Format salah! Gunakan format: nominal, kategori, keterangan.\n\nKetik /help untuk melihat panduan penggunaan bot.")
            return

        nominal, kategori, keterangan = text.split(", ")
        nominal = re.sub(r"[^\d]", "", nominal)

        if not nominal.isdigit():
            msg = "Nominal harus berupa angka!"
            await update.message.reply_text(msg)
            log_sent(msg, user_id)
            return

        data = {"nominal": nominal, "kategori": kategori, "keterangan": keterangan}
        response = requests.post(GOOGLE_SCRIPT_URL, json=data, timeout=10)
        response.raise_for_status()
        await update.message.reply_text(response.text)
        log_sent(response.text, user_id)
    except ValueError:
        msg = "Format salah! Gunakan format: nominal, kategori, keterangan.\n\nKetik /help untuk melihat panduan penggunaan bot."
        await update.message.reply_text(msg)
        log_sent(msg, user_id)
    except requests.exceptions.Timeout:
        msg = "⏱ Waktu koneksi habis, silakan coba lagi"
        await update.message.reply_text(msg)
        log_sent(msg, user_id)
    except requests.exceptions.RequestException as e:
        msg = f"Gagal mengirim data: {str(e)}"
        await update.message.reply_text(msg)
        log_sent(msg, user_id)

async def lihat_data(update: Update, context: CallbackContext) -> None:
    log_received(update)
    log_command("/info", update.effective_user.id)

    try:
        if not check_internet():
            await update.message.reply_text("⚠️ Tidak ada koneksi internet")
            return

        data = get_cached_data()
        if not data:
            msg = "Tidak ada catatan pengeluaran."
            await update.message.reply_text(msg)
            log_sent(msg, update.effective_user.id)
            return

        message = "*CATATAN PENGELUARAN:*\n\n"
        total = 0

        for i, item in enumerate(data, 1):
            nominal_raw = str(item.get("nominal", "")).replace(".", "").replace(",", "").strip()
            nominal = float(nominal_raw) if nominal_raw.isdigit() else 0
            total += nominal
            message += (
                f"{i}. Tanggal: {item.get('tanggal', '-')}\n"
                f"   Kategori: {item.get('kategori', '-')}\n"
                f"   Nominal: Rp {int(nominal):,}".replace(",", ".") + "\n"
                f"   Keterangan: {item.get('keterangan', '-')}\n\n"
            )

        message += f"*TOTAL PENGELUARAN:* Rp {int(total):,}".replace(",", ".")

        if len(message) > 4096:
            buffer = BytesIO(message.encode('utf-8'))
            buffer.seek(0)
            await update.message.reply_document(
                document=buffer,
                filename="pengeluaran.txt",
                caption="Data pengeluaran (terlalu panjang untuk pesan biasa)"
            )
        else:
            await update.message.reply_text(message, parse_mode="Markdown")
            
        log_sent("Mengirim data pengeluaran ke user.", update.effective_user.id)

    except requests.exceptions.RequestException as e:
        msg = f"Gagal mengambil data: {str(e)}"
        await update.message.reply_text(msg)
        log_sent(msg, update.effective_user.id)

async def kirim_grafik(update: Update, context: CallbackContext) -> None:
    log_received(update)
    log_command("/grafik", update.effective_user.id)

    try:
        if not check_internet():
            await update.message.reply_text("⚠️ Tidak ada koneksi internet")
            return

        data = get_cached_data()
        if not data:
            msg = "Tidak ada data untuk ditampilkan."
            await update.message.reply_text(msg)
            log_sent(msg, update.effective_user.id)
            return

        # Dapatkan bulan dan tahun saat ini
        now = datetime.now()
        current_month = now.month
        current_year = now.year
        
        # Filter data hanya untuk bulan ini
        monthly_data = []
        for item in data:
            tanggal = item.get("tanggal", "")
            if tanggal:
                try:
                    day, month, year = map(int, tanggal.split('-'))
                    if month == current_month and year == current_year:
                        monthly_data.append(item)
                except:
                    continue

        if not monthly_data:
            msg = f"Tidak ada data pengeluaran untuk bulan {get_month_name(current_month)} {current_year}."
            await update.message.reply_text(msg)
            log_sent(msg, update.effective_user.id)
            return

        # Buat grafik untuk bulan ini
        chart_buffer = generate_chart(monthly_data)
        month_name = get_month_name(current_month)

        await update.message.reply_photo(
            photo=chart_buffer,
            caption=f"Grafik Pengeluaran Harian Bulan {month_name} {current_year}",
            filename=f"grafik_pengeluaran_{month_name}_{current_year}.png"
        )
        log_sent(f"Mengirim grafik pengeluaran bulan {month_name}.", update.effective_user.id)

    except requests.exceptions.RequestException as e:
        msg = f"Gagal mengambil data: {str(e)}"
        await update.message.reply_text(msg)
        log_sent(msg, update.effective_user.id)
async def kategori_pie(update: Update, context: CallbackContext):
    log_received(update)
    log_command("/kategori", update.effective_user.id)

    try:
        # Default to current month/year
        now = datetime.now()
        current_month = now.month
        current_year = now.year
        
        # Parse month/year from command args
        if context.args:
            try:
                month, year = map(int, context.args[0].split('/'))
                if 1 <= month <= 12 and 2000 <= year <= 2100:
                    current_month = month
                    current_year = year
                else:
                    await update.message.reply_text("Format bulan/tahun tidak valid. Gunakan: /kategori MM/YYYY (contoh: /kategori 04/2025)")
                    return
            except:
                await update.message.reply_text("Format tidak valid. Gunakan: /kategori MM/YYYY (contoh: /kategori 04/2025)")
                return

        month_name = get_month_name(current_month)
        
        response = requests.get(GOOGLE_SCRIPT_URL + "?action=getData", timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data:
            await update.message.reply_text("Belum ada data pengeluaran.")
            return

        # Filter data by month/year
        filtered_data = []
        for item in data:
            tanggal = item.get("tanggal", "")
            if tanggal:
                try:
                    day, month, year = map(int, tanggal.split('-'))
                    if month == current_month and year == current_year:
                        filtered_data.append(item)
                except:
                    continue

        if not filtered_data:
            await update.message.reply_text(f"Tidak ada data pengeluaran untuk {month_name} {current_year}.")
            return

        # Calculate category totals with normalized names
        categories = defaultdict(float)
        original_names = {}  # To store the original name for display
        
        for item in filtered_data:
            original_kategori = item.get("kategori", "Lainnya").strip()
            normalized_kategori = normalize_category(original_kategori)
            nominal = float(str(item.get("nominal", "0")).replace(".", "").replace(",", ""))
            categories[normalized_kategori] += nominal
            
            # Store the original name (capitalized) for display
            if normalized_kategori not in original_names:
                original_names[normalized_kategori] = original_kategori.capitalize()

        # Create pie chart with improved formatting
        fig, ax = plt.subplots(figsize=(10, 8))
        colors = plt.cm.Pastel1(range(len(categories)))
        
        def make_autopct(values):
            def my_autopct(pct):
                total = sum(values)
                val = int(round(pct*total/100.0))
                return f"{pct:.1f}%\n(Rp {val:,})".replace(",", ".")
            return my_autopct
        
        wedges, texts, autotexts = ax.pie(
            categories.values(),
            labels=[original_names[k] for k in categories.keys()],  # Use original capitalized names
            autopct=make_autopct(categories.values()),
            startangle=90,
            colors=colors,
            textprops={'fontsize': 8}
        )
        
        ax.set_title(f"Persentase Pengeluaran per Kategori\n{month_name} {current_year}", pad=20)
        plt.setp(autotexts, size=8, weight="bold")
        plt.tight_layout()

        # Send as image
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=120, bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        
        caption = f"📊 Distribusi Pengeluaran {month_name} {current_year}:\n"
        # Sort by amount descending and use original capitalized names
        sorted_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)
        caption += "\n".join([f"• {original_names[k]}: Rp {int(v):,}".replace(",", ".") 
                            for k, v in sorted_categories])
        
        await update.message.reply_photo(
            photo=buf,
            caption=caption,
            filename=f"kategori_{current_month}_{current_year}.png"
        )
        log_sent(f"Mengirim grafik kategori {month_name} {current_year}", update.effective_user.id)

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")
        logger.error(f"Error in kategori_pie: {str(e)}")

async def top_kategori(update: Update, context: CallbackContext):
    """Menampilkan 5 kategori pengeluaran tertinggi dalam bentuk grafik batang horizontal"""
    log_received(update)
    log_command("/topkategori", update.effective_user.id)

    try:
        # Default ke bulan/tahun sekarang
        now = datetime.now()
        current_month = now.month
        current_year = now.year
        
        # Parse parameter bulan/tahun jika ada
        if context.args:
            try:
                month, year = map(int, context.args[0].split('/'))
                if not (1 <= month <= 12 and 2000 <= year <= 2100):
                    await update.message.reply_text("Format bulan/tahun tidak valid. Gunakan: /topkategori MM/YYYY (contoh: /topkategori 04/2025)")
                    return
                current_month = month
                current_year = year
            except:
                await update.message.reply_text("Format tidak valid. Gunakan: /topkategori MM/YYYY (contoh: /topkategori 04/2025)")
                return

        month_name = get_month_name(current_month)
        
        # Ambil data terbaru (force refresh)
        response = requests.get(GOOGLE_SCRIPT_URL + "?action=getData", timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data:
            await update.message.reply_text("Belum ada data pengeluaran.")
            return

        # Filter data berdasarkan bulan/tahun
        filtered_data = [
            item for item in data 
            if item.get("tanggal") and 
            datetime.strptime(item["tanggal"], "%d-%m-%Y").month == current_month and
            datetime.strptime(item["tanggal"], "%d-%m-%Y").year == current_year
        ]

        if not filtered_data:
            await update.message.reply_text(f"Tidak ada data pengeluaran untuk {month_name} {current_year}.")
            return

        # Hitung total per kategori
        categories = defaultdict(float)
        original_names = {}
        
        for item in filtered_data:
            original_kategori = item.get("kategori", "Lainnya").strip()
            normalized_kategori = normalize_category(original_kategori)
            nominal = float(str(item.get("nominal", "0")).replace(".", "").replace(",", ""))
            categories[normalized_kategori] += nominal
            
            if normalized_kategori not in original_names:
                original_names[normalized_kategori] = original_kategori.capitalize()

        # Ambil top 5 kategori
        top5 = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]
        
        if not top5:
            await update.message.reply_text(f"Tidak ada data kategori untuk {month_name} {current_year}.")
            return

        # Buat grafik batang horizontal
        fig, ax = plt.subplots(figsize=(10, 6))
        colors = plt.cm.Blues(np.linspace(0.4, 0.8, len(top5)))
        
        bars = ax.barh(
            [original_names[k] for k, v in top5],
            [v for k, v in top5],
            color=colors,
            height=0.6
        )
        
        # Tambahkan label nilai
        ax.bar_label(bars, 
                    labels=[f"Rp{int(v):,}".replace(",", ".") for k, v in top5],
                    padding=5,
                    fontsize=9)
        
        ax.set_title(f"5 Kategori Pengeluaran Tertinggi\n{month_name} {current_year}", 
                    fontsize=12, pad=20)
        ax.set_xlabel("Total Pengeluaran", fontsize=10)
        ax.tick_params(axis='both', labelsize=9)
        ax.invert_yaxis()  # Kategori terbesar di atas
        plt.tight_layout()

        # Kirim sebagai gambar
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=120, bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        
        # Buat caption
        caption = f"🏆 Top 5 Kategori Pengeluaran {month_name} {current_year}:\n"
        for i, (k, v) in enumerate(top5, 1):
            caption += f"{i}. {original_names[k]}: Rp{int(v):,}\n".replace(",", ".")
        
        await update.message.reply_photo(
            photo=buf,
            caption=caption,
            filename=f"top_kategori_{current_month}_{current_year}.png"
        )
        log_sent(f"Mengirim top kategori {month_name} {current_year}", update.effective_user.id)

    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"⚠️ Gagal mengambil data: {str(e)}")
        logger.error(f"Request error in top_kategori: {str(e)}")
    except ValueError as e:
        await update.message.reply_text("⚠️ Format nominal tidak valid pada beberapa data")
        logger.error(f"Value error in top_kategori: {str(e)}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Terjadi kesalahan: {str(e)}")
        logger.error(f"Unexpected error in top_kategori: {str(e)}", exc_info=True)

async def kirim_pdf(update: Update, context: CallbackContext) -> None:
    log_received(update)
    log_command("/pdf", update.effective_user.id)

    try:
        # Force refresh data to get latest entries
        data = get_cached_data(force_refresh=True)
        
        if not data:
            msg = "Tidak ada data untuk dibuat PDF."
            await update.message.reply_text(msg)
            log_sent(msg, update.effective_user.id)
            return

        # Check for month/year filter parameter
        month_filter = None
        year_filter = None
        if context.args:
            try:
                month_filter, year_filter = map(int, context.args[0].split('/'))
                if not (1 <= month_filter <= 12 and 2000 <= year_filter <= 2100):
                    await update.message.reply_text("Format bulan/tahun tidak valid. Gunakan: /pdf MM/YYYY (contoh: /pdf 04/2025)")
                    return
            except:
                await update.message.reply_text("Format tidak valid. Gunakan: /pdf MM/YYYY (contoh: /pdf 04/2025)")
                return

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, 
                              rightMargin=2*cm, leftMargin=2*cm, 
                              topMargin=2*cm, bottomMargin=2*cm)
        elements = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            name='TitleStyle',
            parent=styles['Title'],
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=20
        )
        
        wrap_style = ParagraphStyle(
            name='wrap_style',
            parent=styles['Normal'],
            alignment=TA_LEFT,
            wordWrap='CJK',
            fontSize=8,
        )
        
        center_style = ParagraphStyle(
            name='center_style',
            parent=styles['Normal'],
            alignment=TA_CENTER,
            fontSize=8,
        )

        # Chart generation functions
        def generate_monthly_chart(month_data, year, month):
            import matplotlib.dates as mdates
            daily_totals = defaultdict(float)
            month_name = get_month_name(month)
            
            for item in month_data:
                tanggal = item.get("tanggal", "").strip()
                nominal_raw = str(item.get("nominal", "")).replace(".", "").replace(",", "").strip()
                nominal = float(nominal_raw) if nominal_raw.isdigit() else 0
                if nominal > 0:
                    daily_totals[tanggal] += nominal

            sorted_data = sorted(daily_totals.items(), key=lambda x: datetime.strptime(x[0], "%d-%m-%Y"))
            dates = [datetime.strptime(tgl, "%d-%m-%Y") for tgl, _ in sorted_data]
            amounts = [jumlah for _, jumlah in sorted_data]

            fig, ax = plt.subplots(figsize=(14, 6))
            bars = ax.bar(dates, amounts, color="#4285F4")

            for bar, amount in zip(bars, amounts):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(), 
                       f"Rp{int(amount):,}".replace(",", "."),
                       ha='center', va='bottom', fontsize=8)

            ax.set_ylabel("Nominal", fontsize=9)
            ax.set_title(f"Pengeluaran Harian", fontsize=10)
            ax.tick_params(axis='x', rotation=45, labelsize=8)
            ax.tick_params(axis='y', labelsize=8)
            ax.set_ylim(0, max(amounts)*1.2 if amounts else 1)

            ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%m-%Y'))

            fig.tight_layout()
            chart_buffer = BytesIO()
            plt.savefig(chart_buffer, format='png', dpi=120, bbox_inches='tight')
            chart_buffer.seek(0)
            plt.close(fig)
            return chart_buffer

        def generate_category_chart(month_data, year, month):
            categories = defaultdict(float)
            original_names = {}
            
            for item in month_data:
                original_kategori = item.get("kategori", "Lainnya").strip()
                normalized_kategori = normalize_category(original_kategori)
                nominal_raw = str(item.get("nominal", "0")).replace(".", "").replace(",", "").strip()
                nominal = float(nominal_raw) if nominal_raw else 0
                categories[normalized_kategori] += nominal
                
                if normalized_kategori not in original_names:
                    original_names[normalized_kategori] = original_kategori

            fig, ax = plt.subplots(figsize=(8, 8))
            colors = plt.cm.Pastel1(range(len(categories)))
            
            def make_autopct(values):
                def my_autopct(pct):
                    total = sum(values)
                    val = int(round(pct*total/100.0))
                    return f"{pct:.1f}%\n(Rp {val:,})".replace(",", ".")
                return my_autopct
            
            wedges, texts, autotexts = ax.pie(
                categories.values(),
                labels=[original_names[k].capitalize() for k in categories.keys()],
                autopct=make_autopct(categories.values()),
                startangle=90,
                colors=colors,
                textprops={'fontsize': 7},
                pctdistance=0.85,
                labeldistance=1.05
            )
            
            ax.set_title(f"Distribusi Kategori", fontsize=10, pad=20)
            plt.setp(autotexts, size=8, weight="bold")
            plt.tight_layout()

            buf = BytesIO()
            plt.savefig(buf, format='png', dpi=120, bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)
            return buf

        def generate_top_categories_chart(month_data, year, month):
            categories = defaultdict(float)
            original_names = {}
            
            for item in month_data:
                original_kategori = item.get("kategori", "Lainnya").strip()
                normalized_kategori = normalize_category(original_kategori)
                nominal_raw = str(item.get("nominal", "0")).replace(".", "").replace(",", "").strip()
                nominal = float(nominal_raw) if nominal_raw else 0
                categories[normalized_kategori] += nominal
                
                if normalized_kategori not in original_names:
                    original_names[normalized_kategori] = original_kategori

            top5 = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]
            
            fig, ax = plt.subplots(figsize=(12, 5))
            colors = plt.cm.Blues(np.linspace(0.5, 1, len(top5)))
            
            bars = ax.barh(
                [original_names[k].capitalize() for k, v in top5],
                [v for k, v in top5],
                color=colors
            )
            
            ax.bar_label(bars, 
                        labels=[f"Rp {int(v):,}".replace(",", ".") for k, v in top5],
                        padding=5,
                        fontsize=8)
            
            ax.set_title(f"Top 5 Kategori", fontsize=10)
            ax.tick_params(axis='both', labelsize=8)
            ax.invert_yaxis()
            plt.tight_layout()

            buf = BytesIO()
            plt.savefig(buf, format='png', dpi=120, bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)
            return buf

        # Group data by month with new data check
        monthly_data = defaultdict(list)
        monthly_totals = defaultdict(float)
        
        for item in data:
            tanggal = item.get("tanggal", "")
            if tanggal:
                try:
                    day, month, year = map(int, tanggal.split('-'))
                    nominal_raw = str(item.get("nominal", "")).replace(".", "").replace(",", "").strip()
                    nominal = float(nominal_raw) if nominal_raw.isdigit() else 0
                    
                    # Always include all valid data (removed filtering conditions)
                    monthly_data[(year, month)].append(item)
                    monthly_totals[(year, month)] += nominal
                except Exception as e:
                    logger.error(f"Error processing item: {item} - {str(e)}")
                    continue

        if not monthly_data:
            msg = "Tidak ada data yang sesuai dengan filter."
            await update.message.reply_text(msg)
            log_sent(msg, update.effective_user.id)
            return

        sorted_months = sorted(monthly_data.keys())

        # Create report for each month
        for year, month in sorted_months:
            month_name = get_month_name(month)
            month_data = monthly_data[(year, month)]
            
            # Month title
            elements.append(Paragraph(f"LAPORAN PENGELUARAN {month_name.upper()} {year}", title_style))
            elements.append(Spacer(1, 12))

            # Transactions table
            table_data = [["NO", "Tanggal", "Kategori", "Nominal", "Keterangan"]]
            month_total = 0

            for i, item in enumerate(month_data, 1):
                nominal_raw = str(item.get("nominal", "")).replace(".", "").replace(",", "").strip()
                nominal = float(nominal_raw) if nominal_raw.isdigit() else 0
                month_total += nominal
                table_data.append([
                    Paragraph(str(i), center_style),
                    Paragraph(item.get("tanggal", "-"), wrap_style),
                    Paragraph(item.get("kategori", "-"), wrap_style),
                    Paragraph(f"Rp {int(nominal):,}".replace(",", "."), wrap_style),
                    Paragraph(item.get("keterangan", "-"), wrap_style)
                ])

            col_widths = [1.5*cm, 2.5*cm, 3*cm, 2.5*cm, 6*cm]
            table = Table(table_data, repeatRows=1, colWidths=col_widths)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#4285F4")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('ALIGN', (0,0), (-1,0), 'CENTER'),
                ('VALIGN', (0,0), (-1,0), 'MIDDLE'),
                ('ALIGN', (3,1), (3,-1), 'RIGHT'),
                ('VALIGN', (0,1), (-1,-1), 'TOP'),
            ]))

            elements.append(table)
            elements.append(Spacer(1, 12))
            elements.append(Paragraph(
                f"<b>TOTAL PENGELUARAN {month_name.upper()} {year}:</b> Rp {int(month_total):,}".replace(",", "."), 
                styles["Heading3"]
            ))

            # Highest spending date analysis
            daily_totals = defaultdict(float)
            daily_items = defaultdict(list)

            for item in month_data:
                tgl = item.get("tanggal", "").strip()
                nominal_raw = str(item.get("nominal", "")).replace(".", "").replace(",", "").strip()
                nominal = float(nominal_raw) if nominal_raw.isdigit() else 0
                daily_totals[tgl] += nominal
                daily_items[tgl].append(item)

            if daily_totals:
                tanggal_terbanyak = max(daily_totals, key=daily_totals.get)
                jumlah_terbanyak = daily_totals[tanggal_terbanyak]

                transaksi_detail = []
                for item in daily_items[tanggal_terbanyak]:
                    kategori = item.get("kategori", "Lainnya").strip()
                    nominal_raw = str(item.get("nominal", "")).replace(".", "").replace(",", "").strip()
                    nominal = float(nominal_raw) if nominal_raw.isdigit() else 0
                    keterangan = item.get("keterangan", "-")
                    transaksi_detail.append({
                        'kategori': kategori,
                        'nominal': nominal,
                        'keterangan': keterangan
                    })

                elements.append(Spacer(1, 12))
                elements.append(Paragraph(
                    f"<b>Pengeluaran tertinggi pada bulan {month_name} terjadi pada tanggal {tanggal_terbanyak} dengan total sebesar:</b> Rp {int(jumlah_terbanyak):,}".replace(",", "."),
                    styles["Normal"]
                ))

                elements.append(Spacer(1, 6))
                elements.append(Paragraph(f"<b>Berikut rincian pengeluarannya:</b>", styles["Normal"]))

                for i, transaksi in enumerate(transaksi_detail, 1):
                    elements.append(Paragraph(
                        f"{i}. Kategori: {transaksi['kategori']}<br/>"
                        f"&nbsp;&nbsp;&nbsp;&nbsp;Total: Rp {int(transaksi['nominal']):,}<br/>"
                        f"&nbsp;&nbsp;&nbsp;&nbsp;Keterangan: {transaksi['keterangan']}".replace(",", "."),
                        styles["Normal"]
                    ))
                    elements.append(Spacer(1, 6))

            # Move charts to new page
            elements.append(PageBreak())
            elements.append(Paragraph(f"ANALISIS PENGELUARAN {month_name.upper()} {year}", title_style))
            elements.append(Spacer(1, 12))

            # Daily chart
            daily_chart = generate_monthly_chart(month_data, year, month)
            elements.append(RLImage(daily_chart, width=15*cm, height=7*cm))
            elements.append(Spacer(1, 0.5*cm))
            
            # Category pie chart
            category_chart = generate_category_chart(month_data, year, month)
            elements.append(RLImage(category_chart, width=10*cm, height=10*cm))
            elements.append(Spacer(1, 0.5*cm))
            
            # Top categories chart
            top_categories_chart = generate_top_categories_chart(month_data, year, month)
            elements.append(RLImage(top_categories_chart, width=15*cm, height=5*cm))

            if (year, month) != sorted_months[-1]:
                elements.append(PageBreak())

        # Monthly comparison for multi-month reports
        if len(sorted_months) > 1 and not month_filter:
            elements.append(PageBreak())
            elements.append(Paragraph("PERBANDINGAN BULANAN", title_style))
            elements.append(Spacer(1, 12))
            
            months = [f"{get_month_name(m)} {y}" for y, m in sorted_months]
            amounts = [monthly_totals[(y, m)] for y, m in sorted_months]

            fig, ax = plt.subplots(figsize=(14, 6))
            bars = ax.bar(months, amounts, color="#34A853")

            for bar, amount in zip(bars, amounts):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(), 
                       f"Rp{int(amount):,}".replace(",", "."),
                       ha='center', va='bottom', fontsize=8)

            ax.set_title("Perbandingan Pengeluaran Bulanan", fontsize=10)
            ax.tick_params(axis='x', rotation=45, labelsize=8)
            ax.set_ylim(0, max(amounts)*1.2 if amounts else 1)
            plt.tight_layout()

            chart_buffer = BytesIO()
            plt.savefig(chart_buffer, format='png', dpi=120, bbox_inches='tight')
            chart_buffer.seek(0)
            plt.close(fig)
            
            elements.append(RLImage(chart_buffer, width=15*cm, height=7*cm))

        doc.build(elements)
        buffer.seek(0)

        caption = "Laporan pengeluaran lengkap"
        if month_filter:
            caption += f" untuk {get_month_name(month_filter)} {year_filter}"
        
        await update.message.reply_document(
            document=buffer,
            filename="laporan_pengeluaran.pdf",
            caption=caption
        )
        log_sent(f"Mengirim laporan PDF {caption}", update.effective_user.id)

    except Exception as e:
        logger.error(f"Error in kirim_pdf: {str(e)}", exc_info=True)
        await update.message.reply_text(f"⚠️ Gagal membuat PDF: {str(e)}")

# ===== Error Handler =====
async def error_handler(update: object, context: CallbackContext) -> None:
    """Handle errors"""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    if not update or not hasattr(update, 'message'):
        return
        
    try:
        if isinstance(context.error, NetworkError):
            await update.message.reply_text("⚠️ Terjadi masalah koneksi, silakan coba lagi nanti")
        elif isinstance(context.error, requests.exceptions.Timeout):
            await update.message.reply_text("⏱ Waktu koneksi habis, silakan coba lagi")
        elif isinstance(context.error, BadRequest):
            if "Message is too long" in str(context.error):
                await update.message.reply_text("📝 Data terlalu panjang, gunakan /pdf untuk laporan lengkap")
            else:
                await update.message.reply_text(f"⚠️ Permintaan tidak valid: {context.error}")
        else:
            await update.message.reply_text(f"⚠️ Terjadi kesalahan tak terduga: {context.error}")
    except Exception as e:
        logger.error(f"Error in error handler: {e}")

# ===== Main =====
def main():
    """Start the bot"""
    logger.info("Starting bot...")
    print("Bot is running.")

    app = Application.builder().token(TOKEN).build()
    
    # Error handler
    app.add_error_handler(error_handler)
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("info", lihat_data))
    app.add_handler(CommandHandler("pdf", kirim_pdf))
    app.add_handler(CommandHandler("grafik", kirim_grafik))
    app.add_handler(CommandHandler("kategori", kategori_pie))
    app.add_handler(CommandHandler("topkategori", top_kategori))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Job queues
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(backup_data, interval=86400, first=10)  # Backup daily
        job_queue.run_repeating(check_updates, interval=86400, first=60)  # Check updates daily

    try:
        app.run_polling()
    except Exception as e:
        logger.error(f"Bot stopped: {e}")
    finally:
        logger.info("Bot stopped")

if __name__ == '__main__':
    main()