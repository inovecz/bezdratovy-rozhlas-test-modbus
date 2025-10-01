# 4. Návrh backendu v Laravelu

Backend v Laravelu přijímá zprávy z parseru (Artisan), provádí validaci, ukládá je do databáze, emituje interní eventy a spouští navazující workflow (výstrahy, notifikace, řízení Modbus kanálu). Návrh klade důraz na idempotenci, nízkou latenci a auditovatelnost.

## 4.1 Datový model a migrace

### Tabulka: `jsvv_messages`
Slouží jako centrální evidenční tabulka všech přijatých zpráv.

- `id` (bigIncrements) – primární klíč.  
- `networkId` (unsignedSmallInteger) – ID sítě.  
- `vycId` (unsignedSmallInteger) – ID VyC.  
- `kppsAddress` (string, 32) – adresa KPPS (hex/dec).  
- `operatorId` (unsignedInteger, nullable) – ID operátora.  
- `type` (string, 32) – ACTIVATION | STATUS | FAULT | TRIGGER | QUERY | RESPONSE.  
- `command` (string, 64) – viz slovník příkazů.  
- `params` (json) – parametry příkazu.  
- `priority` (string, 4) – P1 | P2 | P3.  
- `payloadTimestamp` (unsignedBigInteger) – Unix time (UINT64).  
- `receivedAt` (timestampTz) – čas přijetí z Artisanu.  
- `rawHex` (longText) – původní rámec (HEX/ASCII).  
- `status` (string, 24) – NEW | VALIDATED | QUEUED | PROCESSED | DUPLICATE | REJECTED | FAILED.  
- `dedupKey` (string, 128) – hash pro idempotenci (unikátní index).  
- `artisanExit` (smallInteger, nullable) – návratový kód z Artisanu (pokud je volán synchronně).  
- `meta` (json, nullable) – doplňková metadata.  
- `created_at` / `updated_at` (timestampsTz).  

Indexy:
- `idx_jsvv_messages_lookup` na (`networkId`, `vycId`, `kppsAddress`, `payloadTimestamp`, `priority`).  
- `uniq_jsvv_messages_dedupKey` – unique na `dedupKey`.  
- `idx_jsvv_messages_type_command` na (`type`, `command`).

### Tabulka: `jsvv_events`
Auditní stopa navazujících akcí a stavových změn.

- `id` (bigIncrements).  
- `message_id` (foreignId → `jsvv_messages.id`).  
- `event` (string, 64) – např. JsvvMessageReceived, ValidationFailed, DispatchedToQueue, ModbusPaused, ModbusResumed, NotificationSent, WorkflowCompleted, ErrorRaised, RetryScheduled apod.  
- `data` (json) – payload události.  
- `created_at` (timestampTz).  

Indexy:
- `idx_jsvv_events_message` na (`message_id`).  
- `idx_jsvv_events_event_time` na (`event`, `created_at`).

### Tabulka: `control_channel_commands`
Log a poslední známý stav řídicích příkazů Modbus kanálu.

- `id` (bigIncrements).  
- `command` (string, 32) – pause_modbus | resume_modbus | stop_modbus | status_modbus.  
- `state_before` (string, 24) – IDLE | TRANSMITTING | PAUSED | STOPPED.  
- `state_after` (string, 24).  
- `reason` (string, 128) – např. „P1 STOP přijato“.  
- `message_id` (foreignId nullable) – původní zpráva, která přechod vyvolala.  
- `result` (string, 24) – OK | TIMEOUT | FAILED.  
- `created_at` (timestampTz).

### Příklad migrace (zestručněno)

```php
Schema::create('jsvv_messages', function (Blueprint $t) {
  $t->bigIncrements('id');
  $t->unsignedSmallInteger('networkId');
  $t->unsignedSmallInteger('vycId');
  $t->string('kppsAddress', 32);
  $t->unsignedInteger('operatorId')->nullable();
  $t->string('type', 32);
  $t->string('command', 64);
  $t->json('params');
  $t->string('priority', 4);
  $t->unsignedBigInteger('payloadTimestamp');
  $t->timestampTz('receivedAt');
  $t->longText('rawHex');
  $t->string('status', 24)->default('NEW');
  $t->string('dedupKey', 128);
  $t->smallInteger('artisanExit')->nullable();
  $t->json('meta')->nullable();
  $t->timestampsTz();
  $t->unique('dedupKey', 'uniq_jsvv_messages_dedupKey');
  $t->index(['networkId','vycId','kppsAddress','payloadTimestamp','priority'], 'idx_jsvv_messages_lookup');
  $t->index(['type','command'], 'idx_jsvv_messages_type_command');
});
```

## 4.2 Příjem zpráv z Artisanu (Command Handler)

### Artisan příkaz
`php artisan jsvv:processMessage {payload}`

- Přijme JSON (`single` nebo `batch`).  
- Ověří JSON proti schématu (Laravel Validation / JSON Schema).  
- Vytvoří nebo najde záznam v `jsvv_messages` podle `dedupKey`.  
- Emituje event `JsvvMessageReceived`.  
- U `batch` iteruje nad `items[]` a postupuje stejně pro každou zprávu.

### DedupKey (idempotence)
`dedupKey = sha256(networkId|vycId|kppsAddress|type|command|normalized(params)|timestamp)`

