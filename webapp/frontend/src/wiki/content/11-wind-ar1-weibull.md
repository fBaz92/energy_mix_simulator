---
title: "Eolico: AR(1) + Weibull + curva di potenza"
category: "Processi stocastici"
order: 11
slug: "wind-ar1-weibull"
---

# Modello eolico: AR(1) gaussiano + Weibull + curva di potenza

La disponibilità eolica è il più elaborato dei modelli stocastici del simulatore: una pipeline a tre stadi che trasforma rumore bianco in fattori di capacità realistici. L'implementazione sta in [`WindAvailability.generate_profile`](../../../../../../energy_sim/generators.py) in `energy_sim/generators.py:367`.

## La pipeline

$$
\varepsilon_t \;\xrightarrow{\text{AR(1)}}\; z_t \;\xrightarrow{\Phi}\; u_t \;\xrightarrow{F_W^{-1}}\; v_t \;\xrightarrow{\text{power curve}}\; \mathrm{CF}_t
$$

### Stadio 1 — AR(1) gaussiano

$$
z_t = \phi\,z_{t-1} + \sqrt{1 - \phi^2}\,\varepsilon_t,\qquad \varepsilon_t \sim \mathcal{N}(0,1)
$$

con $\phi = 0.995$. Il coefficiente $\sqrt{1-\phi^2}$ rende il processo **marginalmente $\mathcal{N}(0,1)$** e stazionario. L'autocorrelazione decade esponenzialmente con costante di tempo

$$
\tau = -\frac{\Delta t}{\ln \phi} \approx \frac{0.25\,\text{h}}{0.005} = 50\,\text{h}.
$$

Cinquanta ore è la scala tipica di un **fronte meteorologico**: un'alta pressione con vento debole può durare 2–3 giorni, una depressione ventosa idem. Questa è la proprietà più importante del modello.

### Stadio 2 — mappa a uniforme

$$
u_t = \Phi(z_t) \in (0,1)
$$

$\Phi$ è la CDF della normale standard. Siccome $z_t$ è $\mathcal{N}(0,1)$, $u_t$ è uniforme in $(0,1)$ per costruzione (probability integral transform).

### Stadio 3 — CDF inversa di Weibull

La velocità del vento in un sito fisso segue empiricamente una **distribuzione di Weibull**:

$$
F_W(v;\lambda,k) = 1 - \exp\!\left[-\left(\frac{v}{\lambda}\right)^{\!k}\right]
$$

Invertendo:

$$
v_t = \lambda_{m(t)}\,\bigl[-\ln(1 - u_t)\bigr]^{1/k}
$$

Il parametro di forma $k$ è fissato ($k \approx 2$, tipico per siti europei). Il parametro di scala $\lambda_{m(t)}$ **dipende dal mese** $m(t)$: in Italia i mesi invernali sono più ventosi ($\lambda \approx 8$ m/s) di quelli estivi ($\lambda \approx 6$ m/s). Tabulato in `MONTHLY_WIND_LAMBDA`.

### Stadio 4 — curva di potenza turbina

La potenza normalizzata della turbina in funzione della velocità del vento è:

$$
P(v) = \begin{cases}
0 & v < v_{\text{cut-in}} \\[4pt]
\left(\dfrac{v - v_{\text{cut-in}}}{v_{\text{rated}} - v_{\text{cut-in}}}\right)^{\!3} & v_{\text{cut-in}} \le v < v_{\text{rated}} \\[8pt]
1 & v_{\text{rated}} \le v \le v_{\text{cut-out}} \\[4pt]
0 & v > v_{\text{cut-out}}
\end{cases}
$$

con $v_{\text{cut-in}} = 3$ m/s, $v_{\text{rated}} = 12$ m/s, $v_{\text{cut-out}} = 25$ m/s. Il tratto cubico riflette il fatto che l'energia cinetica del vento scala come $v^3$.

## Perché queste scelte

### Perché AR(1) e non rumore bianco

Un modello i.i.d. (rumore bianco) produce un profilo eolico che oscilla freneticamente da un quarto d'ora al successivo — fisicamente assurdo. Il vento ha **memoria**: se c'è stato vento forte alle 12:00, è molto probabile che ce ne sia anche alle 12:15. Un sistema elettrico con molta rinnovabile è sensibile agli eventi di scarsità **prolungata** (Dunkelflaute), e quelli emergono solo se il modello ha la giusta autocorrelazione.

### Perché AR(1) gaussiano e non direttamente AR(1) sulla velocità

Perché le velocità del vento **non sono gaussiane** — sono Weibull. Un AR(1) diretto sulla velocità richiederebbe rumore non-gaussiano per preservare la Weibull a lungo termine, e non esistono formulazioni semplici. Il trucco **AR(1) in spazio gaussiano + mappa** (copula gaussiana) disaccoppia il problema:

- la **dipendenza temporale** (autocorrelazione) vive in spazio gaussiano, dove AR(1) è esatta;
- la **distribuzione marginale** (Weibull) è imposta dalla trasformazione.

Il risultato marginale è esattamente Weibull, e la struttura di autocorrelazione è preservata in senso rank-based.

### Perché Weibull e non log-normale o Rayleigh

La Weibull con $k \approx 2$ è **lo standard di fatto** in ingegneria eolica dalla fine degli anni '70. Ha supporto in $[0, \infty)$, un solo modo, coda destra sottile — tutte proprietà osservate empiricamente. La **Rayleigh** è il caso speciale $k=2$ della Weibull ed è usata quando non si hanno dati di sito. La **log-normale** ha code destre troppo pesanti (sovrastima eventi di vento estremo). Weibull generale è il sweet spot: un parametro in più rispetto a Rayleigh ($k$ varia 1.8–2.3) per adattarsi al sito.

### Perché $\lambda$ mensile e non $\lambda$ costante

La stagionalità del vento in Italia è marcata e coerente con l'andamento della domanda invernale. Un modello con $\lambda$ costante sottostimerebbe la correlazione rinnovabili-carico, e con essa la frequenza di eventi di **prezzo negativo** (sovra-generazione in estate) e di **scarcity** (calma invernale con domanda alta).

## Limiti

- **Singola "area eolica"**: tutto il vento del Paese vede lo stesso $z_t$. Nel mondo reale Sicilia e Sardegna vedono venti diversi dalla Puglia. Non c'è correlazione spaziale parziale. Per scenari multi-zona si può generare un profilo indipendente per ciascuna area, ma attualmente il simulatore usa un solo processo.
- **Curva di potenza idealizzata**: nessuna modellazione di wake effects, fuori-servizio, ostructioni.
- **$k$ costante**: in realtà $k$ varia leggermente con la stagione, ma l'effetto dominante è catturato da $\lambda(m)$.
- **Implementazione**: il loop AR(1) è in Python puro e non vettorializzato. Per batch molto grandi si può sostituire con `scipy.signal.lfilter`.
