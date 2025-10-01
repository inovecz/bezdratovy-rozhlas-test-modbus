# 6. Referenční tabulky a slovníky

Tato kapitola obsahuje kompletní tabulky extrahované ze specifikace JSVV, nutné pro implementaci parseru, backendu a řízení Modbus. Jsou zde vyjmenovány všechny typy zpráv, stavových dotazů, automatických hlášení, adresace a SLA parametry.

## 6.1 Typy zpráv a příkazů z VyC → KPPS (aktivace)

| Příkaz | Parametry | Rozsah | Jednotky | Priorita | Poznámka |
|--------|-----------|--------|-----------|----------|----------|
| Signál sirény | `signalType` | 1–3 | kód (typ tónu) | P2 | 3 různé tóny (např. varovný, požární, zkouška) |
| Znělka (gong) | `gongType` | 1–2 | – | P3 | Gong 1 = začátek, Gong 2 = konec |
| Verbální informace | `slot` | 1–20 | index hlášky | P2 | min. 20 nahraných hlášek |
| Připojení rozhlasu | – | – | – | P3 | připojení na rozhlasový přijímač |
| Vzdálený hlas | – | – | – | P3 | živý mikrofon z VyC |
| Místní hlas | – | – | – | P3 | mikrofon lokálně |
| Externí audio (primární) | – | – | – | P3 | |
| Externí audio (sekundární) | – | – | – | P3 | |
| Text pro panel | `text` | 1–128 znaků | UTF-8 | P3 | zobrazení na LED panelu |
| STOP | – | – | – | P1 | okamžité ukončení |
| RESET | – | – | – | P1 | tovární reset |
| TEST | – | – | – | P3 | tichý test |

## 6.2 Stavové dotazy a odpovědi

| Dotaz | Odpověď – pole | Jednotky | Priorita |
|-------|----------------|----------|----------|
| Stav EKPV | `sirenaStatus`, `panelStatus` | bool | P1 |
| Stav KPM | `napajeni`, `signal`, `teplota` | V, dB, °C | P1 |
| Vadné hlásiče MIS | `ids[]` | seznam ID | P1 |
| Stav KPPS | `napajeni`, `paměť`, `signalStrength` | V, B, dB | P1 |
| Adresy (`READ_ADR`) | `adr[35]` | hex | P1 |
| Konfigurace (`READ_CFG`) | `interval`, `blockTime`, `retry`, `AESkeyId` | s | P1 |
| Záznamy (`READ_LOG`) | `logEntries[]` | – | P1 |

## 6.3 Automatická hlášení (faults/alarms)

| Hlásící prvek | Stav | Parametry | Priorita |
|---------------|------|-----------|----------|
| KPPS | Porucha napájení | napětí < limit | P1 |
| KPPS | Přetížení | proud > limit | P1 |
| KPPS | Otevření skříně | switch=1 | P1 |
| EKPV | Porucha sirény | stav=FAULT | P1 |
| EKPV | Porucha panelu | stav=FAULT | P1 |
| KPM | Teplota mimo rozsah | > 85 °C | P1 |
| Baterie | Nízké napětí | < 11.5 V | P1 |
| Audio | Ztráta signálu | SNR < 10 dB | P1 |

## 6.4 Adresace a identifikátory

| Pole | Formát | Rozsah | Poznámka |
|------|--------|--------|----------|
| ID sítě | číslo | 1–255 | krajský subsystém |
| ID VyC | číslo | 1–255 | centrum |
| ID operátora | číslo | 0–65535 | max 1000 současných |
| Adresa KPPS | číslo/hex | 0–65534 | 0xFFFF vyhrazeno |
| Skupinové adresy A1–A16 | hex | definované | 16 adres |
| Skupinové adresy B1–B16 | hex | definované | 16 adres |
| Společné adresy | – | – | pro rychlou aktivaci více prvků |

## 6.5 Časování a SLA

| Parametr | Hodnota | Jednotka | Poznámka |
|----------|---------|----------|----------|
| Zahájení aktivačního příkazu | ≤ 3 | s | od přijetí zprávy |
| Zahájení akustické aktivace | ≤ 10 | s | od přijetí zprávy |
| Synchronizace RTC | ±3 | s/den | vyžadováno |
| Formát časové značky | UINT64 | s | Unix time |
| Timeout duplicit | 180 (30–300) | s | nastavitelný |
| Heartbeat parseru | 2 | s | pro watchdog |

## 6.6 Kontrolní mechanismy

- **CRC**: CRC-16-CCITT, polynom 0x1021, init=0x0000, výstup 4 ASCII hex číslice.  
- **Duplicitní klíč**: kombinace `command+params+operatorId+timestamp`.  
- **Ztráty**: retry + logování MER.  
- **Ochrana proti CRC failu**: zpráva odmítnuta, logována.  

