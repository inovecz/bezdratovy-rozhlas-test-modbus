# 1. Kompletní specifikace binárních zpráv JSVV

## 1.1 Formát a rámcování zpráv 
Komunikace v jednotném systému varování a vyrozumění (JSVV) probíhá formou strukturovaných zpráv ve formátu ASCII. Každá zpráva je tvořena **rámcem** s pevně danou strukturou a oddělovacími znaky:

- **Znaková forma přenosu:** Všechny hodnoty jsou přenášeny jako tisknutelné znaky ASCII (0x00–0x7F). Číselné údaje jsou tedy posílány jako řetězce číslic (např. číslo `1` je přeneseno jako znak `'1'` s kódem 0x31). 
- **Struktura rámce:** Každá zpráva se skládá z **identifikátoru zprávy (MID)** následovaného případnými **datovými položkami (DATA)**. Obecné schéma je:  
  `[MID] [D1] [D2] ... [Dx]`  
- **Oddělovače:** Jednotlivé části zprávy (MID a datové bloky) jsou odděleny jednou mezerou (ASCII 0x20). 
- **Zahájení a ukončení zprávy:** Rámec zprávy je ukončen speciálním znakem **newline (LF, 0x0A)**. 
- **Příklad rámce:**  
  ```
  INIT OP1 1000

  ```  

## 1.2 Identifikátory a adresace 
Každá zpráva obsahuje (přímo či nepřímo) tyto identifikátory:

- **ID sítě:** 1–255 (krajský subsystém).  
- **ID VyC (vyrozumívací centrum):** 1–255.  
- **ID operátora:** 1–65535 (max 1000 současných).  
- **Adresa KPPS:** 0–65534 (0xFFFF = vyhrazeno). KPPS podporuje více adres: individuální, územní, krajskou a skupinové adresy A1–A16, B1–B16.  

Časové značky jsou ve formátu **Unix time (UINT64)**. RTC musí být synchronizován, odchylka max. ±3 s/den.

## 1.3 Typy zpráv a příkazů z VyC 

### Aktivační příkazy
| Příkaz | Popis | Parametry | Priorita |
|--------|-------|-----------|----------|
| Signál sirény | Aktivace akustického signálu (3 typy tónů) | kód signálu (1–3) | P2 |
| Znělka (gong) | Znělka 1 (start) nebo 2 (konec) | typ (1–2) | P3 |
| Verbální informace | Přehrání nahrané hlášky | číslo hlášení (1–20) | P2 |
| Připojení rozhlasu | Přesměrování audio z rádia | – | P3 |
| Vzdálený hlas (VyC) | Živý mikrofon z centra | – | P3 |
| Místní hlas | Aktivace místního mikrofonu | – | P3 |
| Externí audio zdroj | Připojení primárního externího zdroje | – | P3 |
| Sekundární ext. audio | Připojení sekundárního externího zdroje | – | P3 |
| Text pro panel | Text 1–128 znaků na informační panel | text | P3 |
| STOP | Okamžité ukončení činnosti | – | P1 |
| RESET | Reset systému, vyprázdnění front | – | P1 |
| TEST | Tichý test funkčnosti | – | P3 |

### Stavové a diagnostické dotazy
| Dotaz | Popis | Priorita |
|-------|-------|----------|
| Dotaz stav EKPV | Vrátí stav sirény/panelu | P1 |
| Dotaz stav KPM | Stav koncového prvku měření | P1 |
| Dotaz vadné hlásiče MIS | Seznam chybných hlásičů MIS | P1 |
| Dotaz stav KPPS | Diagnostika KPPS (napájení, paměť, komunikace) | P1 |
| Dotaz adresy (`READ_ADR`) | Seznam všech 35 adres KPPS | P1 |
| Dotaz konfigurace (`READ_CFG`) | Konfigurace provozních parametrů | P1 |
| Dotaz záznamů (`READ_LOG`) | Log posledních událostí | P1 |

### Konfigurační příkazy
| Příkaz | Popis | Priorita |
|--------|-------|----------|
| `SET_CFG` | Nastavení konfigurace KPPS | P1 |
| `SET_ADR` | Nastavení všech adres KPPS | P1 |
| `SET_KEYS` | Nahrání šifrovacích klíčů AES-256 | P1 |
| `FRESET` | Tovární reset | P1 |
| Servisní příkazy (`INIT`, `PING`, `READ_DIAG`, ...) | Lokální servisní komunikace | P1 |

## 1.4 Kontrolní součet (CRC)
- Algoritmus: **CRC-16-CCITT** (0x1021, init=0x0000, bez invertování).  
- Vstup: všechny znaky zprávy kromě koncového newline.  
- Výstup: 4 hex číslice ASCII.  
- Příklad: `INIT OP1 1000` → CRC = 0x004B → `CRC 004B`.

## 1.5 Detekce duplicit a ztrát zpráv 
- **Detekce duplicit:** kombinace typu příkazu + parametry + ID operátora + timestamp. Blokace duplicit (výchozí 180 s, nastavitelná 30–300 s).  
- **Ztráty zpráv:** řeší se opakováním vysílání, automatickými hlášeními a parametrem MER (Message Error Rate).  
- **Chybné zprávy:** CRC error nebo špatný formát → odmítnout a zalogovat.
