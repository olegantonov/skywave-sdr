"""Fetch public manufacturer references; keep redistribution separate from our design."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "hardware/library"
SOURCES = {
    "esp32": "https://www.espressif.com/sites/default/files/documentation/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf",
    "codec": "https://www.ti.com/lit/ds/symlink/tlv320aic3204.pdf",
    "codec_design": "https://www.ti.com/lit/ml/slaa557/slaa557.pdf",
    "si5351": "https://www.skyworksinc.com/-/media/SkyWorks/SL/documents/public/data-sheets/Si5351-B.pdf",
    "mixer": "https://www.ti.com/lit/ds/symlink/sn74cbt3253.pdf",
    "flipflop": "https://assets.nexperia.com/documents/data-sheet/74LVC74A.pdf",
    "opamp": "https://www.ti.com/lit/ds/symlink/tlv9064.pdf",
    "audio_mux": "https://www.ti.com/lit/ds/symlink/cd74hc4052.pdf",
    "audio_amp": "https://www.ti.com/lit/ds/symlink/lm386.pdf",
    "ldo": "https://www.ti.com/lit/ds/symlink/lm1117.pdf",
    "esd": "https://www.st.com/resource/en/datasheet/usblc6-2.pdf",
    "mosfet": "https://assets.nexperia.com/documents/data-sheet/2N7002.pdf",
    "diode": "https://assets.nexperia.com/documents/data-sheet/1N4148W_1N4448W.pdf",
    "usb": "https://gct.co/files/drawings/usb4105.pdf",
    "vhf": "https://www.dorji.com/docs/data/DRA818V.pdf",
    "uhf": "https://www.dorji.com/docs/data/DRA818U.pdf",
    "ldo18": "https://www.ti.com/lit/ds/symlink/tlv755p.pdf",
    "rf_inductor": "https://www.coilcraft.com/getmedia/dd5f20e4-1ff7-43df-8317-b693eb2dce3e/0805cs.pdf",
    "buck": "https://www.ti.com/lit/ds/symlink/tps62160.pdf",
    "decoder": "https://www.ti.com/lit/ds/symlink/sn74hc139.pdf",
    "nand": "https://www.ti.com/lit/ds/symlink/sn74lvc1g00.pdf",
    "inverter": "https://www.ti.com/lit/ds/symlink/sn74lvc1g04.pdf",
    "relay": "https://omronfs.omron.com/en_US/ecb/products/pdf/en-g6k.pdf",
    "tantalum": "https://search.kemet.com/download/specsheet/T491B226K016AT",
    "uart_buffer": "https://www.ti.com/lit/ds/symlink/sn74lvc1g17.pdf",
    "vishay_resistors": "https://www.vishay.com/docs/20035/dcrcwe3.pdf",
    "samtec_headers": "https://suddendocs.samtec.com/catalog_english/tsw.pdf",
    "buttons": "https://omronfs.omron.com/en_US/ecb/products/pdf/en-b3f.pdf",
    "volume": "https://www.bourns.com/docs/product-datasheets/3296.pdf",
    "crystal": "https://abracon.com/Resonators/abm8.pdf",
    "power_inductor": "https://product.tdk.com/system/files/dam/doc/product/inductor/inductor/smd/catalog/inductor_commercial_power_vls3015et_en.pdf",
}
PAGES = {
    'electrolytic':'https://industrial.panasonic.com/tw/products/pt/aluminum-cap-lead/models/EEUFR1A221',
    'kemet_capacitors':'https://www.kemet.com/en/us/capacitors/ceramic.html',
    'sma':'https://www.amphenolrf.com/en-us/part/132289/1030/',
}

def fetch(item):
    name, url = item
    path = LIB / (name + ".pdf")
    record = dict(id=name, url=url, file=str(path.relative_to(ROOT)), redistributed=False,
                  accessed_date='2026-10-12', tls_verified=name not in ('vhf','uhf'))
    if name in ('vhf','uhf'):
        record['acquisition_note']='Publisher certificate validation failed; cached public PDF originally obtained with curl -k. Hash is integrity tracking, not authentication.'
    try:
        if not path.exists():
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=25) as response:
                data = response.read()
            if not data.startswith(b"%PDF"):
                raise ValueError("Response is not PDF")
            path.write_bytes(data)
        record.update(status="downloaded", sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        subprocess.run(["pdftotext", "-layout", str(path), str(path.with_suffix(".txt"))], check=True, capture_output=True)
    except Exception as error:
        record.update(status="failed", error=str(error))
    return record

if __name__ == "__main__":
    LIB.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        records = list(pool.map(fetch, SOURCES.items()))
    records += [dict(id=n,url=u,status='manufacturer_reference',accessed_date='2026-10-12',
        redistributed=False,note='Ordering-code and dimensional review remains necessary.') for n,u in PAGES.items()]
    (ROOT / "hardware/d1/sources.json").write_text(json.dumps(records, indent=2) + "\n")
    for row in records:
        print(row["id"], row["status"], row.get("error", ""))
