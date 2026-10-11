# Delitto in Griglia

App web (PWA) di enigmi di deduzione. Ogni caso è una griglia: una persona per riga e per colonna e tutti gli indizi sono veri. Nei dieci casi classici la vittima era sola con l'assassino.

**Gioca qui:** https://ixion89-cpu.github.io/delitto-in-griglia/

## Come si gioca

1. Scegli un livello: Facile, Medio o Difficile. Sotto, la campagna Stazione Nadir è chiusa da una parola d'ordine e resta sbloccata sul dispositivo.
2. Leggi la storia e gli indizi. Ogni indizio è vero.
3. Sulla mappa ci sono stanze e oggetti. Su tavoli, piante o TV non può stare nessuno; su letti, sedie, poltrone, divani e tappeti sì.
4. Ogni riga e ogni colonna contiene esattamente una persona, vittima compresa.
5. «Accanto» significa che le caselle condividono un lato. Le righe si numerano dall'alto (1, 2, 3…), le colonne con lettere da sinistra (A, B, C…).
6. Posiziona le persone, prendi appunti ed escludi le caselle impossibili. Quando la mappa è completa, verifica e accusa: il colpevole è l'unica altra persona nella stanza della vittima.

Ogni caso ha una sola soluzione.

## In locale

Apri `index.html`, oppure servi la cartella con un server statico (il service worker si registra solo su `http` o `https`).

In `tools/` ci sono il generatore e il verificatore dei casi (`gen.py`, `verify.py`). L'episodio 1 della campagna si controlla con `episode1.py` e con lo stesso `verify.py`.

## Campagna

Sotto Difficile c'è **Stazione Nadir**, episodio 1 «Attracco al buio»: un interludio, poi una griglia 6×6 (accesso non autorizzato, non un omicidio), poi un interludio di chiusura. La parola d'ordine non è nel codice in chiaro.