- `normalized(params)` = serializace JSON s deterministickým pořadím klíčů.  
- Pokud už záznam s `dedupKey` existuje → označit jako `DUPLICATE`, zalogovat audit a **neprovádět** znovu workflow (no-op).

## 4.3 Zpracování zpráv (Event → Listeners)

Po uložení a validaci je emitován **`JsvvMessageReceived`** s payloadem celé zprávy. Typické posluchače:

- **`RouteActivationCommands`** – pro `type=ACTIVATION` (P1/P2/P3) rychlá cesta do prioritní queue (`activations-high`).  
- **`HandleStatusAndFaults`** – ukládá stavové/fault zprávy, spouští notifikace a případné servisní workflow.  
- **`ControlChannelCoordinator`** – vyhodnotí, zda má být Modbus kanál **pozastaven/přerušen** (viz kapitola 5).  
- **`AuditTrailWriter`** – zapisuje události do `jsvv_events`.  

### Queues a priority
- `activations-high` – nejvyšší priorita, minimální middleware, krátké timeouts.  
- `default` – běžné úlohy.  
- `low` – reporty a housekeeping.

**Cíl SLA:** Zajištění zpracování aktivační zprávy (P2) v řádu **< 500 ms** v backendu, aby celková doba od přijetí po zahájení akustiky nepřesáhla 3 s / 10 s.

## 4.4 Validace schématu

Příklad validačních pravidel (Laravel validation):
- `networkId` – required|integer|min:0|max:255  
- `vycId` – required|integer|min:0|max:255  
- `kppsAddress` – required|string|max:32  
- `operatorId` – nullable|integer|min:0|max:65535  
- `type` – required|in:ACTIVATION,STATUS,FAULT,TRIGGER,QUERY,RESPONSE  
- `command` – required|string|max:64  
- `params` – required|array  
- `priority` – required|in:P1,P2,P3  
- `timestamp` – required|integer|min:0  
- `rawMessage` – required|string

Chybná validace → stav `REJECTED`, audit `ValidationFailed` s chybami.

## 4.5 Idempotence a TTL pro duplicitní cache

- Primární idempotence: `dedupKey` v DB (unique index).  
- Sekundární cache (Redis): `dedup:{dedupKey} = 1` s TTL **10 minut** – zabrání závodům ve více instancích.  
- Chování při duplicitě: zapsat `jsvv_events(event=DUPLICATE_DETECTED)`, nezpracovávat už podruhé.

## 4.6 Zrychlená cesta pro aktivace (fast path)

Pro `type=ACTIVATION`:
1. Minimální validace → **save** (status=VALIDATED).  
2. Emit `JsvvMessageReceived`.  
3. Listener `RouteActivationCommands` bezodkladně pushne job do `activations-high`.  
4. Job provede pouze nezbytné kroky (např. přímý zápis příznaku pro Modbus koordinátor, notifikaci).  
5. Ostatní doprovodné akce (reporting, sekundární notifikace) provádět **asynchronně** v `default/low`.

## 4.7 Chybové stavy a stavový automat

Stavová pole v `jsvv_messages.status`:  
- `NEW` → `VALIDATED` → `QUEUED` → `PROCESSED`  
- Odbočky: `REJECTED` (validace/parse fail), `DUPLICATE` (idempotence), `FAILED` (výjimka/timeout).

Přechody:
- `NEW` → `REJECTED` (neprošel schema).  
- `VALIDATED` → `FAILED` (výjimka posluchače) → retry (exponenciální, max 5x).  
- `QUEUED` → `PROCESSED` (úspěch) | `FAILED`.  

Každý přechod se loguje do `jsvv_events` s důvodem a metadaty (časy, identifikátory).

## 4.8 Monitoring a metriky

- Latence `parser → artisan → stored` (ms).  
- Čas validace (ms), čas emise eventu (ms), queue wait time (ms).  
- Počty zpráv podle `type/command/priority`.  
- Chybovost validace, podíl duplicit.  
- SLA watch: procento aktivací zpracovaných < 3 s, akustika < 10 s (z kombinovaných dat).

Prometheus/Laravel Telescope/Health checks; alarm při degradaci SLA.

## 4.9 Bezpečnost a audit

- Podpis Artisanu (ověření, že volající je parser – API key/Unix socket).  
- Rate limiting na příkaz (ochrana před bouří).  
- Úplná auditní stopa v `jsvv_events` – zejména pro zásahy do Modbus kanálu.  
- Logování originálního `rawHex` pro forenzní analýzu.

## 4.10 Příklady zpracování (happy path a edge cases)

### Aktivace sirény (P2)
- Přijato → validace OK → uloženo → emit event → fast path queue → koordinátor Modbus označí potřebu preempce → workflow pokračuje; status = `PROCESSED`.

### STOP (P1)
- Přijato → validace OK → uloženo → emit event → koordinátor pošle `stop_modbus` přes Control Channel → čeká potvrzení → pokud TIMEOUT, eskalace (fallback viz kap. 5).

### Duplicitní aktivace
- Přijato → `dedupKey` koliduje → záznam s `DUPLICATE`, audit událost, bez dalšího workflow.

### Invalid schema
- Přijato → validace KO → záznam `REJECTED` + seznam chyb v `jsvv_events`.

