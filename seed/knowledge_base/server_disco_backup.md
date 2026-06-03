# Gestione server, spazio disco e backup

## Infrastruttura server

| Server     | Ruolo                                       | Note                      |
| ---------- | ------------------------------------------- | ------------------------- |
| srv-file1  | File server, cartelle condivise             | Shadow copies ogni ~30min |
| srv-tsplus | TSPlus (Genius, Genius Logistics, Prometeo) | ~30 sessioni concorrenti  |
| srv-dc2    | Domain Controller Active Directory          | DNS, DHCP, autenticazione |
| srv-apps3  | Applicativi vari                            |                           |
| srv-db     | Database (Genius e altri)                   | Database critico          |

Virtualizzazione e manutenzione server gestite da `{{IT_EXTERNAL}}`.

## Spazio disco

### Sintomi di disco pieno

- Servizi che smettono di funzionare senza errore evidente
- RDP che non accetta login (il profilo temporaneo non si crea)
- Database che rifiuta scritture ("could not extend file", "disk full")
- Backup che falliscono silenziosamente

### Procedura di emergenza

1. Se il server non è raggiungibile via RDP: accesso fisico in sala server (o chiedere a `{{IT_EXTERNAL}}` per le VM)
2. Identificare cosa occupa spazio:
   - Windows: `dir /s /o-s C:\` oppure WinDirStat
   - Linux: `du -sh /* | sort -rh`
3. Candidati sicuri da eliminare:
   - Log vecchi (C:\Windows\System32\winevt\Logs, /var/log)
   - File temporanei (C:\Windows\Temp, %TEMP%)
   - Shadow copies eccessive
4. **NON cancellare file di database o di sistema senza certezza**
5. Riavviare i servizi bloccati dopo aver liberato spazio

### Server specifici

- **srv-file1**: le shadow copies occupano spazio sullo stesso volume. Se il disco si riempie, le shadow copies più vecchie vengono eliminate automaticamente ma potrebbe non bastare.
- **srv-db**: il database di Genius cresce nel tempo. Se lo spazio si esaurisce, Genius smette di funzionare per tutti. Verificare anche i log del database. Per problemi sul database contattare `{{IT_DEV}}`, per spazio disco della VM contattare `{{IT_EXTERNAL}}`.
- **srv-tsplus**: le sessioni utente creano profili temporanei. Con ~30 utenti attivi, i profili possono accumularsi.

## Backup

### Shadow copies (srv-file1)

- Frequenza: circa ogni 30 minuti
- Storico: alcuni giorni
- Accessibili dagli utenti: tasto destro sulla cartella > "Versioni precedenti"
- Se un utente cancella un file per errore, recuperarlo dalle versioni precedenti PRIMA che vengano sovrascritte

### Veeam (gestito da `{{IT_EXTERNAL}}`)

- Backup avanzato di tutti i server virtualizzati
- Per ripristini da Veeam: contattare `{{IT_EXTERNAL}}` con nome del server, data/ora del ripristino desiderato e cosa deve essere ripristinato

### Verifica backup

Controllare periodicamente (almeno settimanale):

- Le shadow copies su srv-file1 sono attive? (vssadmin list shadows)
- L'ultimo backup Veeam è andato a buon fine? (chiedere report a `{{IT_EXTERNAL}}`)

## Escalation

- Problemi su VM, risorse server, Veeam → `{{IT_EXTERNAL}}`
- Disco pieno su srv-db con impatto su Genius → `{{IT_DEV}}` (database) + `{{IT_EXTERNAL}}` (spazio VM)
