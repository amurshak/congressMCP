# §17 query sets — verbatim, for V20 and V21

Extracted from the six §17 trace files. **30 search calls, 115 individual queries, 7 zero-hit rounds.**
Machine-readable form in `v20-query-sets.json`, one object per search call with:
`target` (congress/bill_type/number/version as issued), `queries` (verbatim, in order),
`max_hits`, `n_hits`, `top_hits` (first 10 section_ids), and `fetched_after` — the
`get_bill_section` calls the model made before its next search, which is the best available
evidence of which unit it treated as the answer. `!` marks a call that errored.

## Known-correct targets

For V20's diagnostic — *does the correct unit ever rank worse under fusion than under its own
best single query?* — these are the units §17 established as correct:

- `S:141.` — A1 tanker inventory (10 U.S.C. 9062(j))
- `S:147.` — A2 A-10 minimum inventory
- `D:W/T:VIII/ST:A/S:804.` — A3 tribal jurisdiction (25 U.S.C. 1304)
- `D:G/T:LXXII/ST:A/S:7201./SS:(e)/CHUNK:3` — B1 training on workings of Congress
- `D:G/T:LXXI/ST:B/S:7117.` — E1/E2 polar security cutter updates
- `D:G/T:LXXII/ST:B/S:7215.` — E1/E2 Great Lakes icebreaking
- `T:VII/ST:A/S:70104.` — D4 child tax credit
- `D:A/T:XVIII/ST:D/S:1832.` — B3/D5 modular open system approach
- `D:C/T:XXXI/ST:B/S:3111.` — C1 atomic energy defense codification

## Caveats on using `fetched_after` as ground truth

It records what the model **chose**, not what is **correct**. In most cases they coincide and
§17 verified the answer. Two exceptions: the A3 id-guessing sequence contains four
`section_not_found` errors before the right id, and the floor B1 run made no calls at all.
Use the table above for targets and `fetched_after` for corroboration, not the reverse.

## Zero-hit rounds are part of the data

7 of 30 rounds returned nothing. Those are the phrase-matching finding (F9) and should be
**included** in any query-family imbalance measurement — a concept that consumed a whole
round and returned zero still competed for the model's attention budget.

