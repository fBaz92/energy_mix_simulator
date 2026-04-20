---
title: "Solare: inviluppo deterministico + catena di Markov per le nuvole"
category: "Processi stocastici"
order: 12
slug: "markov-clouds"
---

# Modello solare: inviluppo deterministico × catena di Markov

La disponibilità solare è decomposta in **due fattori indipendenti**:

$$
\mathrm{CF}_t = \underbrace{k_\text{month}(m_t)\,k_\text{hour}(h_t)}_{\text{inviluppo deterministico}}\;\times\;\underbrace{k_\text{cloud}(t)}_{\text{attenuazione nuvole}}
$$

L'inviluppo rappresenta l'**irradianza teorica** (geometria Sole-Terra), l'attenuazione modella la **copertura nuvolosa** come processo stocastico. Implementato in [`SolarAvailability.generate_profile`](../../../../../../energy_sim/generators.py) in `energy_sim/generators.py:267`.

## L'inviluppo deterministico

Il fattore mensile $k_\text{month}(m)$ normalizza l'irradianza media per mese (giugno $\approx 1$, dicembre $\approx 0.3$). Il fattore orario $k_\text{hour}(h)$ è una **gaussiana centrata alle 13:00**:

$$
k_\text{hour}(h) \propto \exp\!\left[-\frac{(h - 13)^2}{2\sigma_h^2}\right]
$$

hard-zerata di notte. Le costanti sono tabulate in `HOURLY_SOLAR_ENVELOPE` e `MONTHLY_SOLAR_FACTORS`.

## La catena di Markov

### Definizione

Una **catena di Markov a due stati** modella la copertura nuvolosa con granularità **giornaliera** (un giorno o è prevalentemente sereno o coperto). Lo stato $S_d \in \{\text{sunny}, \text{cloudy}\}$ al giorno $d$ evolve con matrice di transizione mensile $T_m$:

$$
T_m = \begin{pmatrix}
1 - p_{s \to c}(m) & p_{s \to c}(m) \\[4pt]
p_{c \to s}(m) & 1 - p_{c \to s}(m)
\end{pmatrix}
$$

La **proprietà di Markov** dice che $S_d$ dipende solo da $S_{d-1}$, non dalla storia più remota:

$$
\mathbb{P}(S_d \mid S_{d-1}, S_{d-2}, \ldots, S_0) = \mathbb{P}(S_d \mid S_{d-1}).
$$

I parametri $p_{s \to c}$ (probabilità che un giorno sereno sia seguito da uno coperto) e $p_{c \to s}$ variano col mese: d'inverno la persistenza nuvolosa è maggiore ($p_{c \to s}$ piccola $\Rightarrow$ streak più lunghi), d'estate il contrario. Tabulato in `CLOUD_TRANSITION`.

### Distribuzione stazionaria

Per una catena ergodica su due stati, la probabilità di lungo periodo di essere nuvoloso è:

$$
\pi_\text{cloudy} = \frac{p_{s \to c}}{p_{s \to c} + p_{c \to s}}
$$

Questo fornisce un controllo di sanity: dato un valore target annuo di giorni nuvolosi (da dati storici), si calibrano $p_{s \to c}$ e $p_{c \to s}$ in modo che $\pi_\text{cloudy}$ sia coerente.

### Attenuazione

Una volta determinato lo stato giornaliero, il fattore di attenuazione è tirato uniformemente:

$$
k_\text{cloud}(t) \sim \begin{cases}
\mathcal{U}(0.15,\ 0.40) & \text{se } S_{d(t)} = \text{cloudy} \\
\mathcal{U}(0.85,\ 1.00) & \text{se } S_{d(t)} = \text{sunny}
\end{cases}
$$

indipendente per ogni quarto d'ora. Questo aggiunge la variabilità intra-giorno (una nuvola di passaggio anche in una giornata serena).

## Perché una catena di Markov

### L'alternativa scartata: rumore i.i.d. giornaliero

Il modello più semplice sarebbe tirare ogni giorno `cloudy` con probabilità $p$ indipendentemente. Va bene per la media, **male per le streak**: nella realtà le perturbazioni atmosferiche durano 2–5 giorni (passaggio di un fronte). Un modello i.i.d. produrrebbe troppi switch sunny/cloudy — sottostimerebbe eventi di scarsità fotovoltaica prolungata di più giorni, che sono quelli critici per un sistema ad alta penetrazione solare.

### La catena di Markov in una riga

È il **minimo livello di memoria**: lo stato di oggi dipende dallo stato di ieri, nient'altro. Un solo bit di memoria extra rispetto al modello i.i.d., ma basta a produrre cluster di giorni coerenti. La distribuzione delle lunghezze delle streak diventa geometrica, con media $1/p_{c \to s}$ per le streak nuvolose — un parametro interpretabile e calibrabile.

### Granularità giornaliera e non oraria

La copertura nuvolosa **sinottica** (fronti, anticicloni) evolve su scala di giorni, non di ore. Una catena oraria richiederebbe probabilità di transizione molto vicine a 1 (persistenza estrema ora-su-ora) ed è praticamente equivalente a una catena giornaliera + rumore intra-day, che è esattamente il modello scelto.

### Perché non AR(1) come per il vento

Il vento è una **variabile continua** (velocità $\in \mathbb{R}_+$) che varia gradualmente: AR(1) è naturale. La copertura nuvolosa è più vicina a un **regime discreto** (ci sono o non ci sono): la cattura con due stati più attenuazione stocastica è semanticamente più pulita e richiede meno parametri. Lo stesso comportamento si potrebbe approssimare con un AR(1) soglia, ma la catena di Markov è più trasparente.

## Indipendenza solare-vento

Nel simulatore attuale il processo eolico e quello delle nuvole sono **indipendenti**. Nella realtà c'è una correlazione negativa debole (giornate di vento forte tendono a essere nuvolose, e viceversa calme anticicloniche estive). Non è modellata. Per scenari stress-test che dipendono da eventi simultanei di scarsità solare *e* eolica (Dunkelflaute), questo può portare a una leggera **sottostima** della co-occorrenza.
