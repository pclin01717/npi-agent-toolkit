# VERIFY.md
> 2026-11-01: drafted by the AI, finalised and confirmed by the user. The AI does not change it; extra tests go in TESTS.md.
> Each item is written as "what you do → what you see (must not happen: …)". All examples use Kalvara (NPI-26-097); Corvane only appears in the STEP 7 exam.
> Batch 1 is "the full flow, every station rough first", so this only verifies that it runs, the format is right, numbers have sources and hand-over works; it does not verify that the judgement matches the answer files.

## STEP 0 Manager: recognise documents, dispatch, stop for review
- [ ] Hand the A0 draft spec `KVP-SPC-2408_RevX1` to the manager → it reports "NPI-26-097 / A0 / customer draft spec" and schedules only the DFM station; the other stations show `未跑` (not run) (must not happen: running on without waiting for my review)
- [ ] Hand over B0's `KVP-ECR-2408-01` → it reports "B0 / ECR / previous revision A0" and schedules the change-impact station
- [ ] Hand over the B0 ECR before all A0 stations are reviewed → error stating which station is not yet reviewed (must not happen: using unreviewed A0 output as the previous revision)
- [ ] Hand over C1's `KVP-ECR-2408-03` → the schedule has no PO check station, and the supply-chain station comes after engineering release
- [ ] Hand over an unrecognisable file (e.g. the factory master data `LPC-PL-2026H2`) → error giving the file name and why it is not recognised (must not happen: guessing a case or revision and carrying on)
- [ ] After a station produces output → the status is `待審` (pending review); I say `可以` ("OK") → it becomes `已審` (reviewed) and only then is the next station dispatched
- [ ] I edit a draft directly (e.g. the quantity of a part number in the BOM) and then say `可以` → the next station reads the number I changed
- [ ] Close the conversation half-way, open a new one and call the manager → it continues from the `待審` station, and stations already reviewed are not re-run

## STEP 1 DFM / change-impact station
- [ ] A0: hand over the draft spec → a DFM reply .eml appears under `output/NPI-26-097/A0/` and opens in a mail client; recipient Dr. Priya Raman, subject contains `KVP-RFQ-26-0311` and `KVP-SPC-2408 Rev X1`
- [ ] Open the DFM email → every item is marked with the spec's R number, and capability claims come with an `LPC-QM-021` section or an `LPC-LL-003` entry
- [ ] Pick 5 numbers at random from the DFM email (amounts, weeks, capability values) → each one can be found in some file under input; anything without a source is written as `待工程師填寫` ("to be filled in by the engineer") (must not happen: a number that cannot be traced)
- [ ] B0: hand over `KVP-ECR-2408-01` → a change-impact assessment .eml whose subject contains the ECR number, with one paragraph of judgement for each of CH1–CH4 (must not happen: any CH missing)
- [ ] C1: hand over `KVP-ECR-2408-03` → the change-impact assessment email has CH1–CH3 and does not mention a PO revision (the ECR says No PO revision)

## STEP 2 Engineering-release station
- [ ] The A0 DFM email is reviewed and I tell the manager the customer's decision (e.g. "全部接受" (all accepted)) → the formal spec (docx), BOM (xlsx), drawing (PDF) and two STEP files (block, assembly) appear, with file names following the input naming, e.g. `LPC-PS-26097_RevA0_Product_Specification.docx`
- [ ] DFM is reviewed but I have not stated the customer's decision → the manager asks for the customer's decision first (must not happen: assuming everything was accepted)
- [ ] Open the A0 formal spec, BOM and drawing → channel count 24, pitch 127 µm, end face 8°, pigtail 800 ± 20 mm are the same in all three (must not happen: the same number differing between two documents)
- [ ] Open the BOM → finished-product part number `LPC-FA24-127-8A`; every part number can be found in `LPC-MM-002`, and those that cannot are flagged
- [ ] Open the drawing PDF → a simplified outline of the block, lid and boot is visible, with the main dimensions and a channel table
- [ ] Open the block STEP in a 3D viewer → the outline can be measured, and length, width and height match the formal spec
- [ ] B0: after ECR-01 is reviewed → the new documents are revision B0, 32 channels, MPO-16; items the ECR does not mention are the same as A0 (must not happen: unrelated fields changed)
- [ ] After B0 is produced → the A0 files are still there with unchanged content (must not happen: overwriting the previous revision)

