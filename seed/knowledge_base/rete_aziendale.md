# Troubleshooting rete aziendale

## Reti e segmentazione

L'azienda utilizza quattro reti principali, su VLAN separate gestite da switch Cisco managed:

- **ADC-Office**: PC aziendali (uffici, laboratorio, totem produzione). Accesso Internet e risorse interne.
- **ADC-Mobile**: smartphone aziendali (usati anche per MFA con Microsoft Authenticator).
- **ADC-Warehouse**: rete industriale SENZA accesso Internet, utilizzata dai tablet per Genius Logistics via Remote Desktop. Isolata per sicurezza.
- **Rete macchinari**: i PLC e i macchinari industriali (Siemens, Profinet) NON usano la rete Wi-Fi. Comunicano su segmenti dedicati gestiti da `{{PLC_VENDOR}}`.

Access point: UniFi, distribuiti tra uffici, laboratorio e produzione.
Firewall: Fortinet FortiGate (gestito da `{{IT_EXTERNAL}}`).
Connettività di backup: linea satellitare EOLO.

## Diagnosi iniziale

1. **Definire l'ambito del problema:**
   - Un solo PC: cavo, porta switch, configurazione locale
   - Un reparto (es. solo laboratorio): switch di cabina, VLAN, AP UniFi della zona
   - Solo ADC-Warehouse: controllare lo switch dedicato e la configurazione VLAN
   - Tutta l'azienda: switch core, FortiGate, o provider (verificare anche EOLO se la linea principale è giù)

2. **Test di base dal PC problematico:**
   - `ping` al gateway della VLAN. Se non risponde: problema locale (cavo, porta switch)
   - `ping` a srv-dc2 (domain controller). Se non risponde: problema di routing inter-VLAN
   - `ping 8.8.8.8`. Se non risponde ma il DC sì: problema Internet/firewall
   - `nslookup adcompound.com`. Se fallisce: problema DNS

## Problemi frequenti

### WiFi instabile in un'area (produzione/magazzino)

- Verificare lo stato dell'AP UniFi della zona dal controller UniFi
- Controllare il numero di client connessi (sovraccarico?)
- Verificare la copertura: l'area produttiva è molto estesa (CMP, macinazione, insacco, estrusione, silos, trituratore, granulazione). Se il problema è in una zona lontana dagli AP, potrebbe servire un AP aggiuntivo.
- Controllare le interferenze sui canali WiFi

### VLAN non comunicano

- Verificare le regole di routing inter-VLAN sul FortiGate
- Controllare la configurazione trunk sugli switch Cisco delle cabine
- Se il problema è iniziato dopo una modifica al firewall, confrontare la configurazione con il backup precedente (`{{IT_EXTERNAL}}` gestisce le regole)

### ADC-Warehouse non funziona (tablet/Genius Logistics)

- Verificare che lo switch della VLAN warehouse sia attivo
- La rete ADC-Warehouse NON ha Internet by design. Se i tablet non raggiungono srv-tsplus, il problema è tra lo switch warehouse e il server, non la connettività esterna.
- Controllare il servizio TSPlus su srv-tsplus (vedi runbook TSPlus)

### Rete giù per tutta l'azienda

- Verificare lo stato del FortiGate (interfaccia web o console)
- Controllare gli switch core nella sala server
- Se solo Internet è assente ma la rete interna funziona: verificare la linea del provider e valutare il failover su EOLO
- Se anche la rete interna è giù: possibile blackout parziale, verificare gli UPS nelle cabine elettriche

## Cabine elettriche e rete di produzione

L'impianto ha circa 5 cabine elettriche distribuite nell'area produttiva, ciascuna con 1-2 switch rack (alcuni da 48 porte) protetti da UPS. Se un'area di produzione perde la connettività:

- Verificare l'alimentazione della cabina (UPS attivo?)
- Controllare fisicamente i LED dello switch nella cabina
- Se lo switch è spento o in errore, contattare `{{IT_EXTERNAL}}`

## Escalation

- Problemi di configurazione firewall/switch/VLAN → `{{IT_EXTERNAL}}`
- Problemi di rete sui macchinari industriali/Profinet → `{{PLC_VENDOR}}` (NON intervenire direttamente)
- Linea Internet/provider → verificare prima il failover EOLO, poi contattare il provider
