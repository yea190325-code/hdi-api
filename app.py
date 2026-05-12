from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from requests.auth import HTTPBasicAuth
import xml.etree.ElementTree as ET
import datetime
import re

app = Flask(__name__)
CORS(app)

# --- API KİMLİK BİLGİLERİ (HDI'den Gelenler) ---
CLIENT_ID = "SGmMJGYyNCcVlR4FpdyV717Io08a"
CLIENT_SECRET = "o_U44kFrwU7TdpbGUCCofE2eje4a"

# Legacy bilgiler (XML içinde gönderilecek)
HDI_USER = "WS36570000" 
HDI_PWD = "8yZD37pb"

# API URL'leri (Test Ortamı)
# Canlıya çıkarken 'apimtest' kısımlarını 'apim' olarak değiştirmeyi unutma.
TOKEN_URL = "https://apim.hdisigorta.com.tr/hdi/token"
HDI_API_URL = "https://apim.hdisigorta.com.tr/hdi/acente/police/uretim/kasko/legacy/hesapla"

def get_hdi_token():
    """HDI Token servisinden Basic Auth ile Access Token alır."""
    try:
        # Dokümandaki 1. Adım: ClientKey ve Secret ile Basic Auth
        response = requests.get(TOKEN_URL, auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET))
        response.raise_for_status()
        token_data = response.json()
        
        # Dokümandaki 2. Adım: access_token alanını döndür
        return token_data.get("access_token")
    except Exception as e:
        print("Token Alınamadı:", str(e))
        return None

@app.route('/api/fiyat-al', methods=['POST'])
def fiyat_al():
    data = request.json
    
    tc_no = data.get('tcNo')
    dogum_tarihi = data.get('dogumTarihi')
    plaka = data.get('plaka')
    tescil_no = data.get('tescilNo')
    
    # Plaka ayrıştırma (Örn: 25 -> il, ABC123 -> kod)
    plaka_match = re.match(r"(\d{2})([A-Z0-9]+)", plaka.replace(" ", ""))
    if not plaka_match:
        return jsonify({"success": False, "message": "Geçersiz plaka formatı."})
    
    plaka_il = plaka_match.group(1)
    plaka_kod = plaka_match.group(2)
    
    # Doğum yılı ve bugünün tarihi
    dogum_yili = dogum_tarihi.split('.')[-1] if '.' in dogum_tarihi else ""
    bugun = datetime.datetime.now().strftime("%d%m%Y")

    # XML Gövdesi (Legacy parametreler)
    xml_body = f"""<HDISIGORTA>
        <user>{HDI_USER}</user>
        <pwd>{HDI_PWD}</pwd>
        <Uygulama>PRKZ777</Uygulama>
        <IstekTip>P</IstekTip>
        <Tarih>{bugun}</Tarih>
        <OzelTuzel>O</OzelTuzel>
        <TcKimlikNo>{tc_no}</TcKimlikNo>
        <MSDogYL>{dogum_yili}</MSDogYL>
        <PlakailKod>{plaka_il}</PlakailKod>
        <PlakaKod2>{plaka_kod}</PlakaKod2>
        <ASBISNo>{tescil_no}</ASBISNo>
        <Uyruk>0</Uyruk>
    </HDISIGORTA>"""

    # --- 1. TOKEN ALMA İŞLEMİ ---
    access_token = get_hdi_token()
    if not access_token:
        return jsonify({"success": False, "message": "HDI Sistemine güvenlik yetkilendirmesi yapılamadı (Token Hatası)."})

    # --- 2. ASIL İSTEĞİ ATMA İŞLEMİ (Bearer Auth ile) ---
    headers = {
        'Authorization': f'Bearer {access_token}', # Dokümandaki 4. Adım
        'Content-Type': 'application/xml',
        'Accept': 'application/xml'
    }

    try:
        response = requests.get(HDI_API_URL, params={'xmlData': xml_body}, headers=headers)
        response.raise_for_status()
        
        # Yanıtı çözümle
        root = ET.fromstring(response.content)
        
        # Hata kontrolü
        hata_mesaji = root.findtext('.//HataMesaji') or root.findtext('.//Mesaj')
        if hata_mesaji and "Hata" in str(root.findtext('.//HataKodu')):
            return jsonify({"success": False, "message": hata_mesaji})
            
        prim = root.findtext('.//BrutPrim') or root.findtext('.//OdenecekPrim')
        
        if prim:
            return jsonify({"success": True, "fiyat": prim})
        else:
            return jsonify({"success": False, "message": "Fiyat bilgisi alınamadı. Müşteri bilgilerini kontrol ediniz."})

    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "message": f"Bağlantı Hatası: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)