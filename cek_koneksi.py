import requests
import socket
from urllib.parse import quote

TOKEN = "isi dengan token anda"  # Ganti dengan token bot Anda

def test_connection():
    try:
        print("1. Testing basic internet connection...")
        socket.create_connection(("api.telegram.org", 443), timeout=10)
        print("✅ Berhasil terhubung ke api.telegram.org")

        print("\n2. Testing Telegram bot API...")
        url = f"https://api.telegram.org/bot{TOKEN}/getMe"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            print(f"✅ Koneksi bot berhasil! Respon: {response.json()}")
        else:
            print(f"❌ Gagal. Kode status: {response.status_code}, Respon: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error koneksi: {str(e)}")
    except Exception as e:
        print(f"❌ Error tak terduga: {str(e)}")

if __name__ == "__main__":
    test_connection()