# Roadmap — Energy Mix Simulator

Questo documento elenca le direzioni di sviluppo del progetto. Le decisioni di design e lo stato corrente del codice vivono in `CLAUDE.md`; qui sta solo *cosa vogliamo fare dopo*.

Convenzioni di stato:
- ✅ **done** — implementato e testato nel codice principale
- 🚧 **in progress** — parzialmente implementato
- 📋 **planned** — progettato, non ancora iniziato
- 💭 **idea** — da discutere/raffinare prima di pianificare

---

## ✅ Done (sintesi)

Funzionalità già in `energy_sim/` con test e notebook di accompagnamento:

- **Tracking CO₂**: emissioni per timestep/generatore, intensità carbonica annuale, breakdown per tecnologia.
- **Coal generator**: coal come dispatchable termico con fuel price O-U dedicato; merit-order recomputato a ogni step abilita fuel-switching realistico con il CO₂.
- **CO₂ stocastico**: `CarbonPriceModel` come processo O-U (prima era costante).
- **Fuel price sensitivity**: sweep 1D e 2D su μ dei combustibili, heatmap prezzo elettrico vs (gas μ, coal μ), coefficienti di sensitività ∂p/∂μ.
- **Load profile realistico**: fattori per giorno-settimana, calendario festività italiano, rumore intra-day aumentato.
- **Interconnessioni**: import come generatori virtuali nel merit order, export come carico aggiuntivo price-dependent, tracking `net_import` per interconnessione.
- **Battery storage**: `StorageUnit` con SOC sequenziale, soglie charge/discharge su percentili rolling, tracking revenue e SOC timeseries.
- **Price areas & reliability**: moduli dedicati (`energy_sim/price_areas.py`, `energy_sim/reliability.py`) con test.
- **Notebook didattici**: serie 01–11 che copre ogni concetto, più `wind_solar_analysis.ipynb`.
- **Webapp — fasi 1–6**: backend FastAPI che espone `energy_sim/` come libreria, frontend React+Vite+Plotly con pagine Scenarios / Simulations / Results / SimulationDetail / Compare, code-splitting di Plotly, dashboard con grafici per dispatch, interconnessioni, storage.

---

## 🚧 In progress

### Webapp — completamento
**Stato**: fasi 1–6 fatte, manca scenario editor avanzato e integrazione statistiche notebook.
**Cosa manca**:
- Scenario editor completo (slider per ogni tech, parametri fuel/CO₂, interconnessioni editabili).
- Integrazione delle statistiche oggi visibili solo nei notebook (vedi sezione *Webapp stats* sotto).
- Test E2E del flusso scenario → simulation → results → compare.

---

## 📋 Planned

### Price-setter tracking
**Obiettivo**: sapere quale tecnologia sta fissando il prezzo marginale a ogni quarto d'ora, con statistiche aggregate.

Design:
- Nel dispatch, il generatore marginale è già noto a ogni step (è quello la cui SRMC = `marginal_price`). Salvare l'indice della tecnologia in un array `price_setter` di shape `(35040,)` dentro `DispatchResult`.
- Aggregazioni in `run_monte_carlo()`:
  - % ore/anno per tecnologia price-setter (media e σ sugli MC runs).
  - Frequenza condizionata al livello di load (quartili) e al mese.
  - Contributo di ogni tecnologia alla varianza del prezzo medio annuo.
- Visualizzazioni:
  - Duration curve del prezzo colorata per tecnologia price-setter (area chart cumulato).
  - Heatmap mese × ora con tecnologia price-setter dominante.
  - Tabella riassuntiva per la webapp.

Costo stimato: basso (1–2 giorni). Nessun cambio al motore di dispatch, solo post-processing.

### Webapp — statistiche dai notebook
**Obiettivo**: portare nella webapp le analisi oggi disponibili solo nei notebook, come grafici interattivi (Plotly) e tabelle.