```
package_id | n_queries | n_hits | queries | fetched after
BILLS-117hr2471enr | 2 | 1 | Division W ; Sec. 804 | D:W/S:804.!, D:W/T:VIII/S:804.!, D:W/T:VIII!
BILLS-117hr2471enr | 3 | 9 | special tribal criminal jurisdiction ; Sec. 804 ; SEC. 804 | D:W/T:VIII/ST:A/S:804.
BILLS-119s1071enr | 3 | 6 | air refueling tanker aircraft ; total aircraft inventory ; tanker | D:A/T:I/ST:D/S:141.
BILLS-119s1071enr | 3 | 2 | A-10 aircraft ; primary mission aircraft inventory ; 96 A-10 | D:A/T:I/ST:D/S:147., D:W/S:804!, D:W/T:VIII/S:804.!, D:W/T:VIII!
BILLS-117hr2471enr | 3 | 12 | Alaska Tribal public safety empowerment ; special Tribal criminal jurisdiction ; Indian Civil Rights Act of 1968 | D:W/T:VIII/ST:A/S:804., D:G/S:7002., D:G/S:7103.
BILLS-119s1071enr | 2 | 5 | Coast Guard Academy ; merchant mariner credential | -
BILLS-119s1071enr | 1 | 15 | title 46, United States Code, is amended | -
BILLS-119s1071enr | 1 | 40 | title 14, United States Code, is amended | D:G/T:LXXVII/S:7701.
BILLS-119s1071enr | 5 | 0 | Coast Guard title 10, United States Code, is amended ; Coast Guard title 37, United States Code ; Coast Guard title 5, United States Code, is amended ; title 33, United States Code, is amended ; title 49, United States Code, is amended Coast Guard | -
BILLS-119s1071enr | 3 | 0 | Coast Guard is operating amended title 10 ; Coast Guard Reserve title 10 amended ; title 6, United States Code | -
BILLS-119s1071enr | 5 | 0 | congressional operations training ; training on Congress ; legislative process training ; flag officers training ; senior officials training | -
BILLS-119s1071enr | 5 | 0 | Coast Guard training congressional ; flag officer congressional operations ; role of Congress training ; congressional engagement training ; Coast Guard senior officers education | -
BILLS-119s1071enr | 1 | 15 | Coast Guard | -
BILLS-119s1071enr | 5 | 13 | legislative branch ; appropriations process ; congressional affairs ; flag officers ; oversight role of Congress | D:G/T:LXXII/ST:A/S:7201./SS:(e)/CHUNK:3, S:1, PRE:1, 1832!, D:A/T:XVIII/ST:D/S:1832., D:A/T:XVIII/ST:D/S:1832.
BILLS-119s1071enr | 3 | 8 | weapons activities ; defense environmental cleanup ; National Nuclear Security Administration | -
BILLS-119s1071enr | 4 | 2 | polar security cutter ; icebreaker ; Arctic Security Cutter ; heavy polar icebreaker | D:G/T:LXXI/ST:B/S:7117.
BILLS-119s1071enr | 4 | 22 | Polar Security ; polar ; icebreaking ; Arctic | -
BILLS-119s1071enr | 6 | 0 | cryptocurrency mining ; digital asset mining ; cryptocurrency ; virtual currency ; blockchain ; bitcoin | -
BILLS-119s1071enr | 6 | 8 | digital asset ; crypto ; mining ; distributed ledger ; stablecoin ; financial technology | S:2., D:H/T:IX/S:9999!
BILLS-119hr1enr | 4 | 1 | child tax credit ; qualifying child credit ; refundable credit child ; social security number child credit | T:VII/ST:A/S:70104., 804!, 804.!, D:E/T:VIII/S:804., D:W/T:VIII/ST:A/S:804., D:W/T:VIII/ST:A/S:804./PARA:(3), D:X/T:VIII/ST:A/S:804.
BILLS-119s1071enr | 6 | 22 | icebreaker ; polar security cutter ; Arctic ; ice-capable vessel ; Great Lakes icebreaker ; polar | -
BILLS-119s1071enr | 8 | 1 | Arctic Security Cutter ; icebreaking ; ice season ; medium icebreaker ; commercially available icebreaker ; polar operations ; ice-strengthened ; Healy | -
BILLS-119s1071enr | 7 | 5 | Arctic District ; Bering Strait ; cutter acquisition ; vessel traffic Arctic ; Arctic infrastructure ; Arctic operations Coast Guard ; high latitude | D:G/T:LXXI/ST:B/S:7117., D:G/T:LXXII/ST:B/S:7215., D:G/T:LXXI/ST:B/S:7111., D:G/T:LXXIII/ST:C/S:7322.
BILLS-119s1071enr | 7 | 7 | Storis ; Mackinaw ; Seventeenth Coast Guard District ; domestic icebreaking ; Alaska homeport ; Arctic strategy Department of Defense ; Arctic Council | D:G/T:LXXVII/S:7701.
BILLS-119s1071enr | 3 | 4 | polar security cutter ; icebreaker ; Coast Guard housing | -
BILLS-119hr3838eh | 3 | 0 | Space Force end strength ; authorized strengths commissioned officers Space Force ; Space Force active duty end strength | -
BILLS-119hr3838eh | 3 | 20 | Space Force ; end strengths ; officers | D:A/T:V/ST:A/S:502.
BILLS-119s1071enr | 3 | 20 | Space Force ; end strengths for active forces ; general officers on active duty | D:A/T:V/ST:A/S:502., D:A/T:V/ST:A/S:501., D:A/T:V/ST:A/S:501.
BILLS-119s1071enr | 4 | 0 | cryptocurrency mining ; crypto mining ; digital asset mining ; cryptocurrency | -
BILLS-119s1071enr | 2 | 2 | polar security cutter ; icebreaker | -
```
