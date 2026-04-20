---
title: "Dispatch: merit order e vincolo di inerzia"
category: "Dispatch"
order: 20
slug: "merit-order"
---

# Dispatch: merit order e vincolo di inerzia

Il cuore del simulatore è il **dispatch economico** che, a ogni quarto d'ora, decide quali impianti accendere per coprire il carico e determina il **prezzo marginale** del sistema. Il codice sta in [`dispatch.py`](../../../../../../energy_sim/dispatch.py).

## Merit order: il principio

Ogni generatore ha un **costo marginale di breve periodo** (SRMC) che rappresenta il costo variabile per produrre un MWh aggiuntivo:

$$
\mathrm{SRMC}_i(t) = \underbrace{\frac{p_\text{fuel}^{(i)}(t)}{\eta_i}}_{\text{combustibile}} \;+\; \underbrace{\frac{p_{\mathrm{CO_2}}(t)\,\epsilon_i}{\eta_i}}_{\text{carbonio}} \;+\; \underbrace{\mathrm{VOM}_i}_{\text{O\&M variabile}}
$$

dove $\eta_i$ è l'efficienza termica-elettrica e $\epsilon_i$ il fattore di emissione in $\text{tCO}_2/\text{MWh}_\text{th}$. I costi fissi (capex, F-O&M) **non** entrano nell'SRMC perché sono sunk — non influenzano la decisione di produrre un MWh in più *ora*.

Al tempo $t$ gli impianti sono ordinati per SRMC crescente e chiamati a produrre fino a coprire il carico residuo $L(t)$ (carico meno rinnovabili must-take). Il **prezzo di sistema** è l'SRMC dell'**ultimo impianto dispacciato** — il cosiddetto *marginal unit* o *price setter*:

$$
\pi(t) = \mathrm{SRMC}_{j^*(t)}(t),\quad j^*(t) = \arg\max_{j \in \text{dispatched}(t)}\ \text{rank}_\text{SRMC}(j).
$$

Questo è il modello del **mercato day-ahead europeo zonale**: pay-as-cleared uniform price, assunzione copper-plate intra-zona.

### Perché proprio il marginale

Il prezzo marginale è l'unico che rende coerente l'offerta di *tutti* gli impianti dispacciati: ognuno di essi è disposto a produrre perché riceve almeno il proprio SRMC. Se il prezzo fosse inferiore al marginale, l'ultimo impianto non produrrebbe e il carico non sarebbe coperto; se fosse superiore, ci sarebbe offerta inframarginale non utilizzata. L'equilibrio di Walras di breve periodo coincide col SRMC del price setter.

## Il vincolo di inerzia

### Perché serve

I generatori **sincroni** (turbine rotanti accoppiate alla rete) immagazzinano energia cinetica nelle loro masse rotanti. Questa **inerzia** stabilizza la frequenza: se il carico improvvisamente aumenta, la frequenza cala ma l'inerzia rallenta la caduta (RoCoF, rate of change of frequency), dando tempo ai servizi di regolazione primaria di intervenire.

Fotovoltaico e eolico moderni sono **non-sincroni** (collegati via inverter): non contribuiscono inerzia. Un sistema con poca inerzia è fragile: in un blackout simile a quello in Sud Australia del 2016, RoCoF elevati innescano trip a cascata.

### Formalizzazione

L'inerzia di sistema al tempo $t$ è la **media pesata per capacità online** delle costanti $H_i$ (secondi):

$$
H_\text{sys}(t) = \frac{\sum_{i\in\text{online}(t)} S_i\,H_i}{\sum_{i\in\text{online}(t)} S_i}
$$

dove $S_i$ è la capacità apparente dell'impianto $i$. Il vincolo è:

$$
H_\text{sys}(t) \;\geq\; H_\text{min} = 3.5\,\text{s}.
$$

### L'algoritmo di fix

Il dispatch procede in fasi:

1. **Fase 1** (vettoriale): dispatch merit-order ignorando l'inerzia.
2. **Fase 2** (iterativa sui timestep in violazione): se $H_\text{sys}(t) < H_\text{min}$:
   - accendi al **minimo tecnico** $p_i^{\min}$ il synchronous offline più economico;
   - ricalcola $H_\text{sys}(t)$;
   - se l'offerta eccede il carico, **curtaila le rinnovabili** non-sincrone (energy spillage);
   - ripeti finché $H_\text{sys}(t) \geq H_\text{min}$ o non ci sono più synchronous disponibili.
3. **Fase 3**: re-dispatch a valle di import/export.

Le interconnessioni HVDC **non** contribuiscono a $H_\text{sys}$ (sono inverter-based) — riflette un effetto reale: più HVDC $\Rightarrow$ meno inerzia naturale.

### Perché questa formulazione

#### Perché soglia e non penalità nel merit order

Si potrebbe inserire l'inerzia come **constraint penalty** in un problema di ottimizzazione lineare, rendendo il dispatch la soluzione di un LP. Sarebbe più elegante ma:

- richiede un solver (gurobi, highs) e rompe la vettorializzazione pura numpy;
- il parametro da tarare è una penalità arbitraria senza controparte fisica;
- $H_\text{min} = 3.5$ s ha invece una giustificazione operativa (soglia RoCoF dei TSO).

Il pragmatic fix con soglia hard è un'ottima approssimazione a costo di un loop non vettoriale solo sui timestep in violazione (tipicamente $0$–$5\%$ dei timestep col mix italiano).

#### Perché minimo tecnico e non dispatch pieno

Accendere un CCGT al minimo tecnico (40–50% capacità) aggiunge l'inerzia necessaria con il **minimo impatto sul merit order**: gli impianti più economici già dispacciati non vengono sostituiti. Se si accendesse al massimo, bisognerebbe spegnere impianti più economici, distorcendo il prezzo marginale in modo artefattuale.

#### Perché curtailare le rinnovabili

Se l'impianto sincrono acceso al minimo causa sovra-generazione, qualcuno deve cedere. Le rinnovabili hanno SRMC $\approx 0$ e **nessun costo di startup**: curtailarle è l'opzione economicamente dominante e riflette la prassi europea (curtailment remunerato ma prioritario rispetto al de-load di termoelettrico sincrono).

## Interconnessioni e storage in breve

- **Import**: entrano nel merit order come *virtual generator* con $\mathrm{SRMC} = p_\text{foreign} + c_\text{transport}$. Se sono più economici di un generatore domestico, spiazzano quello.
- **Export**: aggiustamento post-dispatch quando il marginale domestico è inferiore al prezzo estero netto.
- **Storage (BESS)**: SOC sequenziale, trigger di carica/scarica su percentili di prezzo rolling. Contribuisce inerzia sintetica quando lo stato di carica lo consente. Dettagli in una sezione dedicata (TBD).

## Limiti noti

- **No unit commitment**: niente min-up/min-down, niente sequenza di startup con vincoli temporali.
- **No ramp rate inter-timestep**: solo il minimo tecnico è enforced, non la velocità di salita.
- **Copper-plate intra-zona**: niente vincoli di trasmissione interni.
- **Nessuna elasticità della domanda**: $L(t)$ è esogeno.
