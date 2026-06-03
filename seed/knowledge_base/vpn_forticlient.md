# VPN FortiClient e accessi remoti

## Configurazione

- Soluzione VPN: **FortiClient VPN** con tunnel **IPSec**
- Firewall: **FortiGate** (gestito da `{{IT_EXTERNAL}}`)
- Autenticazione: email aziendale (@adcompound.com) + credenziali Active Directory
- Gruppi VPN con passkey dedicate: ADC (generale), HR, e altri profili
- Utenti tipici: commerciali in trasferta, dipendenti in smart working
- Fornitori esterni: accessi VPN nominativi dedicati per supporto ricorrente

## Problemi frequenti

### FortiClient non si connette (timeout)

1. Verificare che l'utente abbia connettività Internet (può navigare?)
2. Controllare che le credenziali siano corrette (dominio ad_net.com)
3. Verificare che la passkey del gruppo sia quella giusta (ADC, HR, ecc.)
4. Se l'utente ha cambiato password AD di recente: usare la nuova password
5. Se nessun utente si connette: il problema è lato FortiGate
   - Verificare lo stato del servizio VPN sul FortiGate (se si ha accesso)
   - Contattare `{{IT_EXTERNAL}}`

### Connessione VPN lenta

1. Far testare la velocità della connessione domestica dell'utente (speedtest.net)
2. Se la banda è sufficiente: il problema potrebbe essere sul FortiGate
   - Verificare se il DPI (Deep Packet Inspection) è attivo sul tunnel VPN (aggiunge latenza)
   - Controllare quante sessioni VPN sono attive contemporaneamente
3. Consiglio per l'utente: usare la connessione cablata invece del WiFi di casa se possibile

### Certificato VPN scaduto

Sintomo: tutti gli utenti ricevono "Certificate validation failed" contemporaneamente.

1. Verificare la scadenza del certificato sul FortiGate
2. Se scaduto: il rinnovo va fatto da `{{IT_EXTERNAL}}` sul FortiGate
3. Contattare `{{IT_EXTERNAL}}` immediatamente (impatto su tutti gli utenti remoti)
4. Tenere traccia della scadenza nel calendario IT condiviso

### Accesso fornitore esterno non funziona

I fornitori (`{{IT_EXTERNAL}}`, `{{PLC_VENDOR}}`, ecc.) hanno accessi VPN nominativi.

1. Verificare che le credenziali del fornitore siano ancora valide
2. Se l'accesso è stato disattivato per inattività: riattivarlo dal FortiGate (o chiedere a `{{IT_EXTERNAL}}`)
3. Se il fornitore deve accedere a una nuova risorsa: verificare le regole firewall del suo profilo VPN

## Prevenzione

- Mantenere un registro di tutti gli accessi VPN (interni e fornitori) con date di scadenza
- Reminder nel calendario per il rinnovo del certificato VPN (90, 30, 7 giorni prima)
- Revisione trimestrale degli accessi fornitori: disattivare quelli non più necessari

## Escalation

- Configurazione FortiGate, certificati, regole VPN → `{{IT_EXTERNAL}}`
- Problemi di credenziali AD → `{{IT_INTERNAL}}` (reset password, sblocco account)
