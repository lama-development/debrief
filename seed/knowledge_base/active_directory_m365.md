# Active Directory e Microsoft 365

## Panoramica

- Dominio AD: **ad_net.com**
- Dominio posta: **adcompound.com**
- Domain Controller: **srv-dc2**
- Posta: Exchange Online (Microsoft 365)
- Licenze M365: ~60-80 utenti (uffici, lab, responsabili produzione)
- Account AD totali: 100+ (inclusi operatori produzione per accesso TSPlus)
- MFA obbligatoria per tutti gli utenti M365 tramite Microsoft Authenticator su smartphone aziendale
- GPO gestite da `{{IT_EXTERNAL}}`

## Problemi frequenti

### Utente bloccato / non riesce ad accedere al PC

1. Verificare in AD Users and Computers se l'account è bloccato (checkbox "Account is locked out")
2. Se bloccato: sbloccare e verificare la causa (tentativi falliti, script con credenziali vecchie, sessione TSPlus con password scaduta)
3. Se la password è scaduta: resettarla e far impostare una nuova all'utente al primo accesso
4. Attenzione: se un operatore di produzione usa un **account condiviso** su un totem, il blocco impatta tutti gli utenti di quel totem

### Problemi MFA / Microsoft Authenticator

1. Se l'utente ha cambiato smartphone: serve riconfigurare Authenticator
   - Accedere al portale admin M365 > utente > Metodi di autenticazione > rimuovere il vecchio dispositivo
   - L'utente deve riconfigurare Authenticator dal nuovo smartphone
2. Se Authenticator non genera codici: verificare che data/ora dello smartphone siano corretti (sincronizzazione automatica)
3. Se l'utente è completamente bloccato: impostare un bypass temporaneo MFA dall'admin portal (max 24h)

### Posta non funziona (Exchange Online)

1. Verificare se il problema è solo Outlook desktop o anche la webmail (outlook.office.com)
   - Solo Outlook: problema client (profilo, aggiornamento Windows). Vedi runbook postazioni.
   - Anche webmail: problema Exchange Online o account
2. Controllare lo stato del servizio M365: admin.microsoft.com > Integrità del servizio
3. Verificare che la casella non sia piena (M365 Standard ha 50GB per utente)
4. Se le email escono ma non arrivano: controllare il dominio adcompound.com su admin.microsoft.com > Domini

### Creazione nuovo utente

1. Creare l'account in Active Directory (ad_net.com)
2. Assegnare la licenza M365 se necessario (admin.microsoft.com)
3. Configurare MFA (invitare l'utente a registrare Authenticator al primo accesso)
4. Aggiungere ai gruppi AD necessari (reparto, accesso cartelle su srv-file1, gruppo VPN se necessario)
5. Configurare la postazione (vedi runbook postazioni)
6. Se l'utente deve usare TSPlus: creare il profilo su srv-tsplus

### Sincronizzazione AD - M365

L'identità è gestita su AD on-premise e sincronizzata con Microsoft 365. Se un utente cambia password in AD, la modifica si riflette su M365 dopo la sincronizzazione. Se ci sono problemi di sincronizzazione, contattare `{{IT_EXTERNAL}}`.

## Escalation

- Problemi di GPO, sincronizzazione AD-M365, configurazione srv-dc2 → `{{IT_EXTERNAL}}`
- Problemi di licenze M365 o servizi Exchange Online → `{{IT_EXTERNAL}}` (portale admin) o Microsoft support
- Reset MFA di emergenza → `{{IT_EXTERNAL}}` (accesso admin portal)
