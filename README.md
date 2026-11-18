# GTT Smart (Home Assistant)

Integrazione custom per Home Assistant pensata per monitorare le fermate GTT (Torino e cintura) in modo affidabile.

È nata da un problema pratico: se un'integrazione legge solo i passaggi in tempo reale (`PassaggiRT`) e una corsa momentaneamente non viene tracciata dal GPS, quell'orario sparisce del tutto e ti ritrovi mostrato il passaggio successivo (magari 20-30 minuti dopo), anche se il bus sta arrivando regolarmente.

**GTT Smart** risolve il problema incrociando i dati real-time (`PassaggiRT`) con quelli programmati (`PassaggiPR`) restituiti da GTT: quando il dato real-time c'è, sostituisce l'orario programmato corrispondente; se manca, resta comunque visibile l'orario di tabella.

## Cosa fa

- Unisce in automatico orari real-time e programmati (oppure permette di usare solo uno dei due).
- Legge direttamente l'endpoint GTT senza dipendere da servizi esterni aggiuntivi.
- Al primo inserimento del codice fermata interroga la fermata e mostra le linee e direzioni attive in quel momento.
- Supporta filtri per singola linea, più linee separate da virgola (es. `49, 1S`) oppure tutte le linee della fermata.
- Supporta il filtro per direzione (anche parziale, es. `PORTA SUSA`).
- Permette di aggiungere la stessa fermata più volte con filtri diversi.
- Include un filtro "minuti minimi": utile per nascondere i bus che passano tra 1-2 minuti se abiti a qualche minuto a piedi dalla fermata.
- Tutto è modificabile dalle opzioni dell'integrazione senza doverla riconfigurare da zero.

## Installazione

### Tramite HACS (repository personalizzato)

1. Apri **HACS** in Home Assistant.
2. Menu in alto a destra (tre puntini) -> **Repository personalizzati**.
3. Incolla l'URL del repository: `https://github.com/giacomocavera/ha-gtt-smart`
4. Seleziona categoria **Integrazione** e aggiungi.
5. Cerca **GTT Smart** in HACS, installala e riavvia Home Assistant.

### Manuale

1. Copia la cartella `custom_components/gtt_smart` dentro `/config/custom_components/`.
2. Riavvia Home Assistant.

## Configurazione

Vai su **Impostazioni -> Dispositivi e servizi -> Aggiungi integrazione -> GTT Smart**.

1. Inserisci il numero della fermata (es. `1356`).
2. Nel passaggio successivo scegli il nome del sensore e imposta gli eventuali filtri per linea e direzione (se lasci vuoto, monitora tutto).

Dalle opzioni dell'integrazione (pulsante **Configura**) puoi regolare in qualsiasi momento:
- **Modalità**: `Smart` (RT + programmato), solo `Real-Time` o solo `Programmato`.
- **Nascondi bus tra meno di (minuti)**: per escludere le corse ormai troppo vicine.
- **Intervallo di aggiornamento**: in secondi (default `60`).
- **Tolleranza abbinamento RT/Programmato**: finestra in minuti usata per associare una corsa real-time al suo orario programmato (default `10`).
- Testi personalizzati per lo stato vuoto (`No upcoming bus`) e gli slot vuoti (`--`).

## Entità create

Per ogni fermata/configurazione vengono create tre entità:

- `sensor.<nome>`: prossimo orario di passaggio (es. `12:20`).
  - Attributi principali: `first`, `second`, `third`, `fourth`, `next_is_realtime`, `next_source` (`RT` o `PR`), `next_line`, `next_direction`, `upcoming`, `next_rt`, `next_pr`.
- `sensor.<nome>_minutes`: minuti mancanti al prossimo passaggio (comodo per i trigger nelle automazioni).
- `binary_sensor.<nome>_realtime`: `on` se il prossimo orario mostrato è real-time, `off` se è da tabella programmata.

## Esempio rapido (Widget Android / Template)

Se usi il Widget Modello dell'app Home Assistant su Android:

```jinja2
{% macro row(label, entity, min_entity) -%}
{% set t = states(entity) -%}
{% set m = states(min_entity) -%}
{% set rt = state_attr(entity, 'next_is_realtime') -%}
{% set sec = state_attr(entity, 'second') | default('--', true) -%}
{% if t in ['unavailable', 'unknown', 'No upcoming bus', ''] -%}
<font color="#9CA3AF"><b>{{ label }}</b> · nessun bus</font>
{%- else -%}
{% set col = '#4ADE80' if rt is true else '#FBBF24' -%}
{% set dot = '●' if rt is true else '○' -%}
<font color="#E5E7EB"><b>{{ label }}</b></font> <font color="{{ col }}"><b>{{ dot }} {{ t }}</b></font>{% if m not in ['unavailable', 'unknown', 'none', ''] %} <font color="#D1D5DB"><small>({{ m }}m)</small></font>{% endif %} <font color="#9CA3AF"><small>· {{ sec }}</small></font>
{%- endif %}
{%- endmacro %}
{{ row('🏫➔🏠', 'sensor.bus_station_to_home_schedule', 'sensor.bus_station_to_home_schedule_minutes') }}<br>
{{ row('🏠➔🏋️', 'sensor.bus_home_to_gym_schedule', 'sensor.bus_home_to_gym_schedule_minutes') }}<br>
{{ row('🏋️➔🏠', 'sensor.bus_gym_to_home_schedule', 'sensor.bus_gym_to_home_schedule_minutes') }}
```

## Note

L'integrazione si appoggia agli endpoint pubblici del sito GTT. Se GTT dovesse modificare o dismettere quell'endpoint, potrebbe essere necessario aggiornare il client.

## Disclaimer

Questo è un progetto personale, indipendente e **non ufficiale**. Non è in alcun modo collegato, affiliato, autorizzato o supportato da **GTT (Gruppo Torinese Trasporti S.p.A.)**.

Tutti i marchi, i nomi delle linee e i dati sugli orari appartengono ai rispettivi proprietari. L'integrazione si limita a leggere dati pubblici già accessibili via web per comodità d'uso personale su Home Assistant.

Il software viene fornito **"così com'è"**, senza alcuna garanzia di funzionamento continuo o accuratezza: eventuali ritardi, dati mancanti, cambi alle API da parte di GTT o corse perse non possono essere imputati all'autore. Si consiglia inoltre di mantenere intervalli di aggiornamento ragionevoli (es. 60 secondi o superiori) per non generare traffico inutile verso i server GTT.