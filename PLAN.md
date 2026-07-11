# Plan: Hermes handlar aktier

**Mål:** Testa hur bra en AI kan bedöma köp/sälj på Stockholmsbörsen, med målet att gå med vinst.
**Upplägg:** Paper trading först → utvärdera → litet riktigt kapital om resultatet håller.
**Beslutsfrekvens:** 1–2 gånger per dag, baserat på kursdata + nyheter.

---

## Fas 0 — Det du behöver ha koll på (aktie-grunderna)

Det här är sakerna som äter upp vinsten om man inte räknar med dem. Hermes måste simulera dem redan i paper trading, annars ljuger resultatet.

| Begrepp | Vad det är | Varför det spelar roll |
|---|---|---|
| **Courtage** | Avgift per affär (Avanza: ~0,25 %, min 1 kr på "Mini") | Handlar Hermes ofta med små belopp äter courtaget vinsten. 2 affärer/dag = ~500 affärer/år. |
| **Spread** | Skillnad mellan köp- och säljkurs | I småbolag kan spreaden vara 1–2 %. Du förlorar den direkt vid varje köp. |
| **Likviditet** | Hur mycket aktien omsätts | Illikvida aktier = stor spread + svårt att sälja. Håll Hermes till Large/Mid Cap i början. |
| **Slippage** | Du får sämre pris än du såg | Kursen du beslutar på kl 08:45 är inte kursen du får kl 09:00. Simuleras med t.ex. +0,2 % påslag. |
| **ISK-skatt** | Schablonskatt på kontovärdet (~1 % /år) | Relevant först i fas 3. Vinster beskattas inte separat på ISK — bra för aktiv handel. |
| **Benchmark** | Jämförelseindex (OMXS30GI) | "Vinst" räcker inte. Om Hermes gör +5 % när index gör +10 % var det en förlustaffär mot att bara köpa indexfond. |

**Riskregler (hårdkodade, INTE upp till AI:n att besluta):**

- Max 10 % av portföljen i en enskild aktie
- Max 8 innehav samtidigt (lättare att följa och utvärdera)
- Endast Large/Mid Cap på Nasdaq Stockholm i fas 1
- Stop loss: position som backat 8 % från köpkurs säljs automatiskt
- Circuit breaker: om portföljen totalt backat 15 % → all handel pausas, du får larm via Telegram

Varför hårdkodade? LLM:er är bra på analys men kan "prata sig ur" regler i stunden ("den vänder snart..."). Riskhantering ska vara kod, inte omdöme. Det är exakt så proffsen separerar det.

---

## Fas 1 — Bygg paper trading (vecka 1–3)

Ingen mäklare behövs. Hermes handlar mot riktiga kurser med låtsaspengar (100 000 "kr") i en egen databas på Proxmox-servern.

**Proxmox-tips:** Kör trading-delen i en egen LXC-container (Debian, 1 kärna / 1 GB RAM räcker gott). Då kan du ta snapshot innan varje större kodändring och rulla tillbaka om något går sönder — och den stör inte resten av Hermes.

### Arkitektur

