/*
   ESP32-C3 Ultra-Minimal BLE Scanner
   Optimizado para memoria flash limitada
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <BLEDevice.h>
#include <BLEScan.h>

const char* ssid = "CLARO_GOMEZ_2.4_Ext";
const char* pass = "0906119946001";
const char* url = "http://52.21.215.130:8000/esp32/data";

BLEScan* scan;
int rssi1 = -999;
int rssi2 = -999;
bool found1 = false;
bool found2 = false;

bool isUCSG(String n) {
  return n == "UCSG1" || n == "UCSG2";
}

void wifi() {
  WiFi.begin(ssid, pass);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    attempts++;
  }
}

void send(String beaconName, int rssi) {
  if (WiFi.status() != WL_CONNECTED) return;
  
  String payload = "{\"esp32_id\":\"ESP32_003\",\"rssi\":" + String(rssi) + ",\"beacon_name\":\"" + beaconName + "\"}";
  
  HTTPClient h;
  h.begin(url);
  h.addHeader("Content-Type", "application/json");
  h.setTimeout(5000);
  
  h.POST(payload);
  h.end();
}

class CB : public BLEAdvertisedDeviceCallbacks {
  void onResult(BLEAdvertisedDevice d) {
    if (d.haveName() && isUCSG(d.getName().c_str())) {
      String name = d.getName().c_str();
      int r = d.getRSSI();
      
      if (name == "UCSG1") {
        rssi1 = r;
        found1 = true;
      } else if (name == "UCSG2") {
        rssi2 = r;
        found2 = true;
      }
    }
  }
};

void setup() {
  Serial.begin(115200);
  
  WiFi.mode(WIFI_STA);
  wifi();
  
  BLEDevice::init("");
  scan = BLEDevice::getScan();
  scan->setAdvertisedDeviceCallbacks(new CB());
  scan->setActiveScan(true);
  scan->setInterval(300);
  scan->setWindow(150);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) wifi();
  
  rssi1 = -999;
  rssi2 = -999;
  found1 = false;
  found2 = false;
  
  BLEScanResults* results = scan->start(5, false);
  
  if (found1) send("UCSG1", rssi1);
  if (found2) send("UCSG2", rssi2);
  
  scan->clearResults();
  delay(3000);
}