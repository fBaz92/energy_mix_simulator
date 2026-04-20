---
title: "Processo di Ornstein-Uhlenbeck"
category: "Processi stocastici"
order: 10
slug: "ornstein-uhlenbeck"
---

# Il processo di Ornstein-Uhlenbeck

Il prezzo del gas naturale, del carbone e della CO₂ nel simulatore sono modellati come processi di **Ornstein-Uhlenbeck** (OU), la più semplice SDE gaussiana *mean-reverting*.

## Definizione

L'OU è definito dall'equazione differenziale stocastica:

$$
dP_t = \theta\,(\mu - P_t)\,dt + \sigma\,dW_t
$$

dove:

- $P_t$ è il prezzo al tempo $t$;
- $\mu$ è il **valore di equilibrio** (long-run mean) verso cui il processo è attratto;
- $\theta > 0$ è la **velocità di mean-reversion** (più grande $\Rightarrow$ ritorno più rapido a $\mu$);
- $\sigma$ è la **volatilità**;
- $W_t$ è un moto browniano standard, ovvero $dW_t \sim \mathcal{N}(0, dt)$.

### Proprietà

Il processo è gaussiano con momenti noti. Dato $P_0$:

$$
\mathbb{E}[P_t] = \mu + (P_0 - \mu)\,e^{-\theta t}
$$

$$
\operatorname{Var}(P_t) = \frac{\sigma^2}{2\theta}\bigl(1 - e^{-2\theta t}\bigr)
$$

Nel limite $t \to \infty$, $P_t \sim \mathcal{N}\!\left(\mu,\ \frac{\sigma^2}{2\theta}\right)$: la distribuzione stazionaria è normale con media $\mu$ e varianza $\sigma^2/(2\theta)$. Il tempo di dimezzamento dello scostamento da $\mu$ è $\tau_{1/2} = \ln 2 / \theta$.

## Discretizzazione (Euler-Maruyama)

Con passo $\Delta t = 0.25\,\text{h}$ espresso in anni ($\Delta t = 0.25/(24 \cdot 365)$):

$$
P_{t+1} = P_t + \theta\,(\mu - P_t)\,\Delta t + \sigma\,\sqrt{\Delta t}\,\varepsilon_t,\quad \varepsilon_t \sim \mathcal{N}(0,1)
$$

con un floor a $1$ EUR per evitare prezzi non fisici. È quello che fa [`FuelPriceModel.generate_path_from_shocks`](../../../../../../energy_sim/generators.py) in `energy_sim/generators.py:86`.

## Parametri usati

| Processo | $\mu$ | $\sigma$ | $\theta$ |
|----------|-------|----------|----------|
| Gas      | scenario-dipendente (30–80 EUR/MWh_th) | scenario-dipendente | $0.10$ |
| Carbone  | scenario-dipendente | scenario-dipendente | $0.10$ |
| CO₂ (ETS)| $65$ EUR/t | $10$ | $0.05$ |

Il $\theta$ più basso della CO₂ riflette l'**inerzia strutturale del mercato ETS**: le quote europee reagiscono lentamente agli shock perché il cap annuale è noto e il mercato è spesso, mentre il gas reagisce più velocemente agli eventi (meteo, geopolitica).

## Perché l'OU

### I requisiti fisici

I prezzi dei combustibili hanno tre proprietà empiriche che un modello dovrebbe catturare:

1. **Non esplodono**: su orizzonti lunghi il prezzo ha una distribuzione stazionaria, non diverge.
2. **Hanno memoria**: uno shock oggi si propaga nei giorni successivi (persistenza).
3. **Sono volatili**: piccole oscillazioni quotidiane attorno al livello di lungo periodo.

### Il confronto

Un **moto browniano geometrico** (GBM), usato nei modelli finanziari alla Black-Scholes, cattura (2) e (3) ma **non** (1): la varianza cresce linearmente nel tempo e il prezzo è una martingala — può derivare ovunque. Va bene per azioni, male per commodity energetiche osservate per decenni attorno a un range stabile.

Un **processo AR(1)** discreto con $\phi < 1$ è essenzialmente la versione discretizzata dell'OU: stesse proprietà qualitative. L'OU è solo la formulazione in tempo continuo, preferibile perché i parametri $(\mu, \sigma, \theta)$ sono direttamente interpretabili in termini fisici (valore target, ampiezza delle oscillazioni, tempo di ritorno).

Modelli più sofisticati (GARCH, jump-diffusion, mean-reverting con stagionalità) catturano effetti aggiuntivi ma richiedono molti più parametri da stimare e complicano la calibrazione. Per uno studio di scenario Monte Carlo, l'OU offre il miglior compromesso tra **realismo delle code** e **trasparenza dei parametri**.

### Limiti noti

- L'OU è **gaussiano**: non cattura shock estremi ("fat tails") tipici ad esempio del gas durante crisi geopolitiche. Per scenari di stress il floor a 1 EUR è un proxy grezzo ma previene prezzi negativi.
- Non c'è **stagionalità** esplicita (prezzo gas più alto d'inverno): viene modellata indirettamente attraverso scenari con $\mu$ differenti.
- Non c'è **correlazione** tra gas e CO₂, che invece nel mondo reale sono correlati (fuel-switching). Il simulatore supporta correlazione opzionale tra aree di prezzo in [`price_areas.py`](../../../../../../energy_sim/price_areas.py).
