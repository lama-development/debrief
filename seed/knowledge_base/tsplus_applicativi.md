# TSPlus e applicativi aziendali

## Panoramica

**srv-tsplus** ospita TSPlus e gli applicativi principali:

- **Genius**: gestionale aziendale proprietario, usato da uffici e R&D (~30 utenti)
- **Genius Logistics**: gestione magazzino, usato da magazzinieri e carrellisti via tablet sulla rete ADC-Warehouse (Remote Desktop)
- **Prometeo Rifiuti**: gestione rifiuti

Genius e Genius Logistics sono applicativi proprietari sviluppati e mantenuti da `{{IT_DEV}}`. Per qualsiasi problema applicativo (bug, errori, aggiornamenti, migrazioni) il riferimento sono loro, NON `{{IT_EXTERNAL}}`.

Il database di Genius è ospitato su **srv-db** (server virtuale gestito da `{{IT_EXTERNAL}}` come infrastruttura, ma il contenuto/struttura del database è responsabilità di `{{IT_DEV}}`).

In corso la migrazione da Genius a **TS Enterprise** (versione web).

## Problemi frequenti

### TSPlus non risponde / sessioni bloccate

1. Verificare che srv-tsplus sia raggiungibile: `ping srv-tsplus`
2. Se non risponde: controllare lo stato della VM (`{{IT_EXTERNAL}}` gestisce la virtualizzazione)
3. Se risponde ma le sessioni non partono: accedere al server via RDP con le credenziali admin e controllare:
   - Numero di sessioni attive (Task Manager > Users). TSPlus ha un limite di sessioni concorrenti.
   - Memoria e CPU (se al 100%, una sessione potrebbe essere in loop)
   - Servizio TSPlus: verificare che sia in esecuzione (services.msc > TSPlus)
4. Come intervento rapido: disconnettere le sessioni disconnesse (non attive) per liberare risorse

### Genius non si avvia o dà errore di connessione al database

1. Verificare che srv-db sia raggiungibile: `ping srv-db`
2. Se srv-db non risponde: contattare `{{IT_EXTERNAL}}` (la VM è gestita da loro)
3. Se srv-db risponde ma Genius dà errore di connessione:
   - Controllare che il servizio database sia in esecuzione su srv-db
   - Verificare lo spazio disco su srv-db (database pieno → `{{IT_EXTERNAL}}` per lo spazio, `{{IT_DEV}}` per il database)
   - Controllare i log di Genius per l'errore specifico → `{{IT_DEV}}`
4. Se il problema è un bug applicativo o un errore dopo un aggiornamento → `{{IT_DEV}}`
5. Se il problema riguarda un singolo utente: ricreare il profilo TSPlus dell'utente

### Genius Logistics non funziona sui tablet (ADC-Warehouse)

1. Verificare che il tablet sia connesso alla rete ADC-Warehouse (NON ADC-Office o ADC-Mobile)
2. Testare la connessione a srv-tsplus dal tablet
3. Se la rete ADC-Warehouse funziona ma la sessione RDP non parte: controllare le sessioni su srv-tsplus (potrebbe aver raggiunto il limite)
4. Se la rete ADC-Warehouse è giù: controllare lo switch dedicato e la VLAN (vedi runbook rete)

### Lentezza generalizzata su tutti gli applicativi TSPlus

- Controllare le risorse di srv-tsplus (CPU, RAM, disco)
- Verificare quante sessioni sono attive vs limite
- Controllare se c'è un processo anomalo (un report pesante lanciato da un utente può impattare tutti)
- Se srv-tsplus è una VM: verificare con `{{IT_EXTERNAL}}` che le risorse allocate siano sufficienti

## Aggiornamenti

Gli aggiornamenti di Genius e Genius Logistics vanno coordinati con `{{IT_DEV}}`. Gli aggiornamenti di TSPlus come piattaforma vanno invece coordinati con `{{IT_EXTERNAL}}`. Prima di ogni aggiornamento:

- Backup del database su srv-db
- Backup della configurazione TSPlus
- Comunicazione agli utenti della finestra di manutenzione
- Test post-aggiornamento con almeno un utente per applicativo

## Escalation

- Problemi applicativi Genius/Genius Logistics (bug, errori, aggiornamenti, database) → `{{IT_DEV}}`
- Problemi di VM/risorse srv-tsplus (CPU, RAM, disco della VM) → `{{IT_EXTERNAL}}`
- Problemi di rete ADC-Warehouse → `{{IT_EXTERNAL}}` (switch/VLAN) oppure verificare in autonomia gli AP
