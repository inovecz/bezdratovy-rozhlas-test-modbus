# 5. Integrace s Modbus a pravidla přerušování

Tato kapitola definuje propojení backendu (Laravel) s Modbus kanálem a kooperaci s Python parserem tak, aby byla zajištěna **preempce** vysílání podle priorit JSVV (P1 > P2 > P3) a dodrženy SLA: **zahájení do 3 s** a **akustická aktivace do 10 s** od přijetí příkazu.

## 5.1 Control Channel (Backend ↔ Parser)

Obousměrné řídicí rozhraní mezi backendem a parserem (IPC přes Unix socket / ZeroMQ / gRPC-lite). Logicky jde o „řídicí vrstvu“, která nevede samotná data JSVV, ale **koordinační příkazy** pro Modbus kanál na straně parseru.

### Příkazy
- `pause_modbus` – okamžitě pozastaví běžící Modbus operace (dotazování, write/coil, read/holding).  
- `resume_modbus` – obnoví dříve pozastavené Modbus operace.  
- `stop_modbus` – **okamžitě** ukončí probíhající přenos (hard stop); přepne kanál do bezpečného stavu.  
- `status_modbus` – požadavek na zaslání aktuálního stavu FSM (viz níže) a rozpracovaných operací.

### Formát zpráv Control Channel
Každá zpráva má JSON payload:
- `id` – UUID požadavku.  
- `command` – viz výše.  
- `reason` – lidsky čitelný důvod (např. „P1 STOP“, „P2 activation preemption“).  
- `sourceMessageId` – ID záznamu v `jsvv_messages` (je-li k dispozici).  
- `deadlineMs` – měkký deadline pro provedení (např. 500 ms).

### Odpověď
- `ok` (bool)  
- `state` – aktuální stav FSM (IDLE | TRANSMITTING | PAUSED | STOPPED)  
- `details` – doplňkové info (aktuální operace, poslední chyba)  
- `ts` – čas odpovědi (ISO8601)  

Všechny příkazy a odpovědi se auditují do tabulky `control_channel_commands`.

## 5.2 Stavový model Modbus kanálu (FSM)

```
IDLE ──(start Tx)──▶ TRANSMITTING
  ▲                   │  │
  │                   │  ├─(pause_modbus)──▶ PAUSED
  │                   │  └─(stop_modbus)───▶ STOPPED
  │                   │
  └──(resume)◀────────┘
PAUSED ──(resume_modbus)──▶ TRANSMITTING
STOPPED ──(reset/init)──▶ IDLE
```

- **IDLE** – kanál neprovádí žádné přenosy.  
- **TRANSMITTING** – probíhá aktivní komunikace (např. periodické čtení registrů, zápis do cílových zařízení).  
- **PAUSED** – dočasně pozastaveno; lze bezpečně obnovit.  
- **STOPPED** – tvrdě zastaveno; pro návrat je potřeba reinitializace (znovu otevřít port, rehandshake).

### Přechody vyvolané prioritami JSVV
- **P1 (STOP/RESET, kritické stavy)**: backend ihned odešle `stop_modbus` → parser musí **do 200 ms** potvrdit přechod do `STOPPED`.  
- **P2 (aktivační příkazy sirén/verbálů)**: backend odešle `pause_modbus` → parser musí **do 200 ms** přepnout do `PAUSED`; po dokončení klíčové akce backendem (např. zápis příkazu na další rozhraní) odešle `resume_modbus`.  
- **P3**: bez zásahu, pouze pokud nebrání SLA vyšších priorit; může být pauzováno, pokud si to vyžádá režie P2/P1.

## 5.3 Prioritizace a preempce

- **P1 má absolutní přednost**: okamžité `stop_modbus`; běžící P2/P3 úlohy se ukončí (na Modbus i jinde).  
- **P2 přerušuje P3**: při příchodu P2 backend *nejprve* pozastaví Modbus (`pause_modbus`), aby uvolnil kanál i CPU pro rychlou reakci, a teprve poté pokračuje v aktivaci.  
- **P3 je přerušitelná**: může být pozastavena libovolně často, nemá nárok blokovat P2/P1.  

