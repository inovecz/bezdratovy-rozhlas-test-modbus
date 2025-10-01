# 3. Specifikace JSON a komunikace parser → Laravel Artisan

Parser komunikuje s backendem přes Artisan příkaz v Laravelu. Všechny zprávy jsou převedeny do jednotného JSON formátu.

## 3.1 Formát JSON zprávy

Každá zpráva má tuto strukturu:

- **networkId**: číslo (ID sítě / krajský subsystém)  
- **vycId**: číslo (ID vyrozumívacího centra)  
- **kppsAddress**: string/hex (adresa KPPS, 0–65534)  
- **operatorId**: číslo (pokud dostupné)  
- **type**: řetězec (ACTIVATION | STATUS | FAULT | TRIGGER | QUERY | RESPONSE)  
- **command**: řetězec (např. SIREN_SIGNAL | GONG | VERBAL_INFO | BATTERY_LOW …)  
- **params**: objekt s parametry specifickými pro command  
- **priority**: řetězec (P1 | P2 | P3)  
- **timestamp**: číslo (UNIX time, sekundy, UINT64)  
- **rawMessage**: řetězec (HEX nebo ASCII rámec)  

### Příklad JSON
```
{
  "networkId": 5,
  "vycId": 12,
  "kppsAddress": "0x1A2B",
  "operatorId": 42,
  "type": "ACTIVATION",
  "command": "SIREN_SIGNAL",
  "params": { "signalType": 1, "duration": 180 },
  "priority": "P2",
  "timestamp": 1696157700,
  "rawMessage": "SIREN 1 180"
}
```

## 3.2 Varianty volání Artisan

- **Single mode**:  
  Každá zpráva = jedno volání Artisan.  
  ```
  php artisan jsvv:processMessage '{"networkId":5,...}'
  ```

- **Batch mode**:  
  Více zpráv předaných v jedné dávce. JSON obsahuje pole `items[]`.  
  ```
  {
    "items": [
      { "networkId": 5, "command": "SIREN_SIGNAL", ... },
      { "networkId": 5, "command": "STOP", ... }
    ]
  }
  ```

- **Retry pravidla**:  
  Pokud Artisan vrátí nenulový exit code, zpráva je zařazena do retry fronty s exponenciálním backoffem. Počet pokusů a intervaly nastavitelné v parseru.  

## 3.3 Výstup Artisan (STDOUT/exit code)

- **OK**:  
  „OK Message processed: {command} at {ISO8601}“, exit code 0.  

- **ERROR**:  
  „ERROR {reason}“, exit code 1.  

## 3.4 Bezpečnost a robustnost

- **Maximální velikost payloadu**: doporučeno max. 1 MB na jednu zprávu / dávku.  
- **Validace JSON**: všechny příchozí zprávy validovat proti JSON schématu.  
- **Idempotence**: zprávy deduplikovat podle `dedupKey` (kombinace: networkId, vycId, kppsAddress, command, params, timestamp).  
- **Timeouty**: parser musí čekat na odpověď Artisanu max. 5 s, jinak retry.  