## STEP 3 Costing station
- [ ] The A0 BOM is reviewed → a unit cost xlsx appears; the unit price of every part number can be found in `LPC-PL-2026H2`
- [ ] A part number is not in the price list → that row is written as `待工程師填寫` and the total is marked "不完整" (incomplete) (must not happen: adding it to the total as 0)
- [ ] Pick a part number and calculate "quantity × unit price" by hand → same as that row of the unit cost sheet

## STEP 4 PO check station
- [ ] Hand over A0's `KVP-PO-7700-2614_Rev0.pdf` → the check result lists the PO number, revision 0, part number `LPC-FA24-127-8A`, quantity 2,000, unit price USD 112.00 and the four delivery lots, and compares them with the reviewed formal spec revision and unit cost
- [ ] The part number or revision on the PO does not match our reviewed documents → the check result is marked "不一致" (mismatch) and points to the line and field
- [ ] The PO unit price is below the unit cost → the check result flags it

## STEP 5 Supply-chain station
- [ ] The A0 PO check is reviewed → a material-preparation notice .eml whose subject contains `NPI-26-097` and the PO number
- [ ] Open the material-preparation notice → every bought item in the BOM has a row with its required quantity; pick one and calculate "quantity per finished unit × PO quantity" by hand, and it matches
- [ ] B0 → the material-change notice email lists the part numbers added, cancelled and changed in quantity
- [ ] C1 (no new PO) → calculated with the quantity of the previous revision's PO, and the email states which PO revision the quantity is carried over from

## STEP 6 Kalvara full flow
- [ ] Kalvara A0 → B0 → C0 → C1 run in order with every station reviewed → the output of all four revisions is under `output/NPI-26-097/` (must not happen: any file written into `input/`)
- [ ] Re-run one revision with the same input → the output content is the same, with no extra duplicate emails or files
- [ ] Every station's output has a structured result file; open a new conversation, give it only the files and run only the next station → it runs (proving that hand-over need not change when moving to the SDK later)
- [ ] After each revision is run → show me a list of where each station's output differs from `_ground_truth.json` (list only; not a failure in Batch 1)