Candidati da pianificare (priorità alta → bassa):
1. **Dispatch stack chart** — area stacked per tecnologia con selettore finestra temporale (giorno/settimana/mese).
2. **Price duration curve** — con percentili e possibilità di overlay tra scenari.
3. **Merit order snapshot** — SRMC ordinati delle tecnologie a un istante selezionato.
4. **Emissioni** — intensità carbonica mensile, breakdown per tecnologia, curva CO₂ vs penetrazione rinnovabili.
5. **Sensitivity heatmaps** — prezzo vs (gas μ, coal μ) e altri 2D sweeps.
6. **Storage** — profilo SOC, revenue vs sizing.
7. **Interconnessioni** — flussi netti, duration curve import/export.
8. **Price-setter** (dopo la feature sopra) — % annua per tech, heatmap mese×ora.
9. **Tabelle annuali** — media/σ/percentili prezzo, curtailment, ore di inertia-fix, confronto side-by-side tra scenari.

Da decidere: quali di queste vivono in `ResultsPage` vs `ComparePage` vs una nuova `StatisticsPage`.

### Espansione dispatch idroelettrico (con ML)
**Obiettivo**: sostituire la must-run band fissa con un modello di bacino ideale + policy di dispacciamento appresa.

Idea in 3 fasi:
1. **Bacino ideale + fisica**: singolo reservoir che rappresenta l'unione dei bacini nazionali, inflow stagionali stocastici, modello evaporazione basato su "temperatura giornaliera" (Markov chain mese-dipendente analoga a quella del solare) con lookup table temperatura → evaporazione %.
2. **Baseline policy**: dispacciamento greedy con soglie su percentili di prezzo rolling (stesso pattern della batteria) + vincoli di SOC sul bacino.
3. **Policy appresa con TimesNet**: modello transformer time-series che prende una finestra passata (prezzi, load, SOC, stato meteo) e decide pump/hold/generate. Riferimento: https://github.com/thuml/Time-Series-Library/blob/main/models/TimesNet.py. Confrontato contro la baseline (fase 2) per quantificare il valore dell'agente appreso.

Questa roadmap entry verrà espansa con un plan dedicato prima dell'implementazione.

### Dockerizzazione della webapp
**Obiettivo**: deploy riproducibile della webapp (frontend + backend + worker opzionale).

Scope:
- `docker-compose.yml` con tre servizi: `backend` (FastAPI + `energy_sim/`), `frontend` (nginx che serve il build Vite), `worker` (opzionale, per simulazioni async con code).
- Multi-stage build per il frontend (build Vite → nginx).
- Volume per `webapp/data/` (DB SQLite) così da persistere scenari e run tra restart.
- **Non** dockerizzare la libreria `energy_sim/` da sola né i notebook: lo sviluppo locale resta nativo.

### Scenari storici dei paesi europei (ultimi 5 anni)
**Obiettivo**: scenari pre-costruiti che riproducano il mix reale di IT, DE, FR, ES, CH, PT per 2021–2025, utili come punto di partenza e per backtesting.

Per ogni (paese, anno):
- Mix di generazione (GW installati per tech) da ENTSO-E / Terna / Bundesnetzagentur / RTE / REE / BFE / REN.
- Peak load e domanda annuale.
- Parametri combustibili calibrati su TTF / API2 medi dell'anno.
- Prezzo CO₂ medio EUA dell'anno.
- Interconnessioni reali con NTC da ENTSO-E.

Deliverable:
- Modulo `energy_sim/historical_scenarios.py` con dict `HISTORICAL_SCENARIOS[country][year]`.
- Helper `load_historical_scenario(country, year) -> dict` in `simulation.py`.
- Notebook `12_historical_backtest.ipynb` per confronto prezzi simulati vs reali (GME PUN / EPEX / OMIE).
- Preset "carica Germania 2022" nella webapp.

Non-obiettivi: modellare variazioni di capacità intra-annuali, replicare eventi specifici a risoluzione settimanale, match stretto dei prezzi mensili (il modello è stocastico: matcha distribuzioni, non singoli valori).

---

## 💭 Idee da raffinare

Cose che potrebbero entrare nella roadmap ma che richiedono ancora discussione:

- **Unit commitment semplificato** — min up/down times, startup costs. Rompe la vettorizzazione: vale la pena?
- **Ramp-rate enforcement** tra timestep consecutivi.
- **Domanda elastica / demand response** — curva prezzo-quantità per la domanda invece che profilo rigido.
- **Correlazione spaziale del vento** — oggi tutti i parchi eolici vedono lo stesso processo AR(1).
- **Market coupling multi-zona** — clearing simultaneo invece di import/export pragmatico.
- **Migrazione DB** — da SQLite a PostgreSQL quando la webapp diventa multi-utente.
