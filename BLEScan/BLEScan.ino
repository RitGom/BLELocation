/*
   ESP32-D0WDQ6 Ultra-minimal BLE Scanner 
   Optimizado para 1MB Flash - VERSIÓN CORREGIDA
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <BLEDevice.h>
#include <BLEScan.h>

const char* ssid = "CLARO_GOMEZ_2.4";
const char* pass = "0906119946001";
const char* url = "http://52.21.215.130:8000/esp32/data";

BLEScan* scan;

// Variables para los dos beacons
int rssi1 = -999;
int rssi2 = -999;
bool found1 = false;
bool found2 = false;

bool isUCSG(String n) {
  return n == "UCSG1" || n == "UCSG2";
}

void wifi() {
  Serial.println("Conectando WiFi...");
  WiFi.begin(ssid, pass);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi conectado: " + WiFi.localIP().toString());
  } else {
    Serial.println("\nError: WiFi no conectado");
  }
}

void send(String beaconName, int rssi) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Error: Sin WiFi para enviar");
    return;
  }
  
  String payload = "{\"esp32_id\":\"ESP32_001\",\"rssi\":" + String(rssi) + ",\"beacon_name\":\"" + beaconName + "\"}";
  Serial.println("Enviando: " + payload);
  
  HTTPClient h;
  h.begin(url);
  h.addHeader("Content-Type", "application/json");
  h.setTimeout(5000);
  
  int httpCode = h.POST(payload);
  
  if (httpCode > 0) {
    Serial.println("HTTP: " + String(httpCode));
    if (httpCode == 200) {
      String response = h.getString();
      Serial.println("Respuesta: " + response);
    }
  } else {
    Serial.println("Error HTTP: " + String(httpCode));
  }
  h.end();
}

class CB : public BLEAdvertisedDeviceCallbacks {
  void onResult(BLEAdvertisedDevice d) {
    if (d.haveName()) {
      String name = d.getName().c_str();
      Serial.println("BLE encontrado: " + name + " RSSI: " + String(d.getRSSI()));
      
      if (isUCSG(name)) {
        int r = d.getRSSI();
        Serial.println("UCSG detectado! RSSI: " + String(r));
        
        if (name == "UCSG1") {
          rssi1 = r;
          found1 = true;
        } else if (name == "UCSG2") {
          rssi2 = r;
          found2 = true;
        }
      }
    }
  }
};

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("Iniciando ESP32 BLE Scanner...");
  
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(true);
  wifi();
  
  Serial.println("Inicializando BLE...");
  BLEDevice::init("");
  scan = BLEDevice::getScan();
  scan->setAdvertisedDeviceCallbacks(new CB());
  scan->setActiveScan(true);
  scan->setInterval(100);
  scan->setWindow(99);
  
  Serial.println("Sistema listo");
}

void loop() {
  Serial.println("\n=== Nuevo ciclo ===");
  
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Reconectando WiFi...");
    wifi();
  }

  rssi1 = -999;
  rssi2 = -999;
  found1 = false;
  found2 = false;
  
  Serial.println("Iniciando scan BLE (3s)...");
  BLEScanResults* results = scan->start(3, false);
  
  Serial.println("Scan completado. Dispositivos: " + String(results->getCount()));
  
  if (found1) {
    Serial.println("UCSG1 encontrado, enviando datos...");
    send("UCSG1", rssi1);
  }
  
  if (found2) {
    Serial.println("UCSG2 encontrado, enviando datos...");
    send("UCSG2", rssi2);
  }
  
  if (!found1 && !found2) {
    Serial.println("No se encontraron dispositivos UCSG");
  }

  scan->clearResults();
  delay(5000);
}