## STEP 7 Corvane exam
- [ ] Corvane (NPI-26-104), never read during development, runs A0 → C1 as in STEP 6 → every station produces output, and nothing stops just because the documents are laid out differently (must not happen: reading Corvane's our-side documents or answer files during development)
- [ ] After the exam → I compare against Corvane's real documents and note where each station differs

## STEP 8 fan-out engineering release (Batch 2, added by AI, confirmed by the user on 2026-11-01)
- [ ] Corvane A0 DFM is reviewed and the customer's decision is "全部接受" (all accepted) → engineering release produces five documents with file names following the input naming, and the product category in the drawing file name is fan-out (must not happen: stopping because there is no substrate, lid or pitch) (added by AI)
- [ ] Open the Corvane formal spec → the key-parameter table has fan-out fields: 36 fibres, 3 x MPO-12 APC, 36 x LC/APC, trunk 3.0 m, leg length and tolerance, breakout-box outline; no substrate, lid or pitch appears (must not happen: forcing in fibre-array fields) (added by AI)
- [ ] The trunk tolerance +50 / 0 mm appears as-is in the spec, BOM and drawing (must not happen: turning into ± 50 or ± 0) (added by AI)
- [ ] Open the Corvane BOM → the names of the finished product and the first-level assemblies say fan-out (must not happen: "Fibre array" appearing) (added by AI)
- [ ] Open the Corvane drawing PDF → a simplified outline of the trunk, breakout box and legs is visible, the trunk length, leg length and breakout-box dimensions are annotated, and the port map table has 36 rows (added by AI)
- [ ] Open the breakout-box STEP in a 3D viewer → length, width and height match the breakout-box dimensions in the formal spec (added by AI)
- [ ] The judgement file gives an unrecognised product type → error saying which type is not supported (must not happen: carrying on as fibre array or fan-out) (added by AI)
- [ ] Corvane B0's ECR changes fan-out parameters → every parameter of the new revision that differs from the previous one maps to a CH, and parameters the ECR does not mention are unchanged (same as STEP2-7) (added by AI)
- [ ] After fan-out is added, re-run Kalvara fibre array A0→C1 as in STEP 6 → the output content is the same as in Batch 1 (must not happen: fibre array broken) (added by AI)
- [ ] STEP 8 done → re-take the Corvane A0→C1 exam as in STEP 7, and this time every station produces output (added by AI)


## Batch 3: common items + BOM + cost sheet (added by AI, confirmed by the user on 2026-11-01)
> Basis: `~/Desktop/FAU_Document/內容深度規格.md` (content-depth spec) §0, §5, §6, §9, and `input/00_Factory_Master_Data/LPC作業規則.md` (LPC operating rules) §1–§4, §7, §8. Examples use Kalvara; Corvane only appears in STEP 12.
> What follows is written per the recommendations of BRIEF Batch 3, 3-1 to 3-7 (on 2026-11-01 the user confirmed the recommendations).

## STEP 9 Common: event dates, number registry, operating rules as a source, pending list (added by AI)
- [ ] Hand over the Kalvara A0 draft spec → the manager reports A0's timeline: one date each for the DFM reply date, spec release date, cost-to-finance date and material-preparation notice date, each with its basis (the customer document date, or which segment of operating rules §2 plus how many working days) (must not happen: any date being the day it is run) (added by AI)
- [ ] Hand over Kalvara B0's ECR-01 → B0's timeline has the impact assessment date, spec release date, cost-to-finance date and material-preparation notice date; for intervals where the §2 ECR segment gives no number of days, the basis says "沿用初版" (carried over from the initial revision) (added by AI)
- [ ] Open every A0 output → the date on the document equals the event date in the timeline: DFM email = DFM reply date; spec, BOM, drawing = spec release date; cost sheet = cost-to-finance date; material-preparation email = material-preparation notice date; the date in the email file name is the same as Date, and the time is 10:00 +0800 (added by AI)
- [ ] Any day on the timeline → not a Saturday or Sunday; a later event is not earlier than the one before it (must not happen: the spec release date earlier than the DFM reply date) (added by AI)
- [ ] When DFM is reviewed I say "規格發行日改成 2026-07-14" (change the spec release date to 2026-07-14) → stations from engineering release onwards use 7/14 and the dates derived from it; the date of the already-reviewed DFM email does not change (must not happen: the date of a reviewed document being changed) (added by AI)
- [ ] Kalvara A0 → C1 run → list the dates where the timeline differs from the answer file's `timeline` (list only; not a failure) (added by AI)
- [ ] B0 engineering release → the suffix letter of the finished-product part number differs from A0; C1 (minor change) also changes it; the new part number is written into the registry (must not happen: two revisions using the same finished-product part number) (added by AI)
- [ ] Re-run engineering release for the same revision → the same finished-product part number is obtained, and the registry has no extra entry (added by AI)
- [ ] The part number to be generated is already in the registry or the material master → move to the next unused one, or stop with an error naming the number (must not happen: reuse) (added by AI)
- [ ] Open the registry when running A0 → it has the used numbers visible in the master data (e.g. the LPC purchase order number `PO-L26-0612` in the price list, the LPC part numbers in LL-003); it does not have the quotation number `LPC-Q-26-0391`, which only appears in customer documents from B0 onwards; that is only there when running B0 (added by AI)
- [ ] The cost sheet's scrap rate, rates, SG&A rate etc. cite the operating rules → the source points to a single value (e.g. "§3 工作站費率 FPR" (§3 work-station rate FPR)), and the same number can be found there (must not happen: passing by citing the whole operating rules, same as issue #17) (added by AI)
- [ ] The judgement file cites "§3 工作站費率 FPR" but writes 55 (55 is CPM in the same row), or cites a section that does not exist → error pointing to the field (added by AI)
- [ ] Values the operating rules write as a range (cost lot size 500–1,500, set-up time 10–30 minutes) → the document states the chosen value and its basis (added by AI)
- [ ] Kalvara C1 → the revision kind is "小改" (minor change), with the basis citing ECR-03's "no price change requested and no PO revision"; B0 and C0 are "大改" (major change) (added by AI)
- [ ] After each station produces output → the manager lists all `待工程師填寫` items of that station (document, worksheet, which cell); the count equals the actual number of pending cells in the documents (added by AI)

## STEP 10 BOM per content-depth spec §5 (added by AI)
- [ ] Kalvara A0 engineering release → the BOM xlsx has 4 worksheets: BOM, Channel Map, Routing, Revision; from B0 onwards there is one more, Change Summary, 5 in total (added by AI: content-depth spec §9 says all 5 must be present, while §5 says the change summary only exists after the initial revision; this follows §5 and the Kalvara reference documents)
- [ ] Open the BOM worksheet → it has levels 0 / 1 / 2, with item numbers written like 10, 10.10; every row has a part number, description, category (one of make, raw material, purchased part, packaging, consumable), quantity, unit, extended quantity, and a remark giving the corresponding operation (must not happen: a blank category) (added by AI)
- [ ] Category of bought items → per the mapping table in BRIEF 3-4 (e.g. Raw Material → raw material, optical adhesive → raw material, protective cap → packaging) (added by AI)
- [ ] Pick a level-2 item and calculate "its own quantity × the quantity of the level above" by hand → same as the extended quantity (added by AI)
- [ ] Open the Channel Map → Kalvara A0 has 24 rows, each with channel, fibre, connector position and function; the check cell shows OK; delete one row in the judgement file and re-render → the check cell is not OK (added by AI)
- [ ] Open the A0 Routing → the operations follow the fibre-array sequence of operating rules §4 (FPR → VGA → CUR → POL → EFI → CPM → VGA → CON → OPT → PKG), each with work station, set-up time and run time; the set-up time states its basis and the run time is written as `待工程師填寫` (must not happen: invented times) (added by AI)
- [ ] Open the B0 Routing (with PM fibre) → slow-axis alignment and connector key alignment (PMA) are added; open the C0 Routing (with coating) → pre-bake, outsourced coating and incoming inspection are added (operating rules §4) (added by AI)
- [ ] The operation in the remark of every BOM row → can be found in the Routing (added by AI)
- [ ] Open B0's Change Summary → compared with A0 it lists the items added, removed and changed in quantity and the routing differences, each mapped to one CH of ECR-01; I compare the two BOM revisions by hand and they match (added by AI)
- [ ] Open B0's Revision → it has two rows, A0 and B0, each with revision, date (its own spec release date), zone, description, prepared by and approved by (per operating rules §1) (added by AI)
- [ ] During BOM review I say in the conversation "Routing 第 30 道單件時間 2.5 分鐘" (Routing operation 30 run time 2.5 minutes) → the BOM is regenerated and that cell is 2.5; the cost sheet's Conversion also uses 2.5 (added by AI)

## STEP 11 Unit cost sheet per content-depth spec §6 and operating rules §3 (added by AI)
- [ ] Kalvara A0 BOM is reviewed → the cost sheet has 7 worksheets: Summary, Parameters, Material, Services, Conversion, Rates, Approval; from B0 onwards there is one more worksheet named like "Delta vs A0", 8 in total (added by AI)
- [ ] Open it in a spreadsheet application and recalculate → no error values (even with pending cells); more than 100 formula cells; the total cost in Summary is the same as the value computed by the program (added by AI)
- [ ] One cell is pending (e.g. the run time of an operation) → that cell is left empty with `待工程師填寫` next to it, Summary shows "不完整" (incomplete), and the other cells are still calculated (must not happen: an error value, or treating it as 0 and producing a quote that looks complete) (added by AI)
- [ ] Open Parameters → cost lot size, scrap rate, material handling rate 3 %, manufacturing overhead rate 22 %, SG&A rate 8 %, target margin 30 % and rounding USD 0.50 are all there, each row with its basis (which value of the operating rules, or the customer document) (added by AI)
- [ ] Scrap rate → per BRIEF 3-5: if it matches exactly one row of the operating rules §3 table, use that row; if it falls in a gap (Kalvara A0, 24 channels) or matches several rows (B0, 32 channels with PM fibre), write `待工程師填寫` and list the candidate rows (must not happen: picking a row by itself) (added by AI)
- [ ] Open Material → for every bought item "extended quantity × the price break taken for the pricing quantity = amount", with category subtotals; pick a row and the hand calculation matches (added by AI)
- [ ] Open Services → fibre arrays have lot qualification `SV-REL-LOT` at USD 1,650 per lot ÷ cost lot size; C0 (with coating) has `SV-ARC-1310` at USD 3.20 per piece; pick a row and the hand calculation matches (added by AI)
- [ ] Open Conversion → for every operation "(set-up ÷ cost lot size + run) × rate", with the operations the same as the reviewed BOM Routing; pick one and the hand calculation matches (added by AI)
- [ ] Open Rates → the work-station rates are the same as the table in operating rules §3 (added by AI)
- [ ] Open Summary → material, services, conversion, material handling, manufacturing overhead, scrap and SG&A add up item by item to the total cost; quote = total cost ÷ (1 − 30 %) rounded up to 0.50; it has the margin and the NRE breakdown, and compares the quote with the customer's target price (for A0, USD 105.00 from R-14) (added by AI)
- [ ] Change the unit price of a packaging item → the scrap row does not change (per the scrap base in BRIEF 3-5) (added by AI)
- [ ] Open the NRE breakdown → fixtures, test set-up, first article inspection and one-time design qualification are listed item by item; qualification the customer requires that is not in the price list (e.g. Kalvara's thermal cycling) is written as `待工程師填寫`; from B0 onwards ECR NRE is listed separately (added by AI)
- [ ] Open B0's Delta → every cost item of A0 and B0 side by side; the difference is split across each CH of ECR-01, parameter or price-break changes are on a separate row saying which parameter, the sum equals the total difference, and the check cell shows OK (must not happen: forcing it into some CH to balance) (added by AI)
- [ ] Open the Delta of C1 (minor change) → the cost has changed, the quote is carried over from C0, and it shows what the margin changed from and to (added by AI)
- [ ] Open Approval → prepared by and the date (cost-to-finance date) are filled in; review and finance confirmation say "待確認" (to be confirmed) (must not happen: invented sign-off records) (added by AI)
- [ ] During cost review I say in the conversation "成本批量改成 1,000" (change the cost lot size to 1,000) → the cost sheet is regenerated; the unit cost used by the PO check is the changed one (added by AI)

## STEP 12 Batch 3 re-exam (added by AI)
- [ ] Re-run Kalvara A0 → C1 as in STEP 6 → the checks of Batches 1 and 2 all still pass, except STEP8-9 (output same as Batch 1): this batch deliberately changed dates, worksheets and cost content; list where the cost sheet's total cost, quote and scrap rate differ from the answer file (list only; not a failure) (added by AI)
- [ ] Re-run Corvane A0 → C1 as in STEP 7 → BOM 4 / 5 worksheets, cost sheet 7 / 8 worksheets; the Routing is the fan-out cable operations (FOA → FOA → CON → SCT → OPT → PKG); scrap rate 5 %; Services has no lot qualification; "FAU" does not appear in the column names or product names of the BOM and cost sheet (must not happen: reading Corvane's our-side documents or answer files during development) (added by AI)
- [ ] After the exam → I compare against Corvane's real BOM and cost sheet and note where they differ (added by AI)