```
┌──────────────── Proxmox LXC (Hermes trading) ─────────────────────────┐
│                                                                        │
│  Cron 08:45 + 17:30 (vardagar)                                        │
│       │                                                                │
│       ▼                                                                │
│  1. Hämta kurser (yfinance, .ST-tickers)                              │
│  2. Hämta nyheter (MFN.se RSS + Placera RSS)                          │
│  3. Bygg prompt: portfölj + kurser + nyheter + regler                 │
│  4. LLM-anrop → JSON-beslut med motivering                            │
│  5. Validera mot riskregler (kod, inte AI)                            │
│  6. Uppdatera portfölj i SQLite (simulera courtage + slippage)        │
│  7. Skicka Telegram-rapport till dig                                  │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### Datakällor (gratis)

- **Kurser:** `yfinance` (Python) — svenska aktier har suffix `.ST`, t.ex. `VOLV-B.ST`, `ERIC-B.ST`. Gratis, dagsdata räcker för 1–2 beslut/dag.
- **Nyheter:** MFN.se har RSS-flöden med pressmeddelanden från alla nordiska börsbolag — det är samma källa som proffsen får sina pressmeddelanden från. Plus Placera och DI:s RSS för marknadsnyheter.
- **Senare (valfritt):** Börsdata API (~betaltjänst, ca 100 kr/mån) för nyckeltal som P/E, skuldsättning m.m. om du vill ge Hermes fundamentaldata.

### Beslutet — JSON, inte fritext

Hermes ska svara i strikt format så koden kan agera på det:

```json
{
  "decisions": [
    {
      "action": "BUY",
      "ticker": "VOLV-B.ST",
      "amount_sek": 8000,
      "confidence": 0.7,
      "reasoning": "Q2 report beat estimates, truck orders up 12%..."
    }
  ],
  "market_view": "Cautiously positive, OMXS30 above 50-day MA"
}
```

Varför `reasoning` är obligatoriskt: det är själva experimentet. Om Hermes går back vill du kunna läsa VARFÖR den köpte — var det dålig analys eller otur? Det är skillnaden mellan att lära sig något och att bara singla slant.

### Loggning — viktigast av allt

Varje beslut sparas med: tidpunkt, kurs vid beslut, hela motiveringen, vilka nyheter som fanns i prompten. Utan detta kan du inte utvärdera om AI:n faktiskt är bra eller bara hade tur i en uppåtmarknad.

### Byggsteg (ett i taget, i ordning)

1. Python-skript som hämtar kurser för en watchlist (~30 Large Cap-aktier) med yfinance
2. Skript som hämtar och filtrerar RSS från MFN/Placera (bara watchlist-bolagen)
3. SQLite-schema: `portfolio`, `trades`, `decisions`, `daily_snapshot`
4. Prompt + LLM-anrop + JSON-validering
5. Riskregel-validering + portföljuppdatering med simulerat courtage (0,25 %) och slippage (0,2 %)
6. Telegram-rapport (daglig sammanfattning + varje affär)
7. Cron-jobb + parallell "benchmark-portfölj" som bara köper OMXS30-indexfond dag 1

---

## Fas 2 — Kör och utvärdera (3 månader)

Kör paper trading i minst 3 månader utan att ändra strategi mitt i (annars vet du inte vad du utvärderar).

**Mät varje vecka:**

- Total avkastning vs OMXS30GI (benchmark-portföljen)
- Win rate: andel affärer med vinst
- Största enskilda förlust och max drawdown (största fallet från toppen)
- Genomsnittlig innehavstid

**Godkänt för fas 3 = ALLA tre:**

1. Slår benchmark efter simulerade avgifter
2. Max drawdown under 15 %
3. Du förstår motiveringarna bakom både de bästa och sämsta affärerna

Var beredd på: 3 månader är statistiskt kort. Även ett bra resultat kan vara tur. Men det räcker för att avslöja om Hermes gör uppenbart dumma saker.

---

## Fas 3 — Riktiga pengar (litet belopp)

**Rekommendation: semi-automatiskt.** Hermes skickar köp/sälj-förslag med motivering via Telegram, du godkänner och lägger ordern själv i Avanza-appen (tar 1 min, 1–2 ggr/dag).

Varför inte helautomatiskt? Läget för svenska mäklar-API:er är dåligt:

- **Nordnet** har ett officiellt API men tar inte in nya kunder på det just nu
- **Avanza** har inget officiellt API. Det finns ett inofficiellt (Python-biblioteket `avanza-api`) som kan lägga ordrar via TOTP-inloggning — men det kan sluta fungera när som helst, ligger i gråzon mot Avanzas villkor, och kräver att din TOTP-secret ligger på servern. Inget att bygga riktig handel på.

Semi-auto ger dig dessutom en mänsklig spärr — vilket är rimligt tills Hermes bevisat sig.

**Startkapital:** belopp du helt kan avvara, t.ex. 10 000–20 000 kr på ett separat ISK (öppna ett nytt konto så det inte blandas med annat). Samma riskregler som i paper trading.

---

## Kostnader

| Post | Kostnad |
|---|---|
| Kursdata (yfinance) + nyheter (RSS) | 0 kr |
| LLM-anrop, 2 st/dag (Claude API) | ~20–60 kr/mån beroende på modell och promptstorlek |
| Börsdata API (valfritt, fas 2+) | ~100 kr/mån |
| Riktigt kapital (fas 3) | Bara det du är beredd att förlora |

---

## Viktiga förbehåll

- Aktiehandel innebär risk — du kan förlora hela beloppet i fas 3. Detta är ett experiment, inte en inkomstplan.
- Ingen forskning visar att LLM:er konsekvent slår index. Det mest sannolika utfallet är att Hermes går sämre än en indexfond — och det är ett helt okej resultat för experimentet, för då har du lärt dig det på låtsaspengar.
- Detta är inte finansiell rådgivning.