### Časování a SLA
- Backend + parser společně musejí zajistit, aby pro P2 platilo: **zahájení ≤ 3 s**, **akustika ≤ 10 s** od přijetí zprávy.  
- V praxi: Control Channel reakce (pause/stop) do 200 ms, dispatch aktivace do prioritní queue (`activations-high`) do 50 ms, Modbus pauza okamžitá.  

## 5.4 Implementační detaily na straně parseru (Modbus worker)

- Samostatný **Modbus worker** (vlákno/proces) obsluhující čtení/zápis.  
- Worker respektuje **FSM** a **Control Channel** signály (non-blocking).  
- Bezpečné body přerušení: mezi PDU transakcemi (TX/RX), mezitím maximální wait 50–100 ms.  
- Hard-stop: pokud přijde `stop_modbus` uprostřed transakce → zrušit timeoutem, zavřít port, přejít do `STOPPED`.  
- Po `resume_modbus` obnovit periodické dotazy a zápisy v původném pořadí.

## 5.5 Chování backendu při preempci

- Listener `ControlChannelCoordinator` hodnotí `type/priority` přijatého `jsvv_message`:  
  - P1 → `stop_modbus(reason="P1 " + command)`.  
  - P2 → `pause_modbus(reason="P2 activation")`, po potvrzení `PAUSED` → pokračovat v aktivaci → `resume_modbus` po dokončení.  
  - P3 → bez zásahu (pokud koliduje, může být pauzována).

- Všechny tyto kroky se zapisují do `jsvv_events` i `control_channel_commands` (důvod, čas, stav před/po).

## 5.6 Bezpečnostní pojistky a fallbacky

- **Timeout potvrzení**: pokud parser nepotvrdí `stop_modbus`/`pause_modbus` do **500 ms**, backend pošle **opakování**.  
- **Eskalace**: pokud po **3 pokusech** bez potvrzení, backend vyvolá **hardware fallback** (např. **hard-cut relé** přes oddělený out-of-band kanál) a označí výsledek jako `TIMEOUT`.  
- **Watchdog**: parser publikuje heartbeat (např. každých 2 s). Výpadek > 5 s → backend přepne do **degradovaného režimu** (přímá aktivace bez spoléhání na modbus worker, pokud architektura dovoluje).  
- **Obnova po STOPPED**: návrat do `IDLE` pouze explicitním `reset/init` krokem s ověřením portu a linkových parametrů.

## 5.7 Audit a observabilita

- Každý Control Channel příkaz → záznam do `control_channel_commands` s `state_before/state_after/reason/message_id`.  
- Korelace s `jsvv_messages.id` pro kompletní trasování „příčina→následek“.  
- Metriky: počet preempcí, průměrná doba potvrzení pause/stop, % případů vyžadujících fallback, dopad na SLA.

## 5.8 Příklady sekvencí

### P2 aktivace během běžícího P3 (rozhlas)
1. Přijata zpráva `SIREN_SIGNAL` (P2).  
2. Backend: `pause_modbus(reason="P2 activation")` → parser odpoví `PAUSED`.  
3. Backend spustí prioritní workflow pro aktivaci.  
4. Po potvrzení provedení → `resume_modbus`.  
5. Audit: `ModbusPaused` → `ActivationDispatched` → `ModbusResumed`.

### P1 STOP během P2 hlášení
1. Přijato `STOP` (P1).  
2. Backend: `stop_modbus(reason="P1 STOP")` → parser `STOPPED`.  
3. Backend provede ukončovací kroky a nastaví systém do klidu.  
4. Audit: `ModbusStopped` → `SystemIdle`.

## 5.9 Konfigurace a ladění

Doporučené konfigurační položky (Laravel .env / parser config):
- `CONTROL_CHANNEL_ENDPOINT` (unix:///var/run/jsvv.sock)  
- `CONTROL_CHANNEL_TIMEOUT_MS` (500)  
- `CONTROL_CHANNEL_RETRY` (3)  
- `MODBUS_SAFE_BREAKPOINT_MS` (100)  
- `MODBUS_WORKER_HEARTBEAT_MS` (2000)  
- `SLA_ACTIVATION_START_MS` (3000)  
- `SLA_ACOUSTIC_START_MS` (10000)

