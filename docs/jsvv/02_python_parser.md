# 2. Návrh Python parseru JSVV

Parser zajišťuje komunikaci mezi KPPS (přes RS-232) a backendem (Laravel). Jeho úkolem je přijímat, dekódovat a validovat zprávy, převádět je na jednotný JSON a předávat je backendu.

## 2.1 Architektura modulů parseru

- **RS-232 přijímač**  
  - Parametry: 9600 b/s, 8 datových bitů, žádná parita, 1 stop bit, žádné řízení toku.  
  - Propojení: null-modem, DE9, RXD=2, TXD=3, GND=5.  
  - Funkce: čte příchozí rámce ukončené LF (0x0A).

- **Parser zpráv**  
  - Rozdělí zprávu podle mezer na MID a datové bloky.  
  - Validuje formát a typ zprávy.  
  - Ověří, zda odpovídá specifikaci (počet a typ parametrů).

- **Validátor CRC**  
  - Pokud zpráva vyžaduje CRC, vypočítá CRC-16-CCITT a ověří.  
  - CRC nesedí → zpráva odmítnuta, zalogována jako „CRC ERROR“.

- **Mapper na JSON**  
  - Převede zprávu do jednotné JSON struktury (viz bod 3).  
  - Doplňuje identifikátory (síť, VyC) z konfigurace, pokud nejsou ve zprávě.  

- **Prioritní fronta**  
  - Vkládá zprávy podle priority (P1 > P2 > P3).  
  - Při přijetí vyšší priority přeruší zpracování nižší.  
  - Použije datovou strukturu typu `PriorityQueue`.

- **Komunikace s Artisan**  
  - Volá Artisan příkaz s JSON payloadem.  
  - Zachytává exit code a výstup.  
  - Retry mechanizmus s exponenciálním backoffem.  

## 2.2 Priority zpráv a logika preempce

- **P1 (STOP, RESET, stavové dotazy):** okamžité zpracování, přednost před vším ostatním.  
- **P2 (sirény, verbální informace):** zpracování do 3 s, akustická aktivace do 10 s. Přerušuje P3.  
- **P3 (hlášení, externí audio, TEST):** nejnižší priorita, může být přerušena P2 nebo P1.  

### SLA požadavky
- STOP → zařízení do klidu do 15 s.  
- RESET → reset do 60 s.  
- Aktivace sirény → zahájena do 3 s, akustika do 10 s.  

## 2.3 Logování parseru

Každá zpráva musí být zalogována s:  
- časem příjmu (lokální + timestamp z payloadu),  
- RAW (HEX) zprávou,  
- dekódovanými poli,  
- výsledkem CRC validace,  
- vyhodnocenou prioritou,  
- stavem zpracování: RECEIVED, DECODED, DUPLICATE, REJECTED, FORWARDED, FAILED, DONE.  

### Příklad logu

```
2025-10-01T08:50:12.345Z [RECEIVED] RAW: "STOP 5 1696157700"
2025-10-01T08:50:12.346Z [DECODED] MID=STOP, operatorId=5, timestamp=1696157700 -> Priority=P1
2025-10-01T08:50:12.347Z [FORWARDED] Artisan call jsvv:processMessage (single); status=0
2025-10-01T08:50:12.348Z [DONE] Message STOP handled successfully.
```

```
2025-10-01T09:00:00.100Z [RECEIVED] RAW: "READ_CFG"
2025-10-01T09:00:00.101Z [DECODED] MID=READ_CFG (status query) -> Priority=P1
2025-10-01T09:00:00.102Z [FORWARDED] Artisan call jsvv:processMessage (single); status=0
2025-10-01T09:00:00.150Z [RECEIVED] RAW: "READ_CFG 1 30 180 0000000000000001 3 10 2 1 12"
2025-10-01T09:00:00.151Z [DECODED] MID=READ_CFG (response), params: type=1 (ES), interval=30, blockTime=180 ...
2025-10-01T09:00:00.152Z [FORWARDED] Artisan call jsvv:processMessage (single); status=0
```

