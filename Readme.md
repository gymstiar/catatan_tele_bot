# 📘 Catatan Tele Bot

Bot Telegram untuk mencatat pengeluaran, menyimpan data ke Google Spreadsheet, dan membuat laporan otomatis (tabel, grafik, PDF).

---

## 🧩 Fitur Utama

* Mencatat pengeluaran langsung lewat Telegram
* Menyimpan data ke Google Spreadsheet via Apps Script
* Generate PDF laporan (reportlab)
* Grafik pengeluaran (matplotlib)
* Multi-user (otomatis memisahkan data per pengguna)
* Bot berjalan otomatis 24/7 (jika di-hosting)

---

# 🏁 1. PERSIAPAN DASAR

## 1.1 Buat Google Spreadsheet

1. Buka: [https://docs.google.com/spreadsheets](https://docs.google.com/spreadsheets)
2. Buat spreadsheet baru
3. Beri nama: **catatan_pengeluaran**
4. Buat sheet bernama **Sheet1**
5. Tambahkan header berikut:

```
Tanggal | Nominal | Kategori | Keterangan
```

---

# 🛠 2. BUAT GOOGLE APPS SCRIPT

## 2.1 Buka Apps Script

1. Di Google Spreadsheet → **Extensions > Apps Script**
2. Hapus semua kode bawaan
3. Tempelkan script berikut:

---

## 📜 CODE.GS (HARUS DISALIN DI APPS SCRIPT)

```javascript
function doPost(e) {
    var sheet = SpreadsheetApp.openById("isi dengan id Spreadsheet").getSheetByName("Sheet1");
    var data = JSON.parse(e.postData.contents);
    
    var waktu = new Date();
    var tanggal = Utilities.formatDate(waktu, "GMT+7", "dd-MM-yyyy"); // Format tanggal
    var nominal = data.nominal;
    var kategori = data.kategori;
    var keterangan = data.keterangan;
    
    sheet.appendRow([waktu, nominal, kategori, keterangan]);

    // Format response
    var responseMessage = `Catatan dengan deskripsi : \n\n` +
                          `📅 Tanggal : ${tanggal}\n` +
                          `🏷 Kategori : ${kategori}\n` +
                          `💰 Nominal : Rp. ${Number(nominal).toLocaleString("id-ID")}\n` +
                          `📝 Keterangan : ${keterangan}\n\n` +
                          `Berhasil disimpan ✅  \n\n` +
                          
                          'WARNING: Jangan boros boros yaahh ☺️';

    return ContentService.createTextOutput(responseMessage);
}

function doGet(e) {
  var action = e.parameter.action;
  if (action === "getData") {
    return getData();
  }
}

function getData() {
  var sheet = SpreadsheetApp.openById("id_spreadsheet").getSheetByName("Sheet1");
  var data = sheet.getDataRange().getValues();
  
  var result = [];
  for (var i = 1; i < data.length; i++) {  // Mulai dari baris kedua (tanpa header)
    var tanggal = Utilities.formatDate(new Date(data[i][0]), "GMT+7", "dd-MM-yyyy"); // Format tanggal
    result.push({
      tanggal: tanggal, 
      nominal: data[i][1],  
      kategori: data[i][2],  
      keterangan: data[i][3]  
    });
  }
  
  return ContentService.createTextOutput(JSON.stringify(result))
                       .setMimeType(ContentService.MimeType.JSON);
}

```

---

## 2.2 Isi Spreadsheet ID

Spreadsheet ID ada pada URL:

```
https://docs.google.com/spreadsheets/d/1ABCdefGhijkLmNoPQRstuVWxyz12345/edit
                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                      ini ID Spreadsheet
```

Ganti:

```
ID_SPREADSHEET_KAMU
```

dengan ID milik kamu.

---

## 2.3 Deploy sebagai Web App

1. Klik **Deploy** (kanan atas)
2. Pilih **New Deployment**
3. Deployment type → **Web app**
4. Akses → **Anyone**
5. Klik **Deploy**
6. Copy URL berikut:

Contoh:

```
https://script.google.com/macros/s/AKfycbyl3ABC123xyz7890/exec
```

Simpan → nanti dimasukkan ke `.env`

---

# 🧾 3. MEMBUAT TELEGRAM BOT

## 3.1 Buka BotFather

1. Buka Telegram → cari **@BotFather**
2. Kirim:

```
/newbot
```

3. Ikuti instruksi
4. Dapatkan **TOKEN** seperti:

```
123456:ABCDEF-ghijklmnop
```

---

# 🌱 4. SETUP ENVIRONMENT PYTHON

## 4.1 Clone Repository

```bash
git clone https://github.com/gymstiar/catatan_tele_bot.git
cd catatan_tele_bot
```

---

## 4.2 Buat Virtual Environment

```bash
python -m venv venv
```

Aktifkan:

**Windows**

```bash
venv\Scripts\activate
```

**Linux/Mac**

```bash
source venv/bin/activate
```

---

## 4.3 Install Requirements

```bash
pip install -r requirements.txt
```

---

# 🔑 5. BUAT FILE `.env`

Buat file `.env` di folder project:

```
TELEGRAM_BOT_TOKEN=MASUKKAN_TOKEN_BOT_KAMU
GOOGLE_SCRIPT_URL=MASUKKAN_URL_APPS_SCRIPT_EXEC
```

Contoh:

```
TELEGRAM_BOT_TOKEN=123456:ABCDEF-ghijk
GOOGLE_SCRIPT_URL=https://script.google.com/macros/s/AKfycbxxxxx/exec
```

---

# ▶️ 6. MENJALANKAN BOT

Jalankan:

```bash
python bot2.py
```

Jika benar, terminal menampilkan:

```
Bot sedang berjalan...
```

Di Telegram → buka bot → ketik:

```
/help
```

---

# 🧪 7. CARA MENCATAT PENGELUARAN

Format input:

```
25000, Jajan, nasi ayam
```

Atau:

```
13000, Transport, gojek
```

Bot akan:

* menyimpan ke Google Sheet
* menampilkan ringkasan
* mengupdate total pengeluaran

---

# 📝 8. MEMBUAT LAPORAN PDF

Perintah:

```
/laporan
```

Bot akan mengirimkan:

* PDF lengkap
* grafik pengeluaran
* tabel kategori

Perintah:

```
/help
```

Akan menampilkan semua menu bot.

---

# ❗ 9. TROUBLESHOOTING

### **1. Data tidak masuk ke Google Sheet**

✔ Web App diset **Anyone**
✔ URL berakhiran `/exec`
✔ ID Spreadsheet benar
✔ Sheet bernama **Sheet1**

---

### **2. Token tidak terbaca**

Tes:

```python
import os; print(os.getenv("TELEGRAM_BOT_TOKEN"))
```

Jika `None` → masalah:

* `.env` salah
* tidak ada `load_dotenv()`
* penempatan `.env` salah

---

### **3. Bot tidak merespon**

* Token salah
* Script Python berhenti
* Belum klik **Start** di Telegram

---

### **4. Error Apps Script**

Error:

```
TypeError: Cannot read property 'contents' of undefined
```

Solusi → pastikan request menggunakan:

```python
requests.post(GOOGLE_SCRIPT_URL, json=data)
```

---

# 🎯 10. Selesai!

Bot ini sekarang siap digunakan untuk:

* mencatat pengeluaran harian
* menyimpan otomatis ke Google Sheet
* membuat laporan rapi (grafik + PDF)

---


