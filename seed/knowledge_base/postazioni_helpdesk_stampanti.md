# Postazioni di lavoro e helpdesk

## Panoramica postazioni

| Area                      | Quantita' | Sistema         | Note                                                               |
| ------------------------- | --------- | --------------- | ------------------------------------------------------------------ |
| Uffici                    | ~32       | Windows 11      | Postazioni individuali, dominio AD                                 |
| Laboratorio (individuali) | ~10       | Windows 11      | Postazioni individuali                                             |
| Laboratorio (condivise)   | ~5        | Windows 10/11   | Condivise tra analisti/tecnici                                     |
| Laboratorio (strumenti)   | ~10       | Windows 10/11/7 | Dedicate a strumentazione (METTLER TOLEDO STARe, ecc.)             |
| Produzione (totem)        | ~5        | Windows         | Condivise, account condivisi, distribuite in officina/TR/logistica |

**Postazioni Win 7**: isolate dalla rete aziendale per ragioni di compatibilita' con la strumentazione. NON collegarle alla rete.

Tutte le postazioni in dominio **ad_net.com**. Setup manuale (no Intune, no immagine).

## Setup nuova postazione

1. Installazione Windows 11 (ultima versione)
2. Join al dominio ad_net.com (servono credenziali admin)
3. Installazione Sophos Endpoint (scaricabile da Sophos Central)
4. Installazione Microsoft 365 Apps (Office, Outlook, Teams)
5. Configurazione profilo Outlook (autodiscover su adcompound.com)
6. Configurazione MFA con Microsoft Authenticator sullo smartphone aziendale
7. Installazione stampanti PaperCut (vedi sezione stampanti)
8. Configurazione OneDrive (login con account M365)
9. Se l'utente usa TSPlus: verificare che la sessione RDP funzioni
10. Se postazione laboratorio: installare software specifico con il supporto del fornitore dello strumento

## Problemi frequenti

### PC non fa login / account bloccato

1. Verificare connettivita' di rete (il PC deve raggiungere srv-dc2 per autenticarsi)
2. Se "account bloccato": sbloccare in AD Users and Computers (vedi runbook AD)
3. Se "password scaduta": resettare la password
4. Se "relazione di trust con il dominio fallita": rifare il join al dominio (serve accesso con account locale admin)
5. Su totem di produzione: l'account condiviso potrebbe essere stato bloccato da troppi tentativi di un operatore

### Schermata blu (BSOD) ricorrente

1. Annotare il codice di errore (es. KERNEL_DATA_INPAGE_ERROR, IRQL_NOT_LESS_OR_EQUAL)
2. KERNEL_DATA_INPAGE_ERROR: quasi sempre disco difettoso. Controllare lo stato SMART del disco.
3. Fare backup immediato dei dati dell'utente
4. Se il disco e' guasto: sostituire con SSD + reinstallazione

### Outlook non sincronizza

1. La webmail funziona? (outlook.office.com). Se si', il problema e' solo il client
2. Provare a ricreare il profilo Outlook (Pannello di controllo > Mail > Mostra profili)
3. Se il problema e' su piu' postazioni contemporaneamente dopo un Windows Update: cercare il KB problematico
4. Verificare che il PC abbia l'ultimo aggiornamento di Microsoft 365 Apps

### Software strumentazione laboratorio non funziona

- NON aggiornare Windows o driver su postazioni dedicate alla strumentazione senza coordinarsi con il fornitore dello strumento
- Le postazioni Windows 7 sono isolate: se qualcuno le ha collegate alla rete per errore, scollegarle immediatamente
- Per problemi software: contattare il fornitore dello strumento (es. METTLER TOLEDO per STARe)
- Per problemi di rete/postazione: {{IT_INTERNAL}}

## Stampanti e PaperCut

### Panoramica

Sistema di stampa centralizzato **PaperCut** con autenticazione AD e rilascio tramite badge su qualsiasi stampante configurata.

### L'utente non riesce a stampare

1. Verificare che la stampante sia accesa e raggiungibile in rete (ping)
2. Controllare lo stato della coda di stampa sul PC dell'utente
3. Se la coda e' bloccata: svuotarla (services.msc > Print Spooler > Stop/Start)
4. Verificare che PaperCut sia attivo sul PC dell'utente (icona nel system tray)
5. Se PaperCut non si autentica: verificare che l'utente sia nel gruppo AD corretto

### Il badge non rilascia la stampa

1. Verificare che il badge sia associato all'utente in PaperCut
2. Se nuovo badge: associarlo dal pannello admin PaperCut
3. Se il lettore badge non risponde: controllare la connessione USB/rete del lettore alla stampante

### Nuova stampante da configurare

1. Configurare la stampante in rete (IP statico nella VLAN corretta)
2. Aggiungerla in PaperCut come dispositivo
3. Distribuire il driver ai PC (manualmente o via GPO se {{IT_EXTERNAL}} lo imposta)
