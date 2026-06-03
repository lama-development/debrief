# PLC e automazione industriale

## Regola fondamentale

**`{{IT_INTERNAL}}` NON interviene direttamente su PLC, linee produttive e sistemi di automazione.** La gestione è affidata esclusivamente a `{{PLC_VENDOR}}`. Il ruolo dell'IT in caso di incidente in produzione è:

1. Raccogliere le informazioni da `{{PRODUCTION}}`
2. Verificare che il problema non sia di rete IT (cablaggio, switch, VLAN)
3. Contattare `{{PLC_VENDOR}}`
4. Facilitare l'accesso remoto (VPN fornitore) o fisico

## Infrastruttura di automazione

- PLC: prevalentemente **Siemens**
- Protocollo: **Profinet** (Industria 4.0)
- Supervisione: **Movicon Next** per la gestione dei macchinari industriali
- Aree produttive: CMP (carico materie prime), macinazione, agglomerazione, insacco, estrusione, silos, trituratore (TR2-5), tramoggia, granulazione
- I macchinari NON usano la rete WiFi aziendale, comunicano su segmenti di rete dedicati

## Come raccogliere informazioni utili per `{{PLC_VENDOR}}`

Quando un operatore o un capoturno segnala un problema su un macchinario:

1. **Quale linea/area?** (es. "estrusione", "insacco linea 3", "TR2")
2. **Codice di allarme sul pannello** (es. "Err 47 - Comm Fault"). Fotografare il display.
3. **La linea è ferma o funziona con limitazioni?**
4. **Da quando?** (ha coinciso con un evento? blackout, temporale, intervento di manutenzione?)
5. **Hanno già provato qualcosa?** (riavvio, reset allarme)

Queste informazioni accelerano notevolmente l'intervento di `{{PLC_VENDOR}}`.

## Verifiche che l'IT PUò fare

Prima di chiamare `{{PLC_VENDOR}}`, escludere i problemi di rete IT:

- Il macchinario è raggiungibile in rete? (ping dell'indirizzo IP del PLC, se noto)
- Lo switch nella cabina elettrica della zona è acceso e funzionante?
- L'UPS della cabina è attivo?
- C'è stato un blackout o un intervento elettrico recente?

Se il problema è di rete IT (switch, cablaggio, VLAN), risolverlo in autonomia o con `{{IT_EXTERNAL}}`. Se il problema è sul PLC/macchinario, passare a `{{PLC_VENDOR}}`.

## Movicon Next (SCADA)

Movicon Next è il software di supervisione installato su postazioni dedicate in produzione. Se Movicon non visualizza i dati:

- Verificare che la postazione sia accesa e connessa alla rete
- Verificare che il servizio Movicon sia in esecuzione
- Se Movicon funziona ma i dati sono fermi: il problema è nella comunicazione con il PLC → `{{PLC_VENDOR}}`

## Escalation

- Qualsiasi intervento su PLC, programma, sensori, parametri → `{{PLC_VENDOR}}`
- Accesso remoto di `{{PLC_VENDOR}}` non funziona → verificare la VPN nominativa (vedi runbook VPN)
- Problemi di rete/switch nelle cabine elettriche → `{{IT_EXTERNAL}}` o `{{IT_INTERNAL}}`
