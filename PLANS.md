# PLANS.md
First version (2026-11-01), kept for comparison. Later changes to the plan are recorded under "Change log" and do not overwrite it directly.

## Approach
Work through the STEPs continuously in the order of VERIFY.md; when to stop: see CLAUDE.md rule 4; each step also re-runs the tests of the earlier STEPs. Build only what BRIEF asks for.
The whole of Batch 1 (STEP 0–7) is done on a single branch `batch-1`, and merged into main after passing the batch gate.
Batch 2 (STEP 8, ending with the Corvane re-exam per STEP 7) is done on branch `batch-2`, started from main after Batch 1 was merged.
Batch 3 (STEP 9–12: common items, BOM, cost sheet, re-exam) is done on branch `batch-3`, started from main after Batch 2 was merged.

## Progress
- [x] STEP 0 Environment, manager (recognising documents, scheduling, status, review)
- [x] STEP 1 DFM / change-impact station
- [x] STEP 2 Engineering-release station (formal spec, BOM, drawing PDF, STEP)
- [x] STEP 3 Costing station
- [x] STEP 4 PO check station
- [x] STEP 5 Supply-chain station
- [x] STEP 6 Kalvara full flow
- [x] STEP 7 Corvane exam (Batch 1 stopped at A0 engineering release: issue #18; passed in the Batch 2 re-exam STEP8-10)

### Batch 2 (fan-out)
- [x] STEP 8 fan-out engineering release (when done, re-take the Corvane A0–C1 exam per STEP 7, VERIFY STEP8-10)

### Batch 3 (common items + BOM + cost sheet)
- [x] STEP 9 Common: event dates, number registry, operating rules as a source, revision kind, pending list, engineer changing values in the conversation
- [x] STEP 10 BOM with 4 / 5 worksheets
- [x] STEP 11 Unit cost sheet with 7 / 8 worksheets and formulas
- [ ] STEP 12 Batch 3 re-exam (Kalvara automated; Corvane manual) — automated part done (2026-11-01); the Corvane re-run with `/npi` is waiting for the user; the Corvane part (STEP12-2 live run, STEP12-3) was deferred by the user on 2026-11-23, to be replaced by using v1 on a real NPI case (progress entry 77)

## Decided in advance
### What you have already decided
| Item | Decision | Source |
| --- | --- | --- |
| Batch 1 scope | The full A0–C1 flow including ECRs, every station rough first | BRIEF |
| Outputs | DFM / change-impact email, formal spec, BOM, drawing PDF, STEP, unit cost, PO check result, material-preparation / material-change notice email, all drafts | BRIEF |
| Start and gatekeeping | The engineer hands the customer document to the manager; every station stops for review, and only reviewed output goes to the next station | BRIEF |
| How it runs | Claude Code subagents; hand-over by files, replaceable later by the Claude Agent SDK | BRIEF |
| Customer decision | The engineer tells the manager at the review point | BRIEF detail #2 |
| Acceptance isolation | Kalvara for development; Corvane only used in STEP 7, and before that its our-side documents and answer files are not read | BRIEF detail #1 |
| No invented numbers | A number without a traceable source is written as `待工程師填寫` ("to be filled in by the engineer") | BRIEF |
| Batch 2 scope | The engineering-release station produces by product type: fibre array as in Batch 1, plus fan-out; a third kind of product is an error, not forced | BRIEF Batch 2 |
| fan-out key parameters | Fibre count, trunk connector type and quantity, leg connector type and quantity, trunk length and tolerance (may be asymmetric), leg length and tolerance, breakout-box outline, trunk and leg cable diameters, end face | BRIEF Batch 2 |
| Who judges the product type | The engineering-release agent judges it, citing the customer document | BRIEF Batch 2 |
| fan-out drawing and STEP | The drawing shows the trunk, breakout box, legs and port map; the STEP models the breakout box | BRIEF Batch 2 |
| Batch 2 wrap-up | When done, Corvane re-takes the exam from A0 to C1 | BRIEF Batch 2, VERIFY STEP8-10 |
| Batch 3 scope | Common items (event dates, number registry, operating rules as a source, revision kind, pending list), BOM per content-depth spec §5, unit cost sheet per §6; formal spec, drawing, emails and material preparation left for Batches 4, 5 | BRIEF Batch 3 |
| Acceptance standard and company rules | The content-depth spec is rewritten into VERIFY (not in the repo); `input/00_Factory_Master_Data/LPC作業規則.md` is read-only raw data that can be cited | BRIEF Batch 3, progress entry 38 |
| Event dates | Working days derived from the customer document date using the typical values of operating rules §2 (skipping only weekends); intervals an ECR does not give are carried over from the initial revision; the engineer can change them; email at 10:00 +0800 | BRIEF 3-1 |
| Operation times | Operations per §4; set-up time 20 minutes (middle of the §4 range 10–30); run time `待工程師填寫` | BRIEF 3-2 |
| Where event dates apply | All stations; for the other stations only the date and file name change | BRIEF 3-3 |
| BOM category | Mapped from the MM-002 Category; two exceptions: optical adhesive → raw material, protective cap → packaging | BRIEF 3-4 |
| Scrap rate | The agent picks one row by product type and cites it; a gap or several matching rows → pending with candidates listed; base = material (excluding packaging) + services + conversion + material handling + manufacturing overhead | BRIEF 3-5 |
| Engineer changing values | Said in the conversation; the tool edits the judgement file and re-renders | BRIEF 3-6 |
| How Delta is split | For each CH calculate the material, services and conversion difference and then apply the same set of overhead rates; parameter or price-break changes go on a separate "parameter change" row | BRIEF 3-7 |
| Batch 3 wrap-up | Both Kalvara and Corvane re-run from A0 to C1 | BRIEF Batch 3, VERIFY STEP 12 |

### Provisional business rules (我先暫定的; need your agreement)
| # | Item | Provisional approach | Reason |
| --- | --- | --- | --- |
| P1 | Who acts as the manager | The manager is the main conversation, following the steps of the project command `/npi`; each of the five stations is a subagent | A Claude Code subagent cannot dispatch further subagents, so a manager built as a subagent could not dispatch the stations |
| P2 | The four actions of each station | `prepare` (Python gathers the facts) → the subagent writes the judgement file → `render` (Python checks the judgement and fills templates to produce documents) → the engineer reviews → `approve` (Python reads the reviewed documents back into a structured result) | Everything except judgement is in Python and testable; when moving to the SDK only "who writes the judgement file" changes |
| P3 | Hand-over files | Each station folder `output/<case>/<revision>/<station>/` holds `facts.json`, `judgement.json`, the output documents and `reviewed.json`; the next station only reads the previous station's `reviewed.json` | VERIFY STEP6-3: it can continue from files alone |
| P4 | Where the reviewed version comes from | On `approve` the output documents are read again (eml, docx, xlsx; PDF not read, STEP not read), so numbers the engineer changed in the documents go into `reviewed.json` | VERIFY STEP0-7 |
| P5 | Status | `output/<case>/state.json` records the status of each station of each revision: `未跑` (not run) / `待審` (pending review) / `已審` (reviewed); a reviewed station cannot be `render`ed again and must be `reopen`ed first, and the downstream stations go back to not run with it | Reviewed content has been used downstream and must not be silently replaced |
| P6 | Recognising documents | Only files under `input/<NPI-xx-xxx_name>/<revision>/` are recognised, with the case, revision and document kind taken from the folder names (see table A); files elsewhere are an error | The input folder structure is fixed; within BRIEF's scope this is the least error-prone |
| P7 | Revision order | A0 → B0 → C0 → C1, fixed to these four | The input only has these four |
| P8 | Unstable judgement and "same on re-run" | Re-run = `render` again with the same `judgement.json`, and the output content must be the same; to have the subagent judge again, the engineer must say so explicitly | The text a subagent writes is different every time; VERIFY STEP6-2 can only guarantee the program part is the same |
| P9 | Dates | On each station's first `prepare` the current date is recorded (can be set with `--date`), and re-runs use this date; the email Date and document dates all use it | Re-runs must be the same |
| P10 | Sender and internal recipients | Written in `config/people.json`: sender Alex Lin (Senior NPI Engineer), SCM recipient Nina Ho. Customer-side recipients are read from the contact table of the customer document | The customer documents in input do not say who our SCM is; the names are taken from the Kalvara reference emails |
| P11 | Emails are drafts | The .eml gets `X-Unsent: 1`, so a mail client opens it as an editable draft; the tool sends no email | BRIEF: no sending |
| P12 | How our part numbers are decided | The finished-product and block part numbers are decided by the engineering-release subagent during judgement, and Python checks the format (starts with `LPC-`, no duplicates); document numbers use the digits of the NPI number, e.g. NPI-26-097 → `LPC-PS-26097` | The naming convention of input |
| P13 | Which price break is used | The price list has Base, Break 1, Break 2; use the break that "quantity per finished unit × costing order quantity (the quantity in the spec or ECR, otherwise the PO quantity)" falls into | The answer file has costing_lot; start with the most direct rule |
| P14 | How far the unit cost goes | Batch 1 only calculates "direct material" (what can be found in the price list); services, conversion, SG&A and other cost elements are listed but written as `待工程師填寫`, and the total is marked "不完整" (incomplete) | The factory master data has no labour rates; no invented numbers |
| P15 | PO check output | One Markdown document `PO_Check_<PO number>_Rev<n>.md`, generated from a template | BRIEF detail #3: an internal check result; Markdown is the easiest to edit |
| P16 | Material requirements | Requirement = BOM quantity per finished unit × PO quantity; Batch 1 adds no scrap allowance and deducts no stock, and the email states "without scrap allowance" | The hand-calculation formula of VERIFY STEP5-2; rough |
| P17 | Drawing PDF | matplotlib draws A3 landscape: front and side simplified outlines (block, lid, boot), main dimensions, channel table, title block (document number, revision, date) | Batch 1 only aims to get the flow running (BRIEF detail #4) |
| P18 | STEP | Generated with cadquery: block STEP = two boxes, substrate + lid; assembly STEP = block + boot box. Dimensions come from the formal spec | Same as above; the STEP files in input were also generated with Open CASCADE |
| P19 | Reading the PO PDF | Extract text with pdfplumber, then use rules to pick out the PO number, revision, and each line's quantity, unit price and delivery date | Pure Python, no external programs |
| P20 | Subagent model of each station | DFM / change impact and engineering release use opus; costing, PO check and supply chain use sonnet | The first two stations carry the heavy judgement; in the last three Python does most of the calculation and the agent writes a few sentences |
| P21 | Python environment | Rebuild `.venv` with Python 3.11. The old `.venv` was copied from the old project with paths pointing at it, and is moved to the Trash | System Python 3.9 is too old; the old venv is unusable |
| P22 | Testing judgement content | The automated tests use hand-written Kalvara judgement files (`tests/fixtures/`, written from the Kalvara reference documents) and do not call subagents; the parts actually run by subagents are listed as manual tests | Automated tests must be stable and cost no quota |
| P23 | Key parameters of engineering release | All 14 key parameters are required; numeric parameters must be greater than 0, and the end-face angle may be 0 | The drawing and STEP need them; C0 changes to a 0° flat end face (added after the read-only review on 2026-11-01; the user agreed to add it as it stands) |
| P24 | Parameter changes in ECR revisions | A parameter that differs from the previous revision must map to some CH of this ECR; only the existence of the CH is checked, not its relevance to the parameter | VERIFY STEP2-7; relevance relies on the engineer's review |
| P25 | Engineering-release formats | product_type may only use English letters and underscores; Make/Buy is only Make or Buy; duplicate BOM part numbers are not checked | The file name uses product_type; Kit would be skipped by costing and material preparation (issue #5) |
| P26 | The two fixed BOM rows | The program automatically adds item 0 (finished product, name = the key-parameter description) and item 10 (block, name fixed as "Fibre array block, assembled & polished"), quantity 1 | Every FAU has these two levels |
| P27 | "Not in the material master" flag | Only Buy items are flagged; Make items are made in-house and were never in the material master | Avoids the first two rows of every BOM being flagged |
| P28 | UoM in costing | When the BOM and price-list UoM differ, no conversion is done; it is written as `待工程師填寫` with a note in Remark | Avoids silently calculating wrongly |
| P29 | Unit cost total | Direct material is recalculated from the material rows; total = sum of all cost elements, complete only when everything is filled in | The total is only right after the engineer fills in the material rows |
| P30 | PO check | A part number from any reviewed revision counts as consistent (older lots may use an older revision's part number); the customer revision for A0 is the Rev in the Drawing field of the customer spec, and for an ECR the revision after the change; when unclear it writes "無法比較" (cannot compare) | Kalvara PO Rev 1 and Rev 2 have delivery lines of both old and new revisions |
| P31 | Recipients of the DFM / change-impact email | For A0 pick the customer contact whose role contains Engineering, for an ECR the Originator; other customer contacts go in CC; our people are not included | Follows how the real Kalvara emails are addressed |
| P32 | Risk level | High = cannot be done, and the customer must change the design / process / schedule; Medium = can be done or there is an alternative, but with extra cost, a new design or more inspection; Low = the number the customer wrote cannot be met but it has no effect in actual use. ECRs use Feasible / Not feasible | Carried over from the risk table of the old BRIEF |
| P33 | Whether an ECR changes the PO | When the affected-documents table has no Purchase order row, treat it as changing the PO | Better to remind too often |
| P34 | Station order and reopen | The station order is fixed as dfm → release → cost → po → supply, regardless of the order documents arrive in; reopen renames the reviewed.json and facts.json of the stations sent back to *.reopened.json (not deleted) (where they go is replaced by P100 on 2026-11-24), and table C is also checked before render | issues #2, #3 |
| P35 | Engineer edits a key parameter of the formal spec | Blocked on approve; ask them to change the spec back, or reopen and re-run | The BOM, drawing and STEP would not follow (issue #4) |
| P36 | Product type (Batch 2) | `product_type` only accepts `Fiber_Array` and `Fanout` (from the input case folder names `..._Fiber_Array`, `..._FO36_Fanout`); for other values render reports "不支援的產品類型 X" (unsupported product type X) and produces no files. The judgement file must have `product_type_sources` (A0 cites R / SPEC, an ECR cites `PREV product_type`); an ECR revision cannot change the type | VERIFY STEP8-1, 8-7; BRIEF requires citing the customer document |
| P37 | fan-out key parameters (Batch 2) | 18 of them: `fibres`, `trunk_conn_qty`, `trunk_connector`, `leg_conn_qty`, `leg_connector`, `end_face`, `polarity`, `trunk_m`, `trunk_tol_plus_mm`, `trunk_tol_minus_mm`, `leg_mm`, `leg_tol_plus_mm`, `leg_tol_minus_mm`, `trunk_od_mm`, `leg_od_mm`, `box_w_mm`, `box_l_mm`, `box_h_mm`. All are required; tolerances may be 0, other numbers must be greater than 0. Units follow the customer's wording: the trunk in m (shown to one decimal place, `3.0 m`), the others in mm | Customer R-07 says "Trunk 3.0 m + 50 / 0 mm"; converted to 3000 mm it could not be found in the source |
| P38 | Tolerance notation | The plus and minus tolerances are stored as two numbers; when equal write "± 10", when different "+50 / 0" or "+50 / -10"; the spec, BOM and drawing all use the same function, and reading back splits it into two numbers again | VERIFY STEP8-3 |
| P39 | Polarity and port map | Add a `polarity` parameter (`Method A` / `Method B`; BRIEF does not list it, but the port map needs it and customer R-03 states it). The port map has one row per fibre: fibre number, MPO number, position on the MPO, leg number. Each MPO has one group of legs; Method B follows the original text of R-03, "fibre 1 of each MPO to the last leg of its group": position 1 connects to the last leg of the group, and so on in reverse; Method A is my provisional straight-through: position p connects to leg "floor((p − 1) ÷ fibres per leg) + 1" of the group. The fibre count must be divisible by the number of trunk connectors and by the number of legs, otherwise it is an error. The leg label style (P01–, 1A–) is not a key parameter and is written in the spec text | The drawing needs a port map (BRIEF); Method B has the customer's original text, while Method A and the two-fibres-per-leg connection for duplex are my provisional choices and need your confirmation |
| P40 | The two fixed BOM rows for fan-out | item 0 name = the fan-out description (with fibre count, connectors, trunk length and tolerance); item 10 uses `block_pn`, with the name fixed as "Fan-out box sub-assembly". Fibre arrays stay as in P26 | VERIFY STEP8-4; both types keep the two levels "finished product + first-level assembly" |
| P41 | fan-out drawing | matplotlib A3 landscape, schematic and not to scale (marked "NOT TO SCALE"): trunk line and MPOs on the left, breakout-box rectangle in the middle, legs and connectors on the right; annotated with trunk length and tolerance, leg length and tolerance, breakout box W x L x H and cable diameters; port map table on the right; title block as in P17 | With a 3 m trunk and a 62 mm breakout box, the box would be invisible at scale |
| P42 | fan-out STEP | Breakout-box STEP (file name uses `block_pn`) = one W x L x H box; assembly STEP (file name uses `lpc_pn`) = breakout box + trunk cylinder + one cylinder per leg, with lengths and diameters from the parameters | BRIEF "the STEP models the breakout box"; VERIFY STEP8-6 only measures the breakout box |
| P43 | Consistency check of quantities in text | "The channel count in the text must equal channels" is only done for fibre arrays; for fan-out the fibre count in the text is not checked | Corvane text often has "12-fibre ribbon", which the same rule would misjudge |
| P44 | compare with fan-out | The key parameters of engineering release are only compared for fibre arrays; for fan-out the key parameters are not compared (the corresponding answer-file fields can only be known by reading the Corvane answer file, which is not allowed during development); other fields as before | BRIEF detail #1 |
| P45 | Corvane data for automated tests | VERIFY STEP 8 names Corvane, so the automated tests use hand-written Corvane judgement files (`tests/fixtures/corvane/`: DFM / change impact and engineering release for A0 and B0), written only from Corvane's customer documents (`01`) and the factory master data; the DFM may be adapted from the judgement file the subagent wrote in the STEP 7 exam. Corvane's `02`–`04`, `06` and answer files are still not read. The former "tests must not contain NPI-26-104" becomes "tests must not contain the file names of Corvane's our-side documents or the answer files" (TESTS STEP 0 supplementary) | The cost: the code was written against Corvane's customer documents, so the STEP8-10 re-exam can test C0, C1 and the subagents' judgement, but cannot test "a different, unseen fan-out customer" |
| P46 | Baseline for not breaking fibre arrays | After opening `batch-2` and before changing any code, run Kalvara A0–C1 with the Batch 1 code (fixture judgement files) and save each station's `reviewed.json` and the drawing PDF text as `tests/fixtures/kalvara/batch1_golden.json`; compare against it afterwards | VERIFY STEP8-9 "same as Batch 1" needs something to compare with |
| P47 | Old output before the re-exam | Rename the `output/NPI-26-104/` left by the STEP 7 exam to `output/NPI-26-104_exam1/` (not deleted), and run the re-exam from A0 again | The old A0 engineering-release judgement file was written when fan-out was not supported |
| P48 | Comparison baseline for Batch 3 (Batch 3) | After opening `batch-3` and before changing any code, run Kalvara A0–C1 with the Batch 2 code (fixtures) and save it as `tests/fixtures/kalvara/batch2_golden.json`. STEP 12 and the rewritten STEP8-9 compare against it, excluding the fields this batch deliberately changes (table K) | VERIFY STEP12-1 excludes STEP8-9; something is needed to prove "nothing changed apart from the deliberate changes" |
| P49 | Timeline (Batch 3) | One `output/<NPI>/<revision>/timeline.json` per revision: one entry per event (date, basis, whether derived or specified by the engineer). The derivation is a pure function per table F; working days skip only Saturdays and Sundays (there is no public-holiday data). A date specified by the engineer has the basis "工程師指定" (specified by the engineer); specifying a Saturday or Sunday is an error asking for another day | BRIEF 3-1; VERIFY STEP9-4 says "any day on the timeline" is not a weekend |
| P50 | Receipt dates | "Draft spec / ECR / PO received" = the date on that customer document (the `date` already read by the spec and ECR readers, and the PO reader's date). Only POs already `intake`n are used (recorded in `state.json`); until one is handed in it is derived per table F, and once the PO is handed in, stations not yet `prepare`d derive forward from the PO date instead | Customer documents have no receipt date; documents not yet handed in must not be read |
| P51 | Days for which the operating rules have no single typical value | Quote "1–2 days" takes 1; ECR impact assessment "2–3 days" takes 2; "spec release → cost to finance" for a major ECR is not given in §2, so the initial revision's "spec release → customer acceptance → cost to finance", 2 days in total, is used; for a minor change the cost-to-finance date and the material-preparation notice date are both the day after the spec release date (§2 minor change: "spec release and material-preparation notice may be on the same day or the next day", and costing comes before material preparation, so the same day). The basis states the range and the chosen value | BRIEF 3-1 only fixed "typical values"; taking the smaller one makes the schedule early, which is easier for the engineer to push later; deriving a minor change like the initial revision would put the material-preparation notice before cost to finance (read-only review) |
| P52 | Date of each station | Replaces P9: on `prepare` the date of this station's event is taken from the timeline (last column of table F) and recorded as this station's `date` in `state.json`, unchanged on later re-runs. `--date` is kept, with its meaning changed to "the engineer specifies this station's event date" (also written into the timeline); the old tests' `--date 2026-11-01` is a Sunday and would be blocked by P49, so it becomes `2026-11-02` (see "Old tests changed" in TESTS) | Same on re-run (P8); the date of a reviewed document is not affected by later changes (VERIFY STEP9-5) |
| P53 | Email time | Date fixed at 10:00 +0800 (formerly 09:00) | BRIEF 3-1 |
| P54 | Revision kind | A0 is automatically "initial". For ECR revisions the change-impact agent writes `revision_kind` (`major` / `minor`) in the judgement file and cites the ECR; check: judged major although the ECR says No PO revision, or judged minor without it → error. It is stored in the change-impact `reviewed.json`, and engineering release, costing and the timeline all read it from there | BRIEF common 4; the change-impact station is the first to read the ECR |
| P55 | Number registry | `output/registry.json`, each entry: number, kind (product_pn / lpc_po / quote), source, date, which NPI / revision uses it. Used numbers are collected from the master data and from customer documents already `intake`n (table G); the numbers in a customer document are only added when that document is `intake`n, and revision folders not yet handed in are not scanned. Engineering-release check: the suffix letter of the finished-product part number must differ from the previous revision; it must not be registered by another NPI / revision, nor be among the MM-002 part numbers or the LPC P/Ns of LL-003. It is registered only when render succeeds; re-running the same NPI / revision overwrites its own entry and adds none | BRIEF common 2; the part number is proposed by the agent (P12) and checked by the program; VERIFY STEP9-8 |
| P56 | Date filter of the registry | The duplicate check only looks at numbers "dated no later than this revision's receipt date"; master-data numbers without a date (MM-002 part numbers) always count as used | So that A0 does not see numbers that only appear at B0 (VERIFY STEP9-10) |
| P57 | Reading the operating rules | `readers/rules.py` splits `LPC作業規則.md` into sources, each holding a single value: a table row holding two sets (work-station rates) is split into two; sub-items of a bullet separated by "，" or "；" get one each. Source names are `RULES §<section> <table or entry name> <row name>`, e.g. `RULES §3 工作站費率 FPR`, `RULES §3 報廢率 扇出線`, `RULES §3 成本批量 PM 陣列`. Fixed values such as rates and ratios are read directly by the program, and the agent does not write them | BRIEF common 3; the lessons of issues #17, #20; VERIFY STEP9-11, 9-12 |
| P58 | Check of range values | When the cited source is a range (`500–1,500`, `10–30`), the value must fall within the range (ends included), and the number is not required to appear in the original text; outside the range is an error that prints the range | Table D only looks for "the same number", and a value chosen from a range would not be found |
| P59 | Pending list | `pending_items(files)`: scans the xlsx (worksheet, cell), docx (which section or which table) and eml (which line) this station produced for `待工程師填寫` and returns a list of locations; `render` prints it, and the manager reports from the printed list | BRIEF common 5; previously the manager counted with grep, giving a count without locations |
| P60 | Engineer changing values in the conversation | New command `tell <NPI> <revision> <station> "<the engineer's own words>"`: the words are stored in the station folder's `engineer.json`, numbered `ENG-1`, `ENG-2`…; on `render` they are added to the sources. The manager edits that cell of `judgement.json` according to the words, citing `ENG-n`, and then runs `render`. Only usable while this station is `未跑` or `待審` | BRIEF 3-6; numbers given by the engineer must also be traceable to a source |
| P61 | BOM levels and quantities | The item number decides the level: `0` is level 0, one without a dot (`10`) is level 1, one with one dot (`10.10`) is level 2, and more dots are an error. `qty_per` in the judgement file becomes "quantity per parent"; extended quantity = quantity × the parent's extended quantity, written as a formula in the xlsx. Column names do not say FAU: `Qty per Parent`, `Ext. Qty per pc`. Costing and material preparation both switch to the extended quantity | VERIFY STEP10-2, 10-4, 12-2; the parent of a level-2 item must be in the BOM, otherwise it is an error (the existing Kalvara fixtures lack item 60, and B0–C1 lack item 20; added in step 1 of STEP 10, see P82) |
| P62 | BOM category | Per table H; written with the Type codes of the Kalvara reference BOM (MFG, RM, BUY, PKG, CON). For bought items that are "New (ECR / NPI) material code" in MM-002 or not in MM-002, the agent writes the category and cites a source; if it cannot, `待工程師填寫` | BRIEF 3-4; the reference BOM uses these five codes |
| P63 | Routing | The agent writes `routing` in the engineering-release judgement file: for each operation the operation number, description, work station, set-up time, run time and source; each operation gets `kinds` (`base`, `pm`, `prebake`, `coating`, `incoming`; one operation may have several, e.g. outsourced coating and incoming inspection written in the same `SUB` operation); plus `routing_adds` (`PM`, `coating`, each citing a source). check: (1) the basic operations of operating rules §4 for the product type are all present in order (compares the work-station order of the `base` operations); (2) with `PM` there must be two `pm` operations (work station PMA); with `coating` all three of `prebake`, `coating` and `incoming` must be present; (3) the work station must be in the §3 rate table, with outsourced operations written as `SUB`; (4) the set-up time is 20 minutes (BRIEF 3-2), citing `RULES §4 整備時間`; when the engineer gives another value with `tell`, it cites `ENG-n` and per P58 must fall within 10–30; (5) the run time must have a source (usually `ENG-n`) or be `待工程師填寫`. The lot qualification of §4 (REL, charged separately) does not go in the Routing and is counted under Services | BRIEF 3-2; VERIFY STEP10-6, 10-7; §4 does not say where the PM and coating operations are inserted, so the agent sequences them and the program only checks presence and the basic order |
| P64 | BOM to operation mapping | Except for level 0, every row of the judgement file gets an `op` (e.g. `30` or `30-70`), and the program writes "Op 30" at the front of the remark; check: the operation number must be in the Routing | VERIFY STEP10-2, 10-8 |
| P65 | Channel Map | Fibre array: `channel_map` in the judgement file has one row per channel (channel number, function, fibre type; `待工程師填寫` when not found), and the program adds the computed columns: V-groove number, MPO number, position on the MPO (fibres per MPO taken from the connector notation `MPO-12` / `MPO-16`), nominal core position = (channel number − 1) × pitch. Fan-out uses the port map of P39. Check-cell formula: row count = channel count (fibre count for fan-out) shows OK, otherwise CHECK; check does not block (the engineer should see CHECK in the xlsx) | VERIFY STEP10-5 "delete one row in the judgement file" must show CHECK, so the rows must come from the judgement file |
| P66 | Change Summary | From B0 onwards: the BOM difference compares all rows (including Make rows, e.g. `LPC-FA24-110 → LPC-FA32-110`; the supply chain's `bom_changes` only compares bought items and cannot be reused directly), listing additions, cancellations and quantity changes; plus the Routing difference (operations added, removed or changed in time). `change_map` in the judgement file maps each item to a CH, and a missing one is an error (same as P24) | VERIFY STEP10-9; the reference B0 Change Summary lists make items |
| P67 | Revision | One row per revision: revision, date (that revision's spec release date), zone ("—" for A0, the CH numbers for an ECR), description ("Initial release" for A0; "<ECR number> <CH list>" for an ECR), prepared by Alex Lin, approved by Jessica Liao (operating rules §1). The rows of earlier revisions are carried over from the previous revision's engineering-release `reviewed.json` | VERIFY STEP10-10 |
| P68 | Where people's names come from | Prepared by and approved by on the BOM and cost sheet are read from operating rules §1. The sender and recipients of emails still use `config/people.json` in this batch (emails are left for Batch 5); the names in the two places must be the same, and a test is added to compare them | The same thing is written in one place only, but changing emails is outside this batch's scope |
| P69 | Cost sheet layout | The template follows the worksheet order and columns of the Kalvara reference cost sheet (Summary, Delta vs <previous revision>, Parameters, Material, Services, Conversion, Rates, Approval); the layout is in `templates/unit_cost.xlsx` and the formulas are written by the program (each row's formula has to follow the number of data rows) | Operating rules §8; the formulas are generated by row count and cannot go in a fixed template |
| P70 | Pending cells in formulas | A pending input cell is left empty and the status column beside it says `待工程師填寫`; each row's formula is written as "blank if the input is empty"; Summary counts pending cells with COUNTBLANK, and while any are pending the total cost and quote cells show "不完整" (incomplete) instead of a number. Recalculation produces no error values | VERIFY STEP11-2, 11-3; text put into a formula would become #VALUE! |
| P71 | Cost calculation order | Per table I; the program has a pure function that computes the same numbers (for approve, the PO check, and for tests to compare with the formulas) | VERIFY STEP11-2 "the total equals the value computed by the program" |
| P72 | What the costing agent decides | `costing_qty` (P13 unchanged), `lot_size` (cost lot size: cites a sub-item of the §3 cost lot size per P58, or cites the PO quantity per lot), `target_price` (A0 cites the customer document; the customer document of an ECR has no target price, so it is compared with the previous revision's quote instead, citing the new source `PREV quote`, which extends row 5 of table D; agreed by the user on 2026-11-01), `scrap_rate_override` (may only be written when table J judges it pending: the value must be one of the candidate rows, citing that row, or cite `ENG-n`), `services` (outsourced services other than lot qualification, e.g. coating; must cite a source), `nre`, `ecr_nre`. The fixed rates (3 %, 22 %, 8 %, 30 %, USD 0.50, work-station rates) are read directly from §3 by the program; the scrap rate is judged by the program per table J and the agent does not write it (BRIEF 3-5 says "the agent picks a row", but all the conditions can be computed from the parameters and operations, and the program is less likely to pick wrongly; agreed by the user on 2026-11-01) | Only what needs judgement is given to the agent |
| P73 | Services | For fibre arrays the program automatically adds `SV-REL-LOT`, per piece = price per lot ÷ cost lot size; not added for fan-out (§3). For services priced per piece (`SV-ARC-1310`), per piece = max(unit price × cost lot size, minimum charge) ÷ cost lot size | The price list notes "Minimum charge applies per purchase order / batch" |
| P74 | Conversion | Only internal operations with a rate are counted; `SUB` outsourced operations are not conversion (the money is under Services). Rates come from the §3 table (§3 says "the master data prevails", but the master data has no rates) | VERIFY STEP11-8, 11-9 |
| P75 | NRE | A0 must have four rows: fixtures, test set-up, first article inspection, one-time design qualification; each amount has a source or is `待工程師填寫`, and those not needed say "Not required" with a source cited. ECR revisions additionally have at least one ECR NRE row (the amount may be pending) | Content-depth spec §6, operating rules §3; VERIFY STEP11-12 |
| P76 | Quote and comparison | Quote = total cost ÷ (1 − 30 %), rounded up to 0.50. A0 is compared with the customer's target price; a major change with the previous revision's quote; for a minor change the quote = the previous revision's quote (carried over), and Summary and Delta give the margins of both revisions | Operating rules §3, §5 "a minor change is not re-quoted"; VERIFY STEP11-14 |
| P77 | Approval | Prepared: Alex Lin (the NPI owner in operating rules §1; §1 does not say who prepares the cost sheet, so he is used provisionally) + the cost-to-finance date; Reviewed, Finance confirmed: "待確認" (to be confirmed) | BRIEF: no finance confirmation; no invented sign-offs |
| P78 | Reading the cost sheet back | openpyxl cannot read the calculated results of an xlsx with formulas, so `approve` only reads the input cells (Parameters, the quantities and unit prices of Material, Services, the times of Conversion) and recalculates with the pure function of P71; `total`, `complete` and `quote` in `reviewed.json` come from the recalculation, and the PO check uses them as before | The engineer now changes values via P60; reading back is mainly a guard against someone editing the xlsx directly |
| P79 | Formula recalculation tool | The automated tests use `pycel` (installed into `.venv`, written into requirements.txt) to recalculate the xlsx, checking that there are no error values and that the total equals the value of P71. Step 1 of STEP 11 first confirms that pycel can calculate the functions used (IF, SUM, SUMIF, COUNTBLANK, CEILING, ROUND, COUNTA); if it cannot, stop and ask | This Mac has neither Excel nor LibreOffice; opening it in Numbers to look is a manual test |
| P80 | Corvane data for automated tests (Batch 3) | P45 as before: based only on Corvane's customer documents and the factory master data, the Routing, category and costing judgement fields are added in `tests/fixtures/corvane/A0` and `B0`; the Corvane re-run of STEP 12 is manual | VERIFY STEP 12 names Corvane; the fan-out operations, scrap rate and absence of lot qualification need automated tests |
| P82 | Parent of level-2 items (group rows) | Items 50 and 60 of the reference BOM are "Kit", but Kit is blocked by issue #5. Group rows are always written as Make (costing and material preparation only count Buy, so nothing is double counted), the part number is proposed by the agent (e.g. `LPC-FA24-PKG`), and the category follows row 1 of table H. Fixtures added: Kalvara A0 item 60, and item 20 for B0–C1 (present in the previous revision, omitted in this one) | P61 needs a parent; issue #5 is not relaxed |
| P83 | Engineer input for tests | `tests/fixtures/<case>/<revision>/engineer.json` is what it looks like "after tell has been run" (run times, scrap-rate override); the default fixtures do not carry it and the output is pending; tests that exercise the full calculation first copy it into the station folder | VERIFY STEP10-6 needs to see pending values, while STEP 11 needs complete numbers; both must be tested |
| P81 | How Delta is calculated | First calculate "parameter change" = one calculation using the previous revision's materials, services and operations with this revision's parameters (cost lot size, scrap rate, price breaks), minus the previous revision; then assign each material row, service row and operation row that differs to a CH according to the engineering-release `change_map` (P66), applying this revision's rates (rows 4–9 of table I) to each CH's direct difference. The sum of the rows = the total difference (with fixed parameters the rates are linear, so it matches exactly); the check cell compares the sum with the total difference | BRIEF 3-7; VERIFY STEP11-13 |
| P84 | New source: the previous revision's routing additions (Batch 3, agreed by the user on 2026-11-02) | An ECR revision that keeps the previous revision's PM or coating cites `PREV routing_adds PM`, `PREV routing_adds coating` | Same kind as `PREV product_type` and `PREV quote`; extends row 5 of table D |
| P85 | New source: a single upstream row of this revision (agreed by the user on 2026-11-02) | The costing station may cite one operation of the engineering-release Routing, `ROUTING <op>` (an outsourced service must say which operation), or one lot of the PO, `PO line <n>` (the cost lot size may cite it) | One source per row, not the whole document (the principle of issue #17) |
| P86 | Quantity of group rows (agreed by the user on 2026-11-02) | The quantity of a group row (Make, with level-2 items under it) is always 1, and the program does not check the source of this 1 | A group row only bundles the items under it; table D would otherwise require a source |
| P87 | What Change Summary compares (agreed by the user on 2026-11-02) | The finished-product part number (item 0) changes with every revision (operating rules §7) and is not a change item; all other rows are compared, including item 10 and group rows; quantities and times are only compared when both sides are numbers, and a change between pending and a number does not count (issue #39) | Change items must map to a CH, and these two cases map to none |
| P88 | Operation of item 10 (agreed by the user on 2026-11-02) | The program takes the range from the operations of the level-2 items under item 10, e.g. `Op 10-30` | Item 10 is a row the program adds automatically, and the judgement file has no op for it |
| P89 | Comparison price for ECR revisions (agreed by the user on 2026-11-02) | The program automatically takes the previous revision's quote (`PREV quote`); the agent only writes the customer's target price for A0 | An ECR has no customer target price; P72 originally said the agent cites it |
| P90 | Delta difference that cannot be attributed to a CH (agreed by the user on 2026-11-02) | Listed on a separate row "其他（未對應 CH）" (other, not mapped to a CH), with the basis "差額沒有對到任何 CH" (the difference maps to no CH) | The sum still equals the total difference; nothing is forced into a CH (VERIFY STEP11-13) |
| P91 | Engineer input for tests (agreed by the user on 2026-11-02) | Replaces the original text of P83: tests first run `tell` the way an engineer would and the judgement file cites `ENG-n`; no separate `engineer.json` fixture is stored | Same as the real flow; one fewer file to maintain |
| P92 | Functions used for formula recalculation (agreed by the user on 2026-11-02) | pycel does not support COUNTA or COUNTBLANK, so COUNTIF(range,"<>") and COUNTIF(range,"") are used instead; P79 originally said "if it cannot, stop and ask", and I switched to equivalent functions without asking first | Excel and pycel both give the same result |
| P93 | Order of the timeline (agreed by the user on 2026-11-02) | A date specified by the engineer, or one already produced, must not be earlier than the previous fixed date (customer document, specified, already produced); if it is, that is an error; a derived date in between that is later than a following fixed date is moved earlier to the same day, with the reason written (issue #32) | VERIFY STEP9-4; derived dates are only estimates and must not block a date the engineer specifies |
| P94 | When a specified date is blocked | The timeline is restored to what it was, leaving no wrong specification behind | Same on re-run (P8) |
| P95 | Quotation numbers are also collected from the customer PO (decided by the user on 2026-11-02) | On `intake` of a customer PO, the `LPC-Q-… dated …` on the PO is registered; with only the A0 draft spec handed in, the registry still does not have `LPC-Q-26-0391` (VERIFY STEP9-10) | BRIEF common 2 "everything visible in customer documents is registered"; Kalvara's A0 PO already has this number |
| P96 | DFM: direction or position without a reference (decided by Claude on the user's delegation, 2026-11-24) | A requirement that places fibres or connector positions by upper / lower row, left / right or "channel 1 at …" without saying from which side it is viewed or where the connector key is, is listed even when we can do it: risk Medium, the proposal states the reference we will use for the customer to confirm | NPI-26-124 R-08 was missed; the answer raised it (progress entries 82, 86) |
| P97 | Costing lot for a general fibre array (decided by Claude on the user's delegation, 2026-11-24) | Always 500, the lower bound of RULES §3 "一般 500–1,500", regardless of the PO lot quantities; PM and coating rows as before | Both answers use 500 (Kalvara A0–C1 with PO lots 100–2,000, NPI-26-124 with lots 400 / 600); the lower bound gives the higher, safer per-piece cost |
| P98 | Scrap rate for 17–31 channels (decided by Claude on the user's delegation, 2026-11-24) | No rule added: table J keeps leaving it to the engineer with the candidate rows | The answers disagree: Kalvara A0 (24 ch) implies 9 %, NPI-26-124 (24 ch) implies 10 %; a fixed value would contradict one of them |
| P99 | First suffix letter of a new product number (decided by Claude on the user's delegation, 2026-11-24) | Unchanged: the next free letter in the registry (RULES §7 only requires a new letter per revision and a registry check) | The answer's `-8T` / `FA24T` cannot be derived from RULES; the current numbers are unique and registered |
| P100 | Where reopen puts the old results (agreed by the user 2026-11-24; replaces the "rename to *.reopened.json" part of P34) | `reopen` moves everything in the folder of each station sent back (`reviewed.json`, `facts.json`, `judgement.json`, the rendered documents, any subfolder), except `engineer.json`, into `output/<NPI>/<revision>/_reopened/<station>_<n>/` (n = 1, 2, … per reopen of that station; nothing deleted, nothing overwritten; no folder when there is nothing to move); the station folder keeps only the engineer's words, which a re-run may still cite as `ENG-n` (scope decided by the user on 2026-11-24, issue #60) | Issue #48: the costing agent read `*.reopened.json` in its own folder and reported a wrong part number; the agent instruction already says "only read facts.json", so the fix is structural (the old file is not where the agent looks), not one more line of instruction. Also: today a second reopen of the same station overwrites the first `*.reopened.json` |

### Implementation choices (我自己定的; no review needed, tell me if you want a change)
From 2026-11-22, things where a wrong choice would not change the content or numbers of the output documents are written here without stopping for agreement; when unsure, treat it as a business rule and write it in the table above. P1–P95 have all been agreed already and are not moved.
| # | Item | Approach | Why it does not affect the output |
| --- | --- | --- | --- |
| S1 | linter | ruff 0.17.6; `ruff.toml` only enables F (pyflakes), E9 (syntax errors) and B (bugbear), with no formatting or import sorting; B905 (zip without strict) is not enabled for now | Only catches bugs and does not reformat; adding B905 would change behaviour when lengths differ, recorded under "Later" (之後再做) in progress |
| S2 | Architecture check | `check_architecture.py` checks the layering of "File structure": pure-function modules (errors, sources, params, costing, timeline, intake) do not read or write files and do not import I/O libraries or non-pure modules; file reads and writes of state and registry are only in load, save and the path functions; readers do not import downstream, and render does not import readers / stations / pipeline. The 2 violations that existed when it was written are listed in KNOWN and may only decrease; pre-commit blocks KNOWN from growing | Only reads the syntax tree and changes no code; params was not previously stated to be pure but now is, and is guarded together |
| S3 | Quality scorecard | `check_quality.py`: regenerates the two cases into a temporary folder from the judgement files in `tests/fixtures` (all accepted, dates from the timeline, pending values not filled), measures the six items of content-depth spec §9 plus the number of pending items per station, and prints a table; it can also measure an existing output folder directly. It only reports: it does not block commits, is not in pre-commit and is not a pytest test. How many headings and tables an email should have (`EMAIL_ITEMS`) was counted from the items listed in content-depth spec §1, §2, §8; confidentiality only compares numbers, and lines that hit need a human to look | Only reads the tool's output and the factory master data, changing neither `npi/` nor any output; the standard numbers only affect the ✓✗ on this table |
| S4 | How the live smoke run opens a clean session | From the command line with `claude -p … --output-format json`, continuing with `--resume <session_id>` for the next line; only Bash, Read, Write, Edit, Agent, Task, Glob and Grep are allowed. Before the run, the case's old output in `output/` is renamed. The reply, `status` and seconds of each step are saved to files as evidence (TESTS.md "live-run script") | It only changes who types `/npi`; it changes neither `npi/` nor any decision; the output goes down the same path as when the user types `/npi` |
| S5 | Correction log (2026-11-24) | progress.md gets a "Corrections" table: one row per kind of mistake the user or a review corrected that is not filed as an issue (by the developing Claude or by a station agent); one date per occurrence (each comma-separated item one real YYYY-MM-DD date); the column "Became which check" names in backticks a top-level `test_…` function under `tests/`, or a `check_*.py` / `ruff.toml` inside the project, and it must exist; or starts with `文字規則：` (text rule), names in backticks an existing file where the rule is written, and says why it cannot be a check. The table needs its header and separator line. `check_corrections.py` reads the table per its rule table; pre-commit runs it. A row with 2 or more dates and an empty check column blocks the commit | Only reads progress.md and the names of tests and check files; changes no output |
| S6 | Mutation-testing tool (2026-11-24) | `check_mutations.py` + `mutations.json` (id, file, exact text to find, replacement, test files to run). For each mutation: the text must occur exactly once (otherwise error, file untouched); the file must be inside the project and not under `input/`; the listed tests must pass on the unchanged code first (once per set of tests), otherwise error; apply, run the listed tests (pytest `-x`, without the cache plugin, with `PYTHONDONTWRITEBYTECODE=1` so no bytecode of the mutated source is left, and always deselecting `test_S6_repo_mutations_resolve`, which checks the data and would fail on any mutation of a listed text), restore the original bytes in `finally` and verify they are identical; pytest exit code 1 = caught, 0 = not caught, any other = error (issues #49, #55–#57). Seeded with the 6 mutations of progress entry 67. Replaces the scratchpad script that was rewritten each time | Only changes a file for the length of one test run and restores it; the tool and its data are not part of `npi/` |

## Decision tables (compared in order; the first matching row is used)

### Table A: recognising documents (`intake`)
| Order | Condition | Result |
| --- | --- | --- |
| 1 | The file is not under `input/<NPI-xx-xxx_*>/<A0/B0/C0/C1>/` | Error: file name + "不在案子的版次資料夾裡" (not in a case's revision folder) |
| 2 | In `01_Customer_Draft_Spec/`, extension docx, revision A0 | Customer draft spec |
| 3 | In `01_Customer_ECR/`, extension docx, revision not A0 | ECR |
| 4 | In `05_Customer_PO/`, extension pdf | Customer PO |
| 5 | Anything else (e.g. `02`–`04`, `06`, `_ground_truth.json`) | Error: file name + "這是我方文件或答案檔，不是客戶文件" (this is our document or an answer file, not a customer document) |

### Table B: scheduling
| Order | Received | Stations scheduled (in order) |
| --- | --- | --- |
| 1 | Draft spec (A0) | DFM → engineering release → costing |
| 2 | ECR, and this revision has `05_Customer_PO/` | Change impact → engineering release → costing |
| 3 | ECR, and this revision has no `05_Customer_PO/` (C1) | Change impact → engineering release → costing → supply chain |
| 4 | PO | PO check → supply chain |

### Table C: whether a station may start (checked before `prepare`)
| Order | Condition | Result |
| --- | --- | --- |
| 1 | An ECR is received and any station of the previous revision is not `已審` (reviewed) | Error: which station of the previous revision, and its current status |
| 2 | A station before this one is not `已審` | Error: which station is not yet reviewed |
| 3 | Engineering-release station, but there is no `decisions.json` | Error: ask the engineer for the customer's decision (each R / CH accepted or not) |
| 4 | PO check station, but this revision's costing station is not `已審` | Error: the costing station is not yet reviewed |
| 5 | This station is already `已審` | Error: `reopen` first |
| 6 | Otherwise | May run |

### Table D: no invented numbers (the judgement file is checked before `render`)
| Order | Case | Result |
| --- | --- | --- |
| 1 | "Codes" in the text: starting with §; an upper-case letter start followed by a hyphen or dot (`LPC-QM-021`, `R-03`, `MPO-12`, `G.657.A2`, `DR-13`, `R6.3`); or 1–3 letters plus 1–2 digits (`A0`, `X1`, `CH1`, `P01`). Tightening approved by the user on 2026-11-01: numbers inside other words starting with a letter (`USD5000`, `x500`, `交期12週`, `Approx.15`) are checked | Not counted as numbers and not checked; but QM-021 sections, LL-003 entries and R / OP / CH numbers mentioned in the text must exist in facts, otherwise it is an error |
| 2 | `待工程師填寫` | Pass |
| 3 | Every other number (including both ends of a range, e.g. the 3 and 9 of `3-9 weeks`; thousands separators, `2,000` = `2000`) | Must appear in the original facts text cited by this piece of text; if not found, error: which field, which number |
| 4 | There is a number but this piece of text cites no facts | Error |
| 5 | Citing the previous revision (approved by the user on 2026-11-01) | May only cite a single parameter (`PREV <parameter name>`), a single BOM row (`PREV BOM <part number>`) or the previous revision's costing order quantity (`PREV costing_qty`); citing the whole JSON is not allowed |
| 6 | No source can be found for a place that should have a number (decided by the user on 2026-11-01) | Must be written as `待工程師填寫`, and must not be rewritten as a sentence without a number (e.g. not yet quoted); this is written in the agent instructions and not checked by the program |

### Table E: output file names (following the input naming)
| Station | File name |
| --- | --- |
| DFM (A0) | `<date>_DFM_Feedback_<customer spec number>.eml` |
| Change impact | `<date>_ECR-<nn>_Impact_Assessment_<NPI number>.eml` |
| Engineering release | `LPC-PS-<nnnnn>_Rev<revision>_Product_Specification.docx`, `LPC-BOM-<nnnnn>_Rev<revision>_BOM.xlsx`, `LPC-DWG-<nnnnn>_Rev<revision>_<product category>_Drawing.pdf`, `<block part number>_Rev<revision>.step`, `<finished-product part number>_Rev<revision>.step` |
| Costing | `LPC-UC-<nnnnn>_Rev<revision>_Unit_Cost.xlsx` |
| PO check | `PO_Check_<PO number>_Rev<n>.md` |
| Supply chain | A0: `<date>_Material_Preparation_<NPI number>.eml`; others: `<date>_Material_Change_Notice_<NPI number>.eml` |

From Batch 3, `<date>` in table E is this station's event date on the timeline (P52).

### Table F: timeline (Batch 3, P49–P52; working days)
Initial revision (A0):
| Order | Event | Date | Basis | Used by which station |
| --- | --- | --- | --- | --- |
| 1 | Draft spec received | The date on the draft spec | Customer document (P50) | — |
| 2 | DFM reply date | 1 + 3 | §2 "draft spec received → DFM reply" typical value | DFM |
| 3 | Customer agreement | 2 + 4 | §2 "DFM → customer agreement" | — |
| 4 | Spec release date | 3 + 5 | §2 "customer agreement → formal spec release" | Engineering release |
| 5 | Customer acceptance | 4 + 1 | §2 "spec release → customer acceptance" | — |
| 6 | Cost-to-finance date | 5 + 1 | §2 "customer acceptance → cost to finance" | Costing |
| 7 | Finance confirmation | 6 + 1 | §2 | — |
| 8 | Quote | 7 + 1 | §2 "1–2 days" takes 1 (P51) | — |
| 9 | PO received | PO already handed in: the date on the PO; not yet: 8 + 3 | Customer document (P50); or §2 "quote → customer PO" | PO check |
| 10 | Material-preparation notice date | 9 + 1 | §2 "PO received → material-preparation notice" | Supply chain |

ECR revisions (B0–C1):
| Order | Event | Date | Basis | Used by which station |
| --- | --- | --- | --- | --- |
| 1 | ECR received | The date on the ECR | Customer document (P50) | — |
| 2 | Impact assessment date | 1 + 2 | §2 ECR "2–3 days" takes 2 (P51) | Change impact |
| 3 | Customer approval | 2 + 4 | Carried over from the initial revision's "DFM → customer agreement" | — |
| 4 | Spec release date | 3 + 5 | Carried over from the initial revision's "customer agreement → formal spec release" | Engineering release |
| 5 | Major change: cost-to-finance date | 4 + 2 | Carried over from the initial revision's "spec release → customer acceptance" 1 + "customer acceptance → cost to finance" 1 (P51) | Costing |
| 5 | Minor change: cost-to-finance date | 4 + 1 | §2 minor change, the day after spec release (P51) | Costing |
| 6 | Major change: PO change order received | With a PO: the date on the PO; without: 5 + 1 + 1 + 3 | Customer document; or carried over from the initial revision's finance confirmation, quote and customer PO | PO check |
| 7 | Major change: material-preparation notice date | 6 + 1 | Carried over from the initial revision's "PO received → material-preparation notice" | Supply chain |
| 7 | Minor change: material-preparation notice date | 4 + 1 | §2 minor change "same day or next day" takes the next day, the same day as the cost-to-finance date (P51) | Supply chain |

The engineer specifies the date of an event → the specified date is used, and later events are derived forward from it; stations already `prepare`d are not changed (P52).

### Table G: initial numbers of the registry (Batch 3, P55, P56)
| Order | Collected from | Kind | Date |
| --- | --- | --- | --- |
| 1 | `PO-L26-nnnn` in the Last PO / Quote Reference of PL "Material Prices" | lpc_po | The date in brackets |
| 2 | The LPC P/N of LL-003 "Products" | product_pn | NPI Start |
| 3 | The part numbers of MM-002 | product_pn (only for the duplicate check) | No date; always counts as used |
| 4 | `LPC-Q-…` in customer ECRs and customer POs already `intake`n (including `-R1`, `-R2`; the PO was added by the user's decision on 2026-11-02, P95) | quote | The dated date written after it |
| 5 | Finished-product part numbers registered by the tool itself | product_pn | That revision's spec release date |

### Table H: BOM category (Batch 3, P62; BRIEF 3-4)
| Order | Condition | Category |
| --- | --- | --- |
| 1 | Make, and a group row (P82: the level-2 items under it are all of the same category, e.g. a packaging group or a consumables group) | The category underneath (PKG, CON) |
| 1a | Other Make | MFG (make) |
| 2 | The MM-002 Category is "Consumable - Optical Epoxy" | RM (raw material; exception) |
| 3 | The MM-002 Category is "Purchased Part - Protection" | PKG (packaging; exception) |
| 4 | Category starts with "Raw Material" | RM (raw material) |
| 5 | Category starts with "Purchased Part" | BUY (purchased part) |
| 6 | Category is "Packaging" | PKG (packaging) |
| 7 | Category starts with "Consumable" | CON (consumable) |
| 8 | Anything else ("New (ECR / NPI) material code", not in MM-002) | The agent writes it and cites a source; if it cannot, `待工程師填寫` |

### Table I: cost calculation order (Batch 3, P71; operating rules §3, BRIEF 3-5)
| Order | Item | Calculation |
| --- | --- | --- |
| 1 | Material M | Σ extended quantity × the price break taken for the pricing quantity (bought items); the part with category PKG is recorded as M_pkg |
| 2 | Services S | Σ service amount per piece (P73) |
| 3 | Conversion C | Σ (set-up minutes ÷ cost lot size + run minutes) ÷ 60 × rate (P74) |
| 4 | Material handling H | (M + S) × 3 % |
| 5 | Manufacturing overhead O | C × 22 % |
| 6 | Scrap X | (M − M_pkg + S + C + (M − M_pkg + S) × material handling rate + O) × scrap rate: neither packaging nor the material handling on packaging counts towards scrap (decided by the user on 2026-11-02, so that VERIFY STEP11-11 "change a packaging unit price and scrap does not change" holds) |
| 7 | Manufacturing cost MC | M + S + C + H + O + X |
| 8 | SG&A G | MC × 8 % |
| 9 | Total cost T | MC + G |
| 10 | Quote Q | T ÷ (1 − 30 %), rounded up to 0.50 (a minor change carries over the previous revision's, P76) |
| 11 | Margin | (Q − T) ÷ Q |
Any pending input → T, Q and the margin are all "不完整" (incomplete) (P70). NRE is listed separately and does not go into T.

### Table J: scrap rate (Batch 3; BRIEF 3-5)
The program finds the matching row from the product type, the channel count and the engineering-release `routing_adds`; the agent does not write it (stricter than BRIEF 3-5 "the agent picks a row", see P72).
| Order | Condition | Result |
| --- | --- | --- |
| 1 | fan-out | `RULES §3 報廢率 扇出線` |
| 2 | Fibre array: first see whether each row matches — "一般光纖陣列（≤ 16 通道）" (general fibre array, ≤ 16 channels) = ≤ 16 channels and no PM; "32–48 通道陣列" (32–48 channel array) = 32–48 channels; "PM 陣列" (PM array) = has PM; "PM 陣列，端面在空氣中或有鍍膜" (PM array, end face in air or coated) = has PM (the program cannot tell whether the end face is in air, so with PM both rows count as matching). Exactly one row matches | That row |
| 3 | Fibre array where no row matches (e.g. 24 channels without PM) or several match (e.g. 32 channels with PM) | `待工程師填寫`, with the candidate rows listed in the basis column of Parameters |
| 4 | Pending per row 3, and the costing judgement file has `scrap_rate_override` (P72) | The override value is used, with the cited row or `ENG-n` as the basis |

### Table K: exclusions from the Batch 3 comparison baseline (P48)
Only keys present in `batch2_golden.json` are compared, excluding: all `date` fields, dates in file names, the Date of eml files, every row of the engineering-release `bom` (level, category and operation columns were added), and the whole `reviewed.json` of the costing station. Everything else (key parameters, the spec sections, DFM items, PO check, supply-chain requirements) must be the same.

## File structure
| Location | Responsible for |
| --- | --- |
| `npi/__main__.py` | Command entry point: `intake`, `status`, `prepare`, `render`, `approve`, `reopen`, `decide`, `compare` |
| `npi/intake.py` | Table A, table B (pure functions) |
| `npi/state.py` | Reading and writing `state.json`; table C (the decision is a pure function; reads and writes are in one place) |
| `npi/readers/` | Checks at the entry point, one file per kind of input: `master.py` (the four factory master data files), `spec.py` (draft spec), `ecr.py`, `po.py`, `ours.py` (reads our eml / docx / xlsx back for `approve`). Missing files and missing fields are reported here, naming the file, which record and which field |
| `npi/sources.py` | Table D (pure functions) |
| `npi/stations/` | One file per station: `dfm.py` (including change impact), `release.py`, `cost.py`, `po_check.py`, `supply.py`; each has `prepare`, `check` (checks the judgement file) and `render` |
| `npi/render/` | Output tools: `eml.py`, `docx_out.py`, `xlsx_out.py`, `drawing_pdf.py`, `step_cad.py` |
| `npi/compare.py` | Compares `reviewed.json` with `_ground_truth.json` and lists the differences (VERIFY STEP6-4) |
| `templates/` | jinja2 templates for the emails and PO check, the docx template for the formal spec, the xlsx templates for the BOM and unit cost |
| `config/people.json` | Sender, internal recipients (P10) |
| `.claude/commands/npi.md` | The manager's steps (P1) |
| `.claude/agents/npi-dfm.md`, `npi-release.md`, `npi-cost.md`, `npi-po.md`, `npi-supply.md` | The five station subagents: read `facts.json`, write `judgement.json`, run `render` until the check passes |
| `tests/` | One test file per STEP; `tests/fixtures/kalvara/` holds the hand-written judgement files |
| `check_templates.py`, `check_architecture.py`, `ruff.toml` | Pre-commit checks (separation of templates and logic, layering, ruff), run by `.git/hooks/pre-commit` |
| `check_corrections.py` | Correction-log check (S5), run by pre-commit; how it decides is in the table at the top of the file |
| `check_mutations.py`, `mutations.json` | Mutation-testing tool and its list of mutations (S6), run by hand in the STEP check and at the batch gate |
| `check_quality.py` | Quality scorecard (content-depth spec §9 + pending counts), run by hand, report only; how it measures is in the table at the top of the file |
| `npi/timeline.py` (Batch 3) | The derivation of table F (pure functions), working days; `timeline.json` is read and written in `pipeline.py` |
| `npi/registry.py` (Batch 3) | Collecting numbers and the duplicate check of table G (pure functions); `output/registry.json` is read and written only in `load` and `save` (corrected to match the code on 2026-11-22; it originally said `pipeline.py`) |
| `npi/readers/rules.py` (Batch 3) | Reads `LPC作業規則.md`: sources (P57), the names of §1, the days of §2, the rates and ratios of §3, the operations of §4 |
| `npi/costing.py` (Batch 3) | The pure functions of table I, table J and P81 (shared by the costing station, approve and the tests) |
| `npi/pending.py` (Batch 3) | Pending list (P59) |

## Manager flow (`/npi`, followed by the main conversation)
1. `python -m npi intake <file>` → shows the case, revision, document kind and schedule; on an error, stop and relay the error.
2. Find the next `未跑` (not run) station: `prepare` → dispatch the corresponding subagent, giving it the path of this station's folder → the subagent writes `judgement.json` and runs `render` until it passes (at most 3 rounds; if it still fails, change the offending fields to `待工程師填寫`).
3. Report the paths of the output files and the number of `待工程師填寫` items, and **stop**.
4. The engineer says `可以` ("OK") → `approve`; before the engineering-release station, first ask for the customer's decision and record it with `decide` → back to step 2.
5. `status <case>` can be run at any time; a new conversation continues from `status`.

## How it is tested
pytest. The automated tests do not call subagents and use the judgement files in `tests/fixtures/kalvara/` (P22). Corvane's files do not enter any test before STEP 7. The commands are in TESTS.md.

## STEP 0 Environment, manager
**To do**: 1. Rebuild `.venv` with Python 3.11 and install python-docx, openpyxl, pdfplumber, jinja2, matplotlib, cadquery, pytest (P21). 2. `intake`: table A, table B. 3. `state.py`: status and table C; `status`, `approve`, `reopen`. 4. `approve` first implements reading back the BOM xlsx (needed by STEP0-7); reading back the other documents is added at each station. 5. Write the manager flow in `.claude/commands/npi.md`. 6. Add the commands to "How to run" in CLAUDE.md.
**Tests to pass**: all 8 items of VERIFY STEP 0
**Also re-test**: none

## STEP 1 DFM / change-impact station
**To do**: 1. `readers/master.py`: the sections and clauses of QM-021, the entries of LL-003, MM-002, PL. 2. `readers/spec.py`: basic-data table, R table, contact table; tables are found by R numbers and headers, not by a fixed table order. 3. `readers/ecr.py`: basic data, CH table, affected-documents table, contact table. 4. `sources.py`: table D. 5. `stations/dfm.py`: A0 uses the spec's Rs, B0 onwards the ECR's CHs; `check` requires a paragraph for every R (for A0, those with problems) or every CH (for an ECR, all of them). 6. Two email templates (DFM, change impact). 7. `.claude/agents/npi-dfm.md`. 8. Add eml read-back to `ours.py`.
**Tests to pass**: all 5 items of VERIFY STEP 1
**Also re-test**: STEP 0

## STEP 2 Engineering-release station
**To do**: 1. The `decide` command and `decisions.json`. 2. `stations/release.py`: A0 from the draft spec + DFM result + customer decision; B0 onwards from the previous revision's `reviewed.json` + ECR + customer decision, changing only the fields the CHs involve (`check` compares with the previous revision, and a field changed without being involved in a CH is an error). 3. The key parameters (channel count, pitch, end-face angle, pigtail length and tolerance, substrate and lid dimensions) are stored only once, and the spec, BOM, drawing and STEP all come from that one copy. 4. Every BOM part number must be found in MM-002, and rows not found are flagged. 5. The formal spec docx template and the BOM xlsx template. 6. `drawing_pdf.py` (P17), `step_cad.py` (P18). 7. A new revision's output is written in the new revision's folder, leaving the previous revision untouched. 8. Add docx and BOM read-back to `ours.py`. 9. `.claude/agents/npi-release.md`.
**Tests to pass**: all 8 items of VERIFY STEP 2
**Also re-test**: STEP 0–1

## STEP 3 Costing station
**To do**: 1. `stations/cost.py`: every bought item of the BOM × the price-list unit price (P13); those not found are `待工程師填寫` and the total is marked "不完整" (incomplete) (P14). 2. The unit cost xlsx template, with the price-list source (part number, price column) next to the unit price of each row. 3. Add unit cost read-back to `ours.py`. 4. `.claude/agents/npi-cost.md`.
**Tests to pass**: all 3 items of VERIFY STEP 3
**Also re-test**: STEP 0–2

## STEP 4 PO check station
**To do**: 1. `readers/po.py` (P19): PO number, revision, date, and each line's part number / description, quantity, unit price and delivery date. 2. `stations/po_check.py`: the PO against the reviewed formal spec (part number, customer revision, our revision) and the unit cost (a unit price below cost is flagged); mismatches name the PO line and the field. 3. The PO check template (P15). 4. `.claude/agents/npi-po.md`.
**Tests to pass**: all 3 items of VERIFY STEP 4
**Also re-test**: STEP 0–3

## STEP 5 Supply-chain station
**To do**: 1. `stations/supply.py`: the requirement of every bought item (P16) and the MM-002 lead time; from B0 onwards compare with the previous revision's BOM and list additions, cancellations and quantity changes. 2. C1 has no new PO: use the quantity of the previous revision's reviewed PO, and the email states which revision it is carried over from. 3. Two email templates (material preparation, material change). 4. `.claude/agents/npi-supply.md`.
**Tests to pass**: all 4 items of VERIFY STEP 5
**Also re-test**: STEP 0–4

## STEP 6 Kalvara full flow
**To do**: 1. Complete the judgement-file fixtures for every station of Kalvara A0–C1 and run from start to finish. 2. Confirm nothing is written into `input/` and that re-runs give the same content (P8, P9). 3. The `compare` command. 4. In Claude Code actually run Kalvara A0 once with `/npi` (really dispatching subagents) and record the result in progress.
**Tests to pass**: all 4 items of VERIFY STEP 6
**Also re-test**: STEP 0–5

## STEP 7 Corvane exam
**To do**: 1. Run Corvane from A0 to C1 with `/npi`, with the user reviewing every station (or the user authorising me to press `可以` on their behalf). 2. Places where it gets stuck are recorded as issues, and the code is not changed in the middle of the exam; after the exam the user compares against the real documents and the differences are recorded in progress.
**Tests to pass**: both items of VERIFY STEP 7 (manual)
**Also re-test**: STEP 0–6

## STEP 8 fan-out engineering release (Batch 2)
**To do**: 1. Open branch `batch-2`, first save the Kalvara Batch 1 baseline (P46) and commit. Only afterwards add `product_type_sources` to the four Kalvara `release.json` fixtures (required by P36; added after the baseline is saved). 2. `params.py` is changed to group by product type (P36, P37): for each type a set of required parameters, numeric parameters and lower bounds, the rows of the spec table (each row with its own notation and read-back, P38), the product name and the item 10 name; the fibre-array content is unchanged. 3. `stations/release.py`: checks become per type (P36 type and source, P37 missing parameters, P39 divisibility, P43 fibre arrays only); `_change_errors` uses that type's parameters; the two fixed BOM rows by type (P40); `prev_sources` adds `PREV product_type`. 4. `render/drawing_pdf.py` adds the fan-out drawing and port map (P39, P41); `render/step_cad.py` adds the fan-out breakout box and assembly (P42). 5. The spec read-back of `readers/ours.py` by type (`read_spec_doc` needs to know the type); approve blocks edited fan-out parameters (P35 applies likewise). 6. `compare.py` per P44. 7. Corvane fixtures (P45); `fixture_of` and `run_real` in `conftest.py` are changed to take an optional case. 8. `.claude/agents/npi-release.md`: write the parameter tables of both types, `product_type_sources`, and stopping to report when the type is not recognised. 9. Re-exam: after P47, run Corvane from A0 to C1 with `/npi` as in STEP 7, with the user reviewing every station (or authorising me to press on their behalf), recording issues where it gets stuck and not changing the code in the middle of the exam.
**Tests to pass**: all 10 items of VERIFY STEP 8 (8-10 manual)
**Also re-test**: STEP 0–6 (8-9 is compared separately with the Batch 1 baseline)

## STEP 9 Common (Batch 3)
**To do**: 1. Open branch `batch-3`, first save the comparison baseline (P48) and commit. 2. `readers/rules.py` (P57): sources, the names of §1, the days of §2, the rates and ratios of §3, the operations of §4; `master.source_texts` adds the operating-rules sources; `sources.py` adds the range check (P58). 3. `timeline.py` (table F, P49–P51); `pipeline.prepare` takes the date from the timeline (P52); `--date` becomes the engineer's specification; new command `timeline <NPI> <revision>` (display). 4. Every station uses the timeline's dates: DFM / change impact, engineering release (spec, BOM, drawing, STEP), costing, PO check, supply chain; email at 10:00 (P53). 5. The change-impact judgement file adds `revision_kind` (P54), and check requires consistency with the ECR's PO revision; `reviewed.json` carries it out. 6. `registry.py` (table G, P55, P56); engineering release checks the finished-product part number and registers it after render succeeds. 7. `pending.py` (P59), and `render` prints the pending list. 8. New command `tell` (P60). 9. `.claude/commands/npi.md`: show the timeline after intake, the engineer changes dates with `--date`, reports use the pending list, the engineer changes values with `tell`; `npi-dfm.md` adds `revision_kind`. 10. `compare` adds the comparison of the timeline with the answer file's `timeline` (list only).
**Tests to pass**: all 15 items of VERIFY STEP 9
**Also re-test**: STEP 0–8 (8-9 is changed to compare with the P48 baseline, see TESTS)

## STEP 10 BOM (Batch 3)
**To do**: 1. Add the upper-level group rows to the fixtures (P82) and verify that the parent quantity of every level-2 item is 1 before `qty_per` can be taken directly as "per parent" (P61); if not, stop and say so. 2. The BOM template is changed to the layout of the Kalvara reference BOM: 4 worksheets for A0, 5 from B0 onwards (P61, P62, P64–P67). 3. `release.py`: check and render of levels and extended quantity (P61), category (table H), Routing (P63), BOM to operation mapping (P64), Channel Map (P65), Change Summary (P66) and Revision (P67, P68). 4. `readers/ours.read_bom` reads the new layout (the quantity is read from "Qty per Parent", and the extended quantity is recalculated per P61); costing and supply chain switch to the extended quantity. 5. Fixtures get `routing`, `routing_adds`, `op`, `channel_map`, `change_map` and the categories of new part numbers (Kalvara A0–C1; Corvane A0, B0, P80). 6. `.claude/agents/npi-release.md` describes the new fields and the operations of operating rules §4.
**Tests to pass**: all 11 items of VERIFY STEP 10 (including the tests of P61 and P82)
**Also re-test**: STEP 0–9

## STEP 11 Unit cost sheet (Batch 3)
**To do**: 1. Install `pycel` and confirm it can calculate the functions used (P79); if not, stop and ask. 2. `costing.py`: the pure functions of table I, table J, P73, P74, P76 and P81. 3. The cost template follows the 8 worksheets of the Kalvara reference cost sheet (P69); `xlsx_out.write_cost` writes the input cells and formulas (P70). 4. `cost.py`: prepare brings in the previous revision's cost, the PO quantity per lot and the operating-rules sources; check `lot_size` (P58), `target_price`, `services`, `nre`, `ecr_nre` (P72, P75); render writes 7 / 8 worksheets. 5. `ours.read_cost` is changed to read the input cells and recalculate with `costing.py` (P78); the PO check and compare use the recalculated `total`. 6. Fixtures get the new fields of `cost.json` (Kalvara A0–C1; Corvane A0). 7. `.claude/agents/npi-cost.md` describes the new fields, that the scrap rate is judged by the program, and how pending values are reported.
**Tests to pass**: all 16 items of VERIFY STEP 11
**Also re-test**: STEP 0–10

## STEP 12 Batch 3 re-exam
**To do**: 1. Run Kalvara A0–C1 from scratch with the fixtures (automated): compare with the P48 baseline (table K) and list the cost differences from the answer file. 2. Rename the `output/NPI-26-104/` of the Batch 2 re-exam to `output/NPI-26-104_exam2/` (not deleted). 3. Run Corvane from A0 to C1 with `/npi`, with the user reviewing every station (or the user authorising me to press on their behalf), recording issues where it gets stuck and not changing the code in the middle of the exam. 4. The user compares against Corvane's real BOM and cost sheet and notes the differences.
**Tests to pass**: all 3 items of VERIFY STEP 12 (12-2, 12-3 manual)
**Also re-test**: STEP 0–11

## Not yet decided
- (Batch 2) Corvane C0 and C1 engineering release are only run in the re-exam and have no automated tests (P45 only writes A0 and B0 fixtures); CH2 of C0 changes the trunk cable and CH1 of C1 changes the leg labels, neither touching key parameters, so it depends on what the subagent writes.
- (Batch 2) The assembly STEP has 36 leg cylinders and a 10 m trunk, and how long cadquery takes to generate it is only known by actually running it; if a single file takes more than 30 seconds, stop and ask you whether to merge the legs into one bundle.
- (Batch 2) The product category in the fan-out drawing file name is written as `Fanout`, inferred from the input case folder name `NPI-26-104_FO36_Fanout`; the file names of Corvane's our-side drawings must not be looked at during development, so this is unverified and is to be checked after the STEP8-10 re-exam.
- (Batch 2) The costing, PO check and supply-chain stations were not changed for fan-out; in principle they are generic (reading the BOM, price list and PO), but only the re-exam exercises them.
- The installation of cadquery on this Mac (Apple Silicon, Python 3.11) is only certain once it is actually installed in STEP 0; if it cannot be installed, stop and ask you.
- Corvane's customer documents are laid out differently from Kalvara's (issue #11 of the old version: the column names of the basic-data table differ). The readers find tables by R / CH numbers and accept synonyms for column names, but without having seen Corvane there is no way to be sure that is enough; STEP 7 will tell.
- The engineering-release station has to decide the BOM materials (picked from MM-002), the hardest judgement in the whole flow; Batch 1 allows a lot of `待工程師填寫`.
- (Batch 3) The scrap rate of the Kalvara reference cost sheets A0–C1 is 9 % throughout, and the table of operating rules §3 has no 9 %; per table J, both A0 (24 channels) and B0 (32 channels + PM) will be pending. Follow the rules, and only list the differences from the answer file (BRIEF 3-5).
- (Batch 3) All run times are pending (BRIEF 3-2), so the total cost and quote of every revision of Kalvara and Corvane will be "不完整" (incomplete) until the engineer fills them all in with `tell`. The automated tests exercise the full calculation with times filled in by the fixtures.
- ~~(Batch 3) Whether pycel supports CEILING and COUNTBLANK has not been verified (P79)~~ Checked: CEILING works; COUNTA and COUNTBLANK do not, so COUNTIF is used instead (see the change log for STEP 10 done).
- (Batch 3) The names for emails are still in `config/people.json`, while the BOM and cost sheet read operating rules §1; the two coexist until Batch 5 (P68).
- (Batch 3) Operating rules §4 does not say where the PM and coating operations are inserted in the basic sequence; the agent sequences them and the program only checks presence (P63). In the Kalvara reference Routing the PMA is between FPR and VGA, and pre-bake and outsourced coating come after EFI; this is written into the agent instructions as an example.

## Change log
### 2026-11-01 (STEP 0 done)
- File structure adds `npi/pipeline.py`: the file reads and writes of intake / prepare / render / approve / reopen / decide are concentrated here, and `state.py` keeps only the pure decision function (table C). The table did not originally list this file.
- Added `pytest.ini` and `requirements.txt` (cadquery actually installed as 2.8.0).
### 2026-11-01 (STEP 1 done)
- Added `npi/readers/docx_util.py` (walks docx paragraphs and tables in order, de-duplicates merged cells) and `npi/render/__init__.py` (template location), not listed in the table.
- The `dfm` judgement-file format is settled (written in `.claude/agents/npi-dfm.md`): the citation of each item's `ref` is computed automatically, plus `capability_sources` and `sources`; ECRs have `po_change`.
### 2026-11-01 (STEP 2 done)
- Added `npi/params.py`: the list of key parameters, the rows of the spec table, the description string and the channel-count comparison, shared by spec / BOM / drawing / STEP (implementing "the key parameters are stored only once" of PLANS), not listed in the table.
- The spec reader additionally reads the "Parameter | Value" table as `SPEC <parameter name>` sources (the substrate, boot outline and connector quantity need to cite it); the DFM station uses it too.
- BOM quantities may be `待工程師填寫` (treated as empty when read back).
- Engineering-release checks: all key parameters are required and numeric parameters must be greater than 0; in an ECR revision a parameter that differs from the previous revision must map to a CH (a judgement-file check added beyond table C, implementing VERIFY STEP2-7).
### 2026-11-01 (STEP 3 done)
- The costing order quantity is judged by the costing subagent (citing the customer document, e.g. first PO 2,000 pcs in R-14), and Python chooses the price break from "quantity × costing order quantity" (P13).
- When the BOM and price-list UoM differ, no conversion is done; it is written as `待工程師填寫` with a note in Remark (to avoid silently calculating wrongly).
- When the unit cost is read back, the total is recalculated from the cost elements; the total only counts as complete once the engineer has filled in the other cost elements on the Summary sheet (implementing P14).
### 2026-11-01 (STEP 4 done)
- The PO comparison is written as a pure function `po_findings`: the LPC P/N of every delivery line must be the part number of one of our reviewed revisions; the customer revision must match; the unit price of this revision's part number is compared with the unit cost (when the cost is incomplete it writes "無法比較" (cannot compare) and makes no judgement).
- The engineering-release `reviewed.json` adds `cust_rev`: A0 takes the Rev of the customer spec's "Drawing" field (e.g. KVP-DWG-2408 Rev A), an ECR takes the customer revision after the change; when not found it is None and the revision is not compared.
- When the unit cost is read back, "direct material" is recalculated from the material rows and the old number on the Summary sheet is not trusted (the total is only right after the engineer fills in the material rows).
### 2026-11-01 (STEP 5 done)
- Requirements and BOM differences are written as pure functions (`requirements`, `bom_changes`); the lead time is MM-002's "Lead Time (days)".
- The PO quantity is taken from the nearest reviewed PO check going back from this revision (C1 uses C0's PO Rev 2), and the email states which revision it is carried over from.
### 2026-11-01 (code part of STEP 6 done)
- Fields mapped by `compare`: engineering release (part number, the 14 key parameters, quantity of each BOM item; the answer's pitch is in mm and is converted to µm), costing (direct material, total), PO (total finished quantity, revision), supply chain (gross requirement per item).
- The engineering-release check is changed to "the end-face angle may be 0" (C0 changes to a 0° flat end face; requiring every numeric parameter to be greater than 0 was wrong).
- Not yet done: item 4 of PLANS STEP 6, "really dispatch subagents to run Kalvara A0"; STEP 6 is only ticked once that is done.
### 2026-11-01 (batch gate: fixing issues #1–#13)
- The station order is fixed as dfm → release → cost → po → supply, regardless of the order documents arrive in (#2).
- reopen renames the `reviewed.json` and `facts.json` of the stations sent back to `*.reopened.json` (not deleted); render also runs rows 2–5 of table C first (#3).
- On engineering-release approve, if a key parameter of the formal spec has been edited by the engineer it is blocked, because the BOM, drawing and STEP would not follow (#4).
- Make/Buy only accepts Make and Buy; the Kit I had added myself is removed (#5).
- Table D: dates are compared whole, not split into year, month and day (#7); §, LL, DR, R, OP and CH numbers mentioned in the text must exist (#8; row 1 of table D was originally only half done); title, risk, feasibility, po_change, the BOM's uom / remark and the spec section titles all have their numbers checked (#9).
- PO check: when our customer revision is unknown it writes "無法比較" (#12); the costing station's facts add the quantity of the most recent reviewed PO, implementing P13 (#13).
- The factory master data readers only accept rows in part-number / entry form (#1); NpiError is raised when the customer document cannot be found (#6); compare adds the DFM station (#11).
- The subagent trial run of item 4 of PLANS STEP 6 is done (progress entry 14), and STEP 6 is ticked.
### 2026-11-01 (after the user's decisions: table D tightened, provisional table completed)
- The user agreed to list the rules that were only recorded in the change log in the provisional table as they stand: P23–P35 added.
- The user approved tightening table D: the definition of codes in row 1 is narrowed (issue #16); row 5 is added, "the previous revision may only be cited down to a single parameter or a single BOM row" (issue #17, removing the whole-JSON sources `PREV release`, `RELEASE`, `FACTS`, `PREV cost`); row 6 is added, "what cannot be found must be written as `待工程師填寫`" (written in the agent instructions, not checked by the program).
### 2026-11-01 (STEP 7 exam result and Batch 1 scope)
- Corvane A0's DFM passed, and engineering release stopped because the product is fan-out (no substrate, lid or pitch) (issue #18). The user chose B: the scope of Batch 1 is set to fibre arrays, fan-out moves to Batch 2, and STEP 7 is left to be re-taken in Batch 2; agreed to merge with issue #18 still open.
### 2026-11-01 (Batch 2 plan)
- The user confirmed Batch 2 (added by AI) of BRIEF and VERIFY. Added the "Batch 2" progress, five rows under what you have already decided, P36–P47, STEP 8, and three not-yet-decided items.
- P23 (14 key parameters) and P26 (two fixed BOM rows) originally only spoke of fibre arrays; from Batch 2 they are "for fibre arrays"; for fan-out see P37 and P40.
- "<product category>" in table E is `product_type`: `Fiber_Array` or `Fanout` (P36).
### 2026-11-01 (STEP 8 code done, re-exam pending)
- The breakout-box dimensions are ordered L x W x H following MM-002 and the customer's wording (spec row name "Fan-out box L x W x H (mm)", same on the drawing), where P41 originally said W x L x H; the STEP orientation is W along x, L along y, H along z (the same as fibre arrays).
- `PREV product_type` is added among the sources in engineering-release `prepare`, not in `params.prev_sources` (that function has the regression test of issue #17 and only handles parameters and BOM rows).
- The fan-out drawing shows at most 12 legs schematically; the number is written in the "LEGS 36 x …" annotation and the port map.
- The product-type check replaces the former format check "only English letters and underscores" (the product_type part of P25): only the types in `TYPES` are accepted.
- Divisibility check (P39): when parameters are missing, only the missing ones are reported first; when all parameters are present, it runs regardless of errors in other fields, so the engineer sees all problems at once. (Wording corrected after the read-only review)
- `.claude/agents/npi-release.md` describes the parameters of both types, `product_type_sources`, and stopping when the type is not recognised.
### 2026-11-01 (batch gate: after mutation testing and read-only review)
- The implementation of P39 has two extra points not originally written: the fibre count, number of trunk connectors and number of legs must be integers (`36.0` in the judgement file is blocked); the end face in the agent instructions is only an example (APC, PC) and is not checked by the program.
- The implementation of the P45 guard is narrower than the original text: it only blocks files in `tests/` that mention both Corvane and a `02_`–`04_`, `06_` path or the answer-file wording, and does not match the file names of our-side documents (the first review advised against listing those file names, since listing them amounts to having seen them).
- The implementation of P36 is broader than the original text: it only checks that `product_type_sources` exists and every source is in facts, without requiring that A0 cites R / SPEC and an ECR cites `PREV product_type`. On 2026-11-01 the user decided to keep it as is: the meaning of P36 becomes "must cite, and every source must exist", and what A0 / an ECR should cite is advice written for the agent.
- When the spec read-back cannot recognise the product type of the key-parameter table, it reports "認不出是哪種產品" (cannot tell which product this is) directly (issue #27) and no longer defaults to fibre array.
- The patterns of the guard test are extracted into the module constants `MENTIONS_CORVANE` and `OUR_DOCS` (issue #26).
- issue #21: a BOM row whose part number is `待工程師填寫` creates no `PREV BOM` source; the material-change notice lists it separately as "料號待填" (part number pending) and does not count it as added / cancelled.
### 2026-11-01 (Batch 3 plan)
- The user confirmed Batch 3 (added by AI) of BRIEF and VERIFY, with 3-1 to 3-7 as recommended. Added the "Batch 3" progress, eleven rows under what you have already decided, P48–P81, tables F–K, five rows of file structure, STEP 9–12, and five not-yet-decided items.
- P9 (date taken as the day of the first prepare) is replaced by P52; P14 (only direct material calculated) is replaced by P69–P81; item 10 of P26 and P40 stays, but the BOM columns change per P61–P64.
- Table J: the scrap rate is now judged by the program (the original BRIEF 3-5 says the agent picks), agreed by the user on 2026-11-01; `PREV quote` and the old tests TESTS will change were also agreed.
- Corrections after the read-only review (opus): an override field for the scrap rate (P72, row 4 of table J); with PM two rows match (table J); the Channel Map rows come from the judgement file (P65); upper-level group rows added (P82); test data for engineer input (P83); costing and material preparation on the same day for a minor change (P51, table F); specifying a weekend is an error (P49); PO and quotation numbers only from documents already handed in (P50, P55, table G); operations get `kinds` and set-up is fixed at 20 minutes (P63); Change Summary includes Make rows (P66); `PREV quote` marked as needing your agreement (P72).
### 2026-11-01 (STEP 9 done)
- The names of operating-rules sources are taken automatically from the original text (`readers/rules.py`): table rows use the first column, bullet sub-items use the words before the first number; when no clean name can be taken a sequence number is used, e.g. `RULES §3 報價 1` ("成本 ÷（1 − 30 % 目標毛利）", cost ÷ (1 − 30 % target margin)). Bold rules without numbers ("小改" (minor change) in §2, §5) are taken as whole sentences for the basis column to cite.
- New commands `timeline <NPI> <revision>` (prints the timeline) and `tell <NPI> <revision> <station> "<own words>"`; `render` prints the pending list. `compare` adds the comparison of the timeline with the answer file's `timeline` (the event mapping is in `compare.TIMELINE_MAP`).
- The registry is updated on `intake`; engineering-release `prepare` puts "the numbers already used up to this revision's receipt date" into facts, and check uses it (P55, P56). A stand-in station (used in tests) without a finished-product part number registers nothing.
- `.claude/commands/npi.md` adds: showing the engineer the timeline after intake, changing dates with `--date`, reporting the pending list as printed by render, and the engineer giving values via `tell` (section 3a). `npi-dfm.md` adds `revision_kind`.
### 2026-11-01 (STEP 10 done)
- The quantity of a group row (Make, with level-2 items under it) is always 1, and the program does not check the source of this 1 (implementing P82; table D would otherwise require a source, but a group row only bundles the items under it).
- The operation of item 10 is taken by the program as the range of the operations of the level-2 items under it (e.g. `Op 30` or `Op 10-30`); item 0 has no operation.
- Change Summary: the finished-product part number (item 0) changing with the revision is not a change item (operating rules §7: it changes with every revision), and all other rows (including item 10 and group rows) are compared; rows with a pending part number are not compared.
- An ECR revision that keeps the previous revision's `routing_adds` cites the new source `PREV routing_adds <PM / coating>` (placed in engineering-release prepare like `PREV product_type`; the same kind as row 5 of table D).
- The functions of P79: pycel does not support COUNTA or COUNTBLANK, so COUNTIF(range,"<>") and COUNTIF(range,"") are used instead; CEILING, ISBLANK, ISNUMBER, SUMIF and IFERROR were tried and work.
- The BOM template `templates/bom.xlsx` is redone with 5 worksheets (following the columns of the Kalvara reference BOM, with Change Summary deleted for A0). The check cell of Channel Map is at E3 (E2 is the expected row count).
- Costing and supply chain switch to the extended quantity (`ext_qty`); the costing facts carry the Routing. The parent quantities in the Kalvara and Corvane fixtures are all 1, so the numbers do not change (STEP12-1 still passes against the Batch 2 baseline).
### 2026-11-01 (STEP 11 done)
- The implementation of P83 becomes: tests first run `tell` the way an engineer would, then change the pending cells of the judgement file to cite `ENG-n` (run time 5, pending quantity 0.1, scrap rate 0.1, all numbers chosen by the tests themselves, not taken from the answer file); no separate `engineer.json` fixture is stored.
- The comparison price of an ECR revision is taken automatically by the program from the previous revision's quote (`PREV quote`), and the agent only writes `target_price` for A0 (P72 originally said the agent cites `PREV quote`).
- Outsourced services (e.g. `SV-ARC-1310`) cite a single operation of the engineering-release Routing (new source `ROUTING <op>`, the upstream station of this revision, one source per operation); Delta classifies it by this operation's CH.
- When the engineering release in the costing station's facts has no `params` (old format), the scrap rate is simply pending and no error is raised (`test_issue13` uses this minimal kind of engineering-release result).
- The cost sheet's input cells and `costing.model` use the same preparation (`cost._book`); approve reads back only the input cells and recalculates (P78), so a unit price changed directly in the xlsx is reflected too.
### 2026-11-01 (automated part of STEP 12 done)
- `compare` additionally compares the quote (the answer file's `quote_price_usd`) and the scrap amount (`unit_cost_usd.scrap`) for costing; the answer file has no scrap rate, so only the amount can be compared.
### 2026-11-01 (batch gate: after mutation testing and read-only review)
- issues #28–#30: tests added; the unused extended-quantity calculation in `release.bom_rows` is deleted.
- issues #31–#37, #39 fixed (progress entry 50). Table F gets one more sentence: a specified or already produced date must not be earlier than the previous fixed date; a derived date in between is moved earlier (#32). The implementation of P70 becomes counting empty input cells (#33). P56 adds "numbers registered by the tool itself always count as used" (#34). P66 adds "a change between pending and a number does not count" (#39, see the P84 table below, needs your agreement).
### 2026-11-02 (the user agreed to P84–P94 and decided the scrap base and the PO quotation number)
- P84–P94 agreed by the user (including retroactive approval of adding `op` and category to the `test_STEP3_2` data).
- Row 6 of table I: the scrap base also excludes the material handling on packaging. The wording of BRIEF 3-5 ("material (excluding packaging) + services + conversion + material handling + manufacturing overhead") is not changed, since BRIEF is the user's file; "material handling" here is read as "the part excluding packaging".
- Added P95 and row 4 of table G: the quotation number on a customer PO is registered too.
### 2026-11-02 (Batch 3 merged into main)
- STEP 9–11 and the automated part of STEP 12 are merged. Steps 2 and 3 of STEP 12 (re-running Corvane with `/npi`, comparing with the real documents) are not yet done, and STEP 12 is not ticked.
### 2026-11-22 (provisional table split into business rules and implementation choices)
- The heading of "我先暫定的" (provisional business rules) adds "business rules, need your agreement"; an empty "我自己定的" (implementation choices) table is added below it (implementation choices, no stopping for agreement). P1–P95 are untouched. Agreed by the user (CLAUDE.md rules 4 and 9 changed in step).
### 2026-11-22 (linter and architecture check)
- "我自己定的" adds S1 (ruff) and S2 (architecture check). File structure gets the three check files; the registry row is corrected to match the code (reads and writes are in registry's load / save, not in pipeline).

### 2026-11-23 (quality scorecard)
- "我自己定的" adds S3; file structure adds `check_quality.py`. STEPs, decision tables and "我先暫定的" are untouched.

### 2026-11-23 (manual-test triage)
- "我自己定的" adds S4 (the live smoke run opens a clean session from the command line). STEPs, decision tables and "我先暫定的" are untouched. How manual tests are split into three piles is written in the last section of TESTS.md and in CLAUDE.md rule 9 (4)(5).

### 2026-11-24 (correction checks, branch correction-checks; the user read the draft and said 「照草稿做」)
- Draft from the talk "All Code Is Slop (Except Mine)" (Lauren Tan, AI Engineer): every correction should end as a deterministic check. Layers 1–2 (ruff, architecture, template checks, test-count ratchet) and the "AI runs it first" layer (live smoke run, `check_quality.py`, external testing) already exist; what is missing is noticing the second occurrence of a correction (S5), a mutation tool that is not rewritten each time (S6), and a structural fix for issue #48 (P100).
- "我自己定的" adds S5, S6; "我先暫定的" adds P100 (changes P34; agreed by the user); file structure adds two rows. No VERIFY STEP: like S2–S4 these are development tools; issue #48 follows rule 10.
