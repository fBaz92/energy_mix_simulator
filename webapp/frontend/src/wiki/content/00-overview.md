---
title: "Panoramica del simulatore"
category: "Introduzione"
order: 0
slug: "overview"
---

# Panoramica del simulatore

Questo simulatore stima la distribuzione del **prezzo marginale annualizzato** dell'energia elettrica al variare del mix di generazione. Il sistema di riferimento è quello italiano (picco $\approx 60$ GW) ma la libreria è agnostica rispetto alla tecnologia.

## Il ciclo di simulazione

Ogni "anno Monte Carlo" è una realizzazione stocastica del sistema:

1. **Griglia temporale**: l'anno è discretizzato a $\Delta t = 15$ minuti, per $N = 35\,040$ timestep.
2. **Profilo di carico**: il carico orario è una curva moltiplicativa (mese × giorno × ora) con rumore.
3. **Paths stocastici**: per ciascun generatore vengono generati i path di prezzo combustibile (OU), prezzo CO₂ (OU) e disponibilità (solare, vento, ecc.).
4. **Dispatch**: a ogni timestep gli impianti sono chiamati in **merit order** crescente di SRMC fino a coprire il carico residuo; il costo marginale dell'ultimo impianto dispacciato è il **prezzo di sistema**.
5. **Vincoli di sistema**: se l'inerzia aggregata scende sotto $H_{\min}=3.5$ s, viene acceso al minimo tecnico il synchronous più economico, curtailando le rinnovabili se serve.
6. **Aggregazione**: il prezzo annualizzato è la media pesata sull'energia generata (non sul tempo).

Ripetendo $M$ volte il ciclo si ottiene la distribuzione empirica del prezzo annuo.

## Perché Monte Carlo

Il prezzo dell'energia è una funzione fortemente non lineare di input che sono essi stessi stocastici (combustibili, CO₂, vento, nuvole). Una singola corsa deterministica con input medi fornisce un **punto**, non una **distribuzione**. Il metodo Monte Carlo permette di:

- stimare percentili (es. $P_{5}$, $P_{95}$) e deviazione standard;
- misurare la sensibilità del prezzo atteso a una perturbazione del mix;
- catturare eventi rari (week "scarsi" di vento, shock gas) che il valor medio nasconde.

## Unità di misura

Tutti i prezzi sono in EUR/MWh elettrico, salvo quando marcati `EUR/MWh_th` (termico). Le potenze sono memorizzate internamente in *per-unit* rispetto a $P_\text{base}=60$ GW; convertite a GW solo per i grafici di dispatch.

## Struttura della wiki

Le sezioni successive approfondiscono:

- **Processi stocastici**: OU per combustibili/CO₂, AR(1)+Weibull per il vento, Markov chain per le nuvole.
- **Dispatch**: merit order, vincolo di inerzia, storage, interconnessioni.

Ogni sezione spiega prima la matematica del modello, poi **perché** è stato scelto rispetto alle alternative.
