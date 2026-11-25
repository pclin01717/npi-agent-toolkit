# TESTS.md
## How to run
`.venv/bin/pytest`: 102 tests in total when Batch 1 was merged (80 from VERIFY / PLANS / supplementary + 22 issue regressions); Batch 2 added 26 for STEP 8 and 8 for issues #19, #21–#27, 136 in total; Batch 3 expects to add 112 for STEP 9–12. To run a single STEP: `.venv/bin/pytest tests/test_step1_dfm.py`
The automated tests do not call subagents; judgement content comes from the hand-written judgement files in `tests/fixtures/kalvara/` (PLANS P22). In Batch 1 no test reads Corvane (NPI-26-104) files; from Batch 2 (PLANS P45) tests may use Corvane's customer documents (`01`) and the hand-written judgement files in `tests/fixtures/corvane/`, but still do not read Corvane's our-side documents (`02`–`04`, `06`) or answer files.

## STEP 0 Manager　`tests/test_step0_manager.py`
| From | VERIFY item | Automated tests | Beyond automated tests |
| --- | --- | --- | --- |
| STEP0-1 | Hand over the A0 draft spec → reports case / revision / kind, only DFM can run first, other stations not run | `test_STEP0_1_draft_spec_identified` (NPI-26-097, A0, draft spec)<br>`test_STEP0_1_next_station_is_dfm_others_not_run`<br>`test_STEP0_1_release_prepare_refused_before_dfm_reviewed` | [live run] In Claude Code type `/npi` with the draft spec and see that the manager stops after reporting |
| STEP0-2 | Hand over the B0 ECR → B0 / ECR / previous revision A0, schedules the change-impact station | `test_STEP0_2_ecr_identified_with_previous_rev`<br>`test_STEP0_2_ecr_next_station_is_impact` | — |
| STEP0-3 | Hand over the B0 ECR before A0 is fully reviewed → error naming the station | `test_STEP0_3_ecr_refused_names_unreviewed_station`<br>`test_STEP0_3_ecr_accepted_when_previous_all_reviewed` | — |
| STEP0-4 | Hand over the C1 ECR → no PO check station, supply chain after engineering release | `test_STEP0_4_c1_schedule_no_po_supply_after_release` | — |
| STEP0-5 | Unrecognisable file → error giving the file name and reason | `test_STEP0_5_master_data_file_rejected_with_name_and_reason`<br>`test_STEP0_5_our_document_rejected` (e.g. the eml in `02_DFM_Feedback`)<br>`test_STEP0_5_file_outside_input_rejected` | — |
| STEP0-6 | Pending review after output; only reviewed, and the next station dispatched, after `可以` | `test_STEP0_6_render_sets_pending_review`<br>`test_STEP0_6_approve_sets_reviewed_and_unlocks_next`<br>`test_STEP0_6_next_station_refused_while_pending` | [live run] After `/npi` runs a station, confirm the manager stops and waits for you to say `可以` |
| STEP0-7 | Edit the draft, then say `可以` → the next station reads the changed number | `test_STEP0_7_edited_bom_qty_reaches_next_station` (render BOM → change a quantity in the xlsx → approve → the costing station's facts hold the changed number) | [live run] Change a quantity in Excel by hand, then look at the cost sheet |
| STEP0-8 | Close the conversation and reopen → continues from the pending station | `test_STEP0_8_status_from_fresh_process_shows_pending`<br>`test_STEP0_8_reviewed_stations_not_rerun` | [live run] Open a new conversation, type `/npi status NPI-26-097` and see it continue |

From PLANS: `test_PLANS_P5_render_refused_after_approve`, `test_PLANS_P5_reopen_resets_downstream`
From supplementary (Corvane must not be touched before STEP 7): ~~`test_補充_tests_never_reference_corvane` (scans that nothing under `tests/` contains `NPI-26-104`)~~ replaced in Batch 2 by the next item (PLANS P45; **awaiting user review**)
From supplementary (from Batch 2, Corvane's our-side documents and answer files must not be read): `test_補充_tests_never_reference_corvane_our_docs` (does not list Corvane's folders; scans every file under `tests/`: no path where `NPI-26-104` is followed by `02_`–`04_` or `06_`, and no file that mentions both Corvane and `_ground_truth`)

## STEP 1 DFM / change-impact station　`tests/test_step1_dfm.py`
| From | VERIFY item | Automated tests | Beyond automated tests |
| --- | --- | --- | --- |
| STEP1-1 | A0 → a DFM .eml under output; recipient Priya Raman; subject contains the RFQ number and spec Rev X1 | `test_STEP1_1_dfm_eml_written_under_output`<br>`test_STEP1_1_dfm_eml_recipient_and_subject` (parsed with Python email)<br>`test_STEP1_1_eml_is_unsent_draft` (`X-Unsent: 1`) | [review] Open in a mail client: visible and editable |
| STEP1-2 | Every item marked with an R number; capability comes with a QM-021 section or LL-003 entry | `test_STEP1_2_spec_reader_reads_r01_to_r15`<br>`test_STEP1_2_item_without_r_id_rejected`<br>`test_STEP1_2_capability_without_source_rejected`<br>`test_STEP1_2_unknown_qm_section_rejected` (e.g. §13)<br>`test_STEP1_2_unknown_ll_id_rejected` | [review] Read the email and see whether the citations are reasonable |
| STEP1-3 | Every number has a traceable source; untraceable ones are written as `待工程師填寫` | `test_STEP1_3_number_not_in_cited_source_rejected`<br>`test_STEP1_3_pending_text_passes`<br>`test_STEP1_3_codes_not_treated_as_numbers` (`LPC-QM-021`, `MPO-12`, `G.657.A2`, `§4.1`)<br>`test_STEP1_3_both_ends_of_range_checked` (`3-9 weeks`: 9 has no source and must be an error)<br>`test_STEP1_3_thousand_separator_matches`<br>`test_STEP1_3_number_without_any_citation_rejected` | [machine] Pick 5 numbers at random from the email and find their sources in input yourself |
| STEP1-4 | B0 → change-impact eml, subject contains the ECR number, CH1–CH4 all present | `test_STEP1_4_ecr_reader_reads_b0_ch1_to_ch4`<br>`test_STEP1_4_missing_ch_rejected`<br>`test_STEP1_4_impact_eml_subject_has_ecr_no` | [review] Read the email and look at the judgement for each CH |
| STEP1-5 | C1 → CH1–CH3, no mention of a PO revision | `test_STEP1_5_ecr_reader_reads_c1_ch1_to_ch3_no_po_revision`<br>`test_STEP1_5_po_change_rejected_when_ecr_says_no_po_revision` | — |

## STEP 2 Engineering-release station　`tests/test_step2_release.py`
| From | VERIFY item | Automated tests | Beyond automated tests |
| --- | --- | --- | --- |
| STEP2-1 | Reviewed + customer decision → five documents, file names follow input | `test_STEP2_1_release_writes_five_files`<br>`test_STEP2_1_file_names_follow_input_pattern` (table E) | — |
| STEP2-2 | Customer decision not given → ask first, do not assume all accepted | `test_STEP2_2_prepare_refused_without_decisions` (the error message must mention the customer decision)<br>`test_STEP2_2_decide_records_each_item` | [live run] After DFM is reviewed in `/npi`, give no decision and see whether the manager asks |
| STEP2-3 | 24 channels, 127 µm, 8°, 800 ± 20 mm consistent across spec, BOM and drawing | `test_STEP2_3_key_params_same_in_spec_bom_drawing` (reads back the docx, xlsx and PDF text)<br>`test_STEP2_3_inconsistent_key_param_rejected` | — |
| STEP2-4 | BOM finished-product part number LPC-FA24-127-8A; all part numbers in MM-002, missing ones flagged | `test_STEP2_4_bom_top_level_part_number`<br>`test_STEP2_4_material_not_in_mm002_flagged` | — |
| STEP2-5 | The drawing PDF shows a simplified outline, main dimensions and a channel table | `test_STEP2_5_drawing_pdf_has_views_title_block_channel_table` (the PDF text has two view names, a title block and 24 channel rows) | [review] Open the PDF and look at the outline and annotations |
| STEP2-6 | The block STEP's length, width and height match the formal spec | `test_STEP2_6_block_step_bounding_box_matches_spec` (read back with cadquery, tolerance 0.01 mm) | [machine] Open and measure with FreeCAD or an online STEP viewer |
| STEP2-7 | B0: revision B0, 32 channels, MPO-16; what the ECR does not mention is unchanged | `test_STEP2_7_b0_rev_channels_connector`<br>`test_STEP2_7_fields_not_in_ecr_unchanged`<br>`test_STEP2_7_unrelated_field_change_rejected` | — |
| STEP2-8 | After B0 is produced the A0 files are still there, unchanged | `test_STEP2_8_previous_rev_files_unchanged` (hash compared before and after) | — |

## STEP 3 Costing station　`tests/test_step3_cost.py`
| From | VERIFY item | Automated tests | Beyond automated tests |
| --- | --- | --- | --- |
| STEP3-1 | Unit cost xlsx; every unit price can be found in the price list | `test_STEP3_1_unit_cost_xlsx_written`<br>`test_STEP3_1_each_price_matches_price_list_with_source`<br>`test_STEP3_1_price_break_chosen_by_quantity` (PLANS P13) | — |
| STEP3-2 | Not found → `待工程師填寫`, total marked incomplete | `test_STEP3_2_missing_price_pending_not_zero`<br>`test_STEP3_2_total_marked_incomplete` | [review] Open the xlsx and see whether the marking is clear |
| STEP3-3 | Hand calculation of one row, quantity × unit price, matches | `test_STEP3_3_line_cost_equals_qty_times_price`<br>`test_issue46_cost_sheet_material_row_formula` (pycel evaluates that row of the xlsx) | [machine] Pick a row and calculate by hand |

From PLANS: `test_PLANS_P14_non_material_elements_pending`

## STEP 4 PO check station　`tests/test_step4_po.py`
| From | VERIFY item | Automated tests | Beyond automated tests |
| --- | --- | --- | --- |
| STEP4-1 | A0 PO Rev 0: PO number, revision, part number, 2,000, USD 112.00, four delivery lots, compared with spec and cost | `test_STEP4_1_po_reader_kalvara_rev0` (four lots: 100, 400, 750, 750 and their dates)<br>`test_STEP4_1_report_lists_po_fields`<br>`test_STEP4_1_report_compares_spec_rev_and_unit_cost` | [review] Open the check result and see whether it is easy to read |
| STEP4-2 | Part number or revision mismatch → marked as a mismatch, pointing to the line and field | `test_STEP4_2_part_number_mismatch_names_line_and_field`<br>`test_STEP4_2_revision_mismatch_flagged` | — |
| STEP4-3 | Unit price below unit cost → flagged | `test_STEP4_3_price_below_unit_cost_flagged`<br>`test_STEP4_3_incomplete_cost_says_cannot_compare` (when the cost is incomplete it writes "無法比較" (cannot compare) and makes no judgement) | — |

## STEP 5 Supply-chain station　`tests/test_step5_supply.py`
| From | VERIFY item | Automated tests | Beyond automated tests |
| --- | --- | --- | --- |
| STEP5-1 | Material-preparation notice eml, subject contains NPI-26-097 and the PO number | `test_STEP5_1_material_preparation_eml_subject` | [review] Open in a mail client |
| STEP5-2 | One row per bought item; quantity × PO quantity matches | `test_STEP5_2_every_buy_item_listed`<br>`test_issue46_supply_email_quantities` (the requirement written in the email for every bought item)<br>`test_STEP5_2_requirement_equals_qty_per_unit_times_po_qty`<br>`test_STEP5_2_email_says_no_scrap_allowance` (PLANS P16) | [machine] Pick a row and calculate by hand |
| STEP5-3 | B0 → lists added, cancelled and changed quantities | `test_STEP5_3_change_notice_lists_added_removed_changed` (A0 BOM against B0 BOM) | — |
| STEP5-4 | C1 has no new PO → carries over the previous PO quantity and states which revision | `test_STEP5_4_c1_uses_previous_po_qty_and_names_revision` | — |

## STEP 6 Kalvara full flow　`tests/test_step6_full_chain.py`
| From | VERIFY item | Automated tests | Beyond automated tests |
| --- | --- | --- | --- |
| STEP6-1 | A0–C1 run, output of all four revisions present; nothing written into input | `test_STEP6_1_kalvara_a0_to_c1_all_outputs_exist` (fixture judgement files, approve at every station)<br>`test_STEP6_1_input_tree_unchanged` (hash compared before and after) | [live run] In Claude Code really run Kalvara A0 with `/npi`, reviewing every station yourself |
| STEP6-2 | Re-run one revision → same content, no duplicate files | `test_STEP6_2_rerender_same_content` (compares the content read back)<br>`test_STEP6_2_rerender_no_extra_files` | — |
| STEP6-3 | Open a new conversation and run the next station from files only | `test_STEP6_3_next_station_from_files_only` (a new process, given only the output folder) | [live run] Open a new conversation and run only the next station |
| STEP6-4 | List where each station differs from the answer file | `test_STEP6_4_compare_lists_differences` (deliberately change one BOM quantity; the list must show it)<br>`test_STEP6_4_compare_does_not_fail_on_differences` | [review] Read the difference list |

## STEP 7 Corvane exam (no automated tests; failed in Batch 1, re-taken in Batch 2 via STEP8-10)
| From | VERIFY item | Automated tests | Beyond automated tests |
| --- | --- | --- | --- |
| STEP7-1 | Corvane A0–C1 has output at every station and does not stop because of a different layout | — | [live run] Run Corvane from A0 to C1 with `/npi`, reviewing every station |
| STEP7-2 | Compare against Corvane's real documents and note the differences | — | [review] You compare; I record it in progress |

## STEP 8 fan-out engineering release (Batch 2)　`tests/test_step8_fanout.py`
Judgement content comes from the hand-written judgement files in `tests/fixtures/corvane/A0` and `B0` (PLANS P45); the Corvane A0 example: 36 fibres, 3 x MPO-12 APC, 36 x LC/APC, trunk 3.0 m +50 / 0 mm, legs 500 ± 20 mm (customer R-07 says ± 10, the DFM proposes ± 20, the customer's decision is "全部接受" (all accepted)), polarity Method A (the DFM's proposal for R-03), breakout box with the dimensions of `PP-FOB-36S`.

| From | VERIFY item | Automated tests | Beyond automated tests |
| --- | --- | --- | --- |
| STEP8-1 | Corvane A0 DFM reviewed, all accepted → five documents, drawing file name is fan-out; does not stop for lack of substrate, lid or pitch | `test_STEP8_1_corvane_release_writes_five_files`<br>`test_STEP8_1_file_names_follow_input_pattern` (`LPC-DWG-26104_RevA0_Fanout_Drawing.pdf`, and two STEP files for the breakout box and assembly; `Fanout` is inferred from the case folder name, unverified, see the undecided items in PLANS)<br>`test_STEP8_1_fanout_needs_no_fiber_array_params` (the judgement file has no pitch, substrate, lid or boot, and check reports no error) | — |
| STEP8-2 | The spec's key-parameter table has fan-out fields; no substrate, lid or pitch | `test_STEP8_2_spec_key_table_rows_are_fanout` (reads back the docx; the row names are exactly the fan-out rows, with no pitch / Substrate / Lid)<br>`test_STEP8_2_spec_key_values_from_customer_spec` (36, 3 x MPO-12 APC, 36 x LC/APC, 3.0 m, leg length and tolerance, breakout box L x W x H)<br>`test_STEP8_2_missing_fanout_param_rejected` (remove `box_h_mm` → the error message names it) | [review] Open the Corvane formal spec and look at the key-parameter table |
| STEP8-3 | The trunk tolerance +50 / 0 mm appears as-is in spec, BOM and drawing, not turned into ± 50 or ± 0 | `test_STEP8_3_tolerance_text_formats` (pure function: 10 / 10 → "± 10", 50 / 0 → "+50 / 0", 50 / 10 → "+50 / -10", PLANS P38)<br>`test_STEP8_3_asymmetric_tolerance_in_spec_bom_drawing` (all three have "+50 / 0" and none has "± 50" or "± 0")<br>`test_STEP8_3_spec_read_back_keeps_plus_and_minus` (reads back `trunk_tol_plus_mm` = 50, `trunk_tol_minus_mm` = 0) | — |
| STEP8-4 | The BOM names of the finished product and first-level assembly are fan-out; no Fibre array | `test_STEP8_4_bom_item0_item10_names_are_fanout` (item 0 contains Fan-out and 36; item 10 is "Fan-out box sub-assembly", PLANS P40)<br>`test_STEP8_4_no_fibre_array_text_in_fanout_outputs` (the spec, BOM and drawing text contain neither "Fibre array" nor "Fiber array") | — |
| STEP8-5 | The drawing shows the trunk, breakout box and legs, with trunk length, leg length and breakout-box dimensions, and a 36-row port map | `test_STEP8_5_drawing_has_trunk_box_legs_and_dims` (the PDF text has TRUNK, FAN-OUT BOX, LEGS, trunk length and tolerance, leg length and tolerance, breakout box L x W x H, NOT TO SCALE)<br>`test_STEP8_5_port_map_has_36_rows` | [review] Open the PDF and look at the outline, annotations and port map |
| STEP8-6 | The breakout-box STEP's length, width and height match the spec | `test_STEP8_6_box_step_bounding_box_matches_spec` (read back with cadquery, tolerance 0.01 mm) | [machine] Open the breakout-box STEP in a 3D viewer and measure |
| STEP8-7 | Unrecognised product type → error saying which type is not supported, not forced | `test_STEP8_7_unknown_product_type_rejected_names_type` (`Splitter` → the error message contains Splitter)<br>`test_STEP8_7_unknown_product_type_writes_no_files` (after render fails the station folder has no output documents) | — |
| STEP8-8 | Every parameter Corvane B0 changes maps to a CH; what the ECR does not mention is unchanged | `test_STEP8_8_corvane_b0_changed_params_map_to_ch` (the B0 fixture passes: legs 36 → 18, 500 → 1,000 mm, trunk 3.0 → 10.0 m, etc.)<br>`test_STEP8_8_change_without_ch_rejected` (remove the CH mapping of `leg_mm` → error)<br>`test_STEP8_8_unmentioned_params_unchanged` (fibre count 36, trunk connectors 3 x MPO-12, end face and polarity the same as A0) | — |
| STEP8-9 | After fan-out is added, Kalvara A0–C1 re-run gives the same output as Batch 1 | `test_STEP8_9_kalvara_a0_to_c1_same_as_batch1` (each station's `reviewed.json` and the drawing PDF text are the same as `tests/fixtures/kalvara/batch1_golden.json`, PLANS P46) | — |
| STEP8-10 | STEP 8 done → re-take the Corvane A0–C1 exam as in STEP 7, output at every station | — | [live run] Run Corvane from A0 to C1 with `/npi`, reviewing every station (PLANS P47: rename the old output first) |

From PLANS: `test_PLANS_P36_product_type_needs_citation` (no `product_type_sources`, or citing a source that does not exist → error), `test_PLANS_P36_ecr_cannot_change_product_type`, `test_PLANS_P39_port_map_method_a_and_b` (pure function: with Method B, MPO 1 position 1 connects to the last leg of group 1; with Method A, to the first; with duplex, two fibres per leg), `test_PLANS_P39_fibres_not_divisible_rejected` (36 fibres with 5 MPOs → error), `test_PLANS_P35_approve_refuses_edited_fanout_param` (change the trunk length in the docx and then approve → blocked), `test_PLANS_P44_compare_skips_fanout_params` (uses a fake answer-file dict and does not read the Corvane answer file)

## Old tests changed by Batch 3 (agreed by the user on 2026-11-01)
This batch deliberately changed dates, the BOM and the cost sheet, so the expectations of the old tests below change. They are listed per CLAUDE.md rule 6, and the user has agreed:
| Old test | Why it must change | Changed to |
| --- | --- | --- |
| `test_STEP8_9_kalvara_a0_to_c1_same_as_batch1` | VERIFY STEP12-1 explicitly excludes STEP8-9: this batch deliberately changed dates, worksheets and cost | Keep the Batch 1 baseline untouched; the test is changed to compare with P48's `batch2_golden.json`, excluding the fields of table K (this is `test_STEP12_1_kalvara_same_as_batch2_except_table_k`; the old one is removed) |
| `test_PLANS_P14_non_material_elements_pending` | P14 (only direct material calculated, other cost elements pending) is superseded by P69–P81 | Removed; replaced by the STEP 11 tests |
| `test_STEP3_*` (6 tests), `test_STEP0_7_edited_bom_qty_reaches_next_station`, `test_STEP4_3_price_below_unit_cost_flagged`, `test_STEP6_4_compare_lists_differences`, `test_issue13`, `test_issue15` | They read or edit the old BOM column name "Qty per FAU" and column positions, and the old cost-sheet layout (Summary rows 12–18); after P78 approve does not read Summary | The meaning of the assertions is unchanged (unit price can be found, pending is not treated as 0, quantity × unit price, an edited quantity reaches the next station, a unit price below cost is flagged, compare lists differences); only the column names and worksheets read or edited are swapped; the diff is shown to you first |
| `test_STEP2_4_material_not_in_mm002_flagged` | The item it adds has no `op`, parent level or category, and would be blocked once P64 and table H go live | Assertion unchanged (an item not in MM-002 is flagged); the added row gets an `op` and a category |
| All tests using `--date 2026-11-01` (`conftest.py` and 9 test files, 36 places in total) | 2026-11-01 is a Sunday, and P49 blocks weekends per VERIFY STEP9-4 | Only the input date is changed to `2026-11-02` (Monday), together with the file names in assertions that follow the date; no other assertion is changed |

## STEP 9 Common (Batch 3)　`tests/test_step9_common.py`
Kalvara date example: A0 draft spec 2026-06-29 (Monday); per table F: DFM reply date 2026-07-02, customer agreement 2026-07-08, spec release date 2026-07-15… (the actual numbers are computed by the pure function in the tests and are not hard-coded here).

| From | VERIFY item | Automated tests | Beyond automated tests |
| --- | --- | --- | --- |
| STEP9-1 | The A0 timeline's four events each have a date and basis; none is the day it is run | `test_STEP9_1_a0_timeline_has_events_and_basis` (DFM reply date, spec release date, cost-to-finance date and material-preparation notice date all have dates; the basis gives the customer document or which segment of §2)<br>`test_STEP9_1_a0_timeline_counts_working_days` (pure function: derivation from 2026-06-29 per table F)<br>`test_STEP9_1_no_date_is_today` (run the five A0 stations without `--date`; no output date equals the day it is run) | [live run] Hand the A0 draft spec to `/npi` and see whether the manager gives you the timeline |
| STEP9-2 | The B0 timeline has the impact assessment date; intervals the ECR does not give say "沿用初版" (carried over from the initial revision) | `test_STEP9_2_b0_timeline_has_impact_assessment`<br>`test_STEP9_2_ecr_gaps_basis_says_reused_from_initial` | — |
| STEP9-3 | The date of every output equals the timeline; email file-name date = Date, 10:00 +0800 | `test_STEP9_3_each_output_date_matches_timeline` (DFM eml, spec docx, BOM xlsx, drawing PDF text, cost xlsx, material-preparation eml)<br>`test_STEP9_3_eml_file_date_equals_header_date_10am` | [machine] Open the A0 email and spec and look at the dates |
| STEP9-4 | Not a weekend; a later event is not earlier than the one before | `test_STEP9_4_working_days_skip_weekend` (pure function: Friday + 1 = next Monday)<br>`test_STEP9_4_events_in_order` (the timelines of A0–C1 are all in order, including C1 minor change with costing and material preparation on the same day)<br>`test_STEP9_4_weekend_override_rejected` (specify 2026-11-01 → error, P49) | — |
| STEP9-5 | Change the spec release date → later stations use the new date, reviewed ones do not change | `test_STEP9_5_override_moves_later_events`<br>`test_STEP9_5_reviewed_station_date_unchanged` (change the spec release date after DFM is reviewed; the dates in the DFM eml and in state do not change) | [live run] While reviewing DFM tell the manager to change the spec release date, and look at the engineering-release dates |
| STEP9-6 | After the run, list the dates where the timeline differs from the answer file's timeline; not a failure | `test_STEP9_6_compare_lists_timeline_differences` (Kalvara A0–C1; differences are only listed, and it returns success) | — |
| STEP9-7 | The finished-product suffix letter of B0 and C1 differs from the previous revision and is written to the registry | `test_STEP9_7_suffix_must_change_from_previous_rev` (the B0 fixture with the part number changed back to A0's suffix → error)<br>`test_STEP9_7_minor_rev_also_changes_suffix` (C1)<br>`test_STEP9_7_render_registers_product_pn` | — |
| STEP9-8 | Re-run the same revision: same part number, no extra registry entry | `test_STEP9_8_rerender_same_pn_no_new_entry` | — |
| STEP9-9 | Number already in the registry or material master → error naming the number | `test_STEP9_9_pn_used_by_other_rev_rejected`<br>`test_STEP9_9_pn_in_mm002_or_ll003_rejected` (uses LL-003's `LPC-FA08-127-8A`) | — |
| STEP9-10 | The A0 registry has the master-data numbers and not the quotation number that only appears at B0 | `test_STEP9_10_registry_seeded_from_master_data` (has `PO-L26-0612`, `LPC-FA08-127-8A`)<br>`test_STEP9_10_quote_number_hidden_before_its_date` (with only A0 intaken, the registry file does not contain `LPC-Q-26-0391`; it appears only after the B0 ECR is intaken) | — |
| STEP9-11 | Citing the operating rules must point to a single value where the same number can be found | `test_STEP9_11_rules_sources_hold_one_value` (the original text of `RULES §3 工作站費率 FPR` has only 22, not 55)<br>`test_STEP9_11_cited_rule_number_accepted` | — |
| STEP9-12 | Citing FPR but writing 55, or citing a section that does not exist → error | `test_STEP9_12_wrong_number_for_cited_rule_rejected`<br>`test_STEP9_12_unknown_rule_section_rejected` (`RULES §9 …`) | — |
| STEP9-13 | Range values state the chosen value and its basis | `test_STEP9_13_value_inside_range_accepted` (cost lot size 1,000 citing 500–1,500)<br>`test_STEP9_13_value_outside_range_rejected` (2,000 → the error message prints the range)<br>`test_STEP9_13_chosen_value_and_basis_in_output` (the basis column of Parameters, the set-up time basis in Routing) | — |
| STEP9-14 | C1 minor change, B0 and C0 major change, basis citing the ECR | `test_STEP9_14_revision_kind_from_fixture` (B0, C0 major, C1 minor, all with sources)<br>`test_STEP9_14_minor_without_no_po_revision_rejected` (B0 judged minor → error)<br>`test_STEP9_14_a0_is_initial` | — |
| STEP9-15 | Every station lists its pending items, with the same count as in the documents | `test_STEP9_15_pending_items_have_location` (xlsx items have worksheet and cell)<br>`test_STEP9_15_pending_count_matches_documents` (number of list entries = number of times `待工程師填寫` appears in the output documents) | [live run] Run one station with `/npi` and see whether the reported pending list can be located |

From PLANS: `test_PLANS_P51_minor_ecr_cost_and_supply_next_day` (C1 minor change: cost-to-finance date and material-preparation notice date are both spec release date + 1 working day), `test_PLANS_P50_po_date_only_after_intake` (with only the A0 draft spec intaken, PO receipt is derived; after the PO is intaken the PO date is used instead), `test_PLANS_P52_date_option_means_engineer_override` (`--date` is written into the timeline with the basis "工程師指定" (specified by the engineer)), `test_PLANS_P52_rerender_keeps_date`, `test_PLANS_P56_mm002_codes_always_used`, `test_PLANS_P60_tell_adds_eng_source` (after `tell`, `ENG-1` is a source; a number citing `ENG-1` passes), `test_PLANS_P60_tell_refused_after_review`, `test_PLANS_P68_people_json_matches_rules` (the sender and SCM in `config/people.json` are the same as operating rules §1)

## STEP 10 BOM (Batch 3)　`tests/test_step10_bom.py`
| From | VERIFY item | Automated tests | Beyond automated tests |
| --- | --- | --- | --- |
| STEP10-1 | A0 has 4 worksheets, 5 from B0 onwards | `test_STEP10_1_a0_bom_has_four_sheets` (BOM, Channel Map, Routing, Revision)<br>`test_STEP10_1_b0_bom_has_change_summary` | [machine] Open the A0 and B0 BOMs in Numbers |
| STEP10-2 | Levels 0 / 1 / 2, written like 10.10; every row has category and the other columns, category not blank | `test_STEP10_2_level_from_item_number` (pure function: `0`→0, `10`→1, `10.10`→2, `10.10.10`→error)<br>`test_STEP10_2_every_row_has_required_columns`<br>`test_STEP10_2_blank_category_rejected` | — |
| STEP10-3 | Category per the 3-4 mapping table | `test_STEP10_3_category_from_mm002` (pure function per table H, one example per row: `CM-EP-UV365`→RM, `PP-CAP-FA24`→PKG, Raw Material→RM, Packaging→PKG)<br>`test_STEP10_3_new_material_code_needs_cited_category` | — |
| STEP10-4 | Level-2 extended quantity = own quantity × parent quantity | `test_STEP10_4_extended_qty_formula` (pycel recalculates the xlsx; change the parent quantity to 2 → the extended quantity follows) | — |
| STEP10-5 | Channel Map has 24 rows and its columns, check cell OK; one row missing → not OK | `test_STEP10_5_a0_channel_map_24_rows_ok`<br>`test_STEP10_5_missing_row_check_not_ok` (delete one row of `channel_map` in the judgement file → render succeeds, and after pycel recalculation the check cell is CHECK)<br>`test_STEP10_5_mpo_position_from_connector` (pure function: with MPO-12, channel 13 is MPO 2 position 1) | — |
| STEP10-6 | A0 Routing in §4 sequence; set-up has a basis; run time pending | `test_STEP10_6_base_sequence_required` (POL missing → error)<br>`test_STEP10_6_default_routing_run_time_pending` (A0 without `engineer.json`: every run time is pending, set-up time 20, basis `RULES §4 整備時間`)<br>`test_STEP10_6_setup_must_be_20_unless_engineer` (25 citing RULES → error; 25 citing `ENG-n` passes, 35 is an error)<br>`test_STEP10_6_run_time_needs_source_or_pending` (4 written with no source → error) | — |
| STEP10-7 | B0 has PMA; C0 has pre-bake, outsourced coating, incoming inspection | `test_STEP10_7_pm_adds_two_pma_ops`<br>`test_STEP10_7_coating_needs_prebake_coating_incoming` (any of the three `kinds` missing is an error; outsourced coating and incoming inspection written in the same `SUB` operation also counts)<br>`test_STEP10_7_unknown_work_centre_rejected` | — |
| STEP10-8 | The operation in each BOM remark can be found in the Routing | `test_STEP10_8_bom_op_must_exist_in_routing` | — |
| STEP10-9 | B0 Change Summary lists additions, removals and changes, each mapped to a CH | `test_STEP10_9_change_summary_lists_bom_and_routing_diffs`<br>`test_issue41_change_summary_complete` (BOM rows equal a diff computed separately from the two BOM sheets, including a quantity change) (including the Make row `LPC-FA24-110 → LPC-FA32-110`, P66)<br>`test_STEP10_9_diff_without_ch_rejected` | [machine] Compare the A0 and B0 BOMs by hand against the Change Summary |
| STEP10-10 | B0 Revision has two rows, A0 and B0, with all columns | `test_STEP10_10_revision_rows_carry_previous` (the date is each one's own spec release date; prepared by Alex Lin, approved by Jessica Liao) | — |
| STEP10-11 | State a run time in the conversation → that BOM cell changes and the cost sheet uses it too | `test_STEP10_11_tell_run_time_reaches_bom_and_cost` (`tell` → edit the judgement file → render → approve → the time in the costing facts is the new one) | [live run] While reviewing the BOM in `/npi`, give a run time verbally |

From PLANS: `test_PLANS_P61_fixture_parent_qty_is_one` (the check in step 1 of STEP 10 written as a test), `test_PLANS_P61_level2_without_parent_rejected`, `test_PLANS_P82_group_row_category` (item 60 has category PKG and Make/Buy Make, and does not enter material cost), `test_PLANS_P61_no_fau_in_bom_headers`, `test_PLANS_P65_fanout_channel_map_is_port_map` (Corvane A0, 36 rows), `test_PLANS_P63_rel_not_in_routing`

## STEP 11 Unit cost sheet (Batch 3)　`tests/test_step11_cost.py`
Tests that exercise the full calculation first run `tell` the way an engineer would, then change the pending cells of the judgement file to cite `ENG-n` (run time 5 minutes, pending quantity 0.1, scrap rate 0.1; these numbers are chosen by the tests themselves, not taken from the answer file; PLANS P83 change log); tests that do not run `tell` see pending values.

| From | VERIFY item | Automated tests | Beyond automated tests |
| --- | --- | --- | --- |
| STEP11-1 | A0 has 7 worksheets, 8 from B0 onwards (Delta vs A0) | `test_STEP11_1_a0_cost_has_seven_sheets`<br>`test_STEP11_1_b0_cost_has_delta_vs_a0` | — |
| STEP11-2 | Recalculation gives no error values; formulas > 100; total cost = the program's value | `test_STEP11_2_recalc_no_errors` (pycel)<br>`test_STEP11_2_more_than_100_formulas`<br>`test_STEP11_2_total_equals_costing_function` (difference < 0.005) | [machine] Open in Numbers and look for error values |
| STEP11-3 | Pending cell left empty with pending written next to it, Summary incomplete, no errors | `test_STEP11_3_pending_input_blank_with_status`<br>`test_STEP11_3_pending_makes_total_incomplete_no_error` (pycel recalculation: the total cost and quote cells are "不完整" (incomplete), with no error values) | — |
| STEP11-4 | Parameters has seven parameters with their basis | `test_STEP11_4_parameters_values_and_basis` (the basis of 3 %, 22 %, 8 %, 30 % and 0.50 is `RULES §3 …`) | — |
| STEP11-5 | Scrap rate per 3-5; 24 channels and 32 channels + PM are pending with candidates listed | `test_STEP11_5_scrap_rate_table_j` (pure function, one example per row: fan-out → 5 %; 12 channels → 8 %; 24 channels → pending; 32 channels + PM → pending, candidates include at least "32–48 通道陣列" (32–48 channel array) and "PM 陣列" (PM array) (table J: with PM both PM rows match, so there are three rows))<br>`test_STEP11_5_pending_scrap_lists_candidates_in_basis`<br>`test_STEP11_5_pm_always_two_candidates` (16 channels + PM → pending, candidates 12 %, 14 %)<br>`test_STEP11_5_override_must_be_candidate_or_eng` (override to 10 % citing `RULES §3 報廢率 32–48 通道陣列` when it is not a candidate → error; citing `ENG-n` passes) | — |
| STEP11-6 | Material: quantity × price break, category subtotals | `test_STEP11_6_material_line_and_subtotals`<br>`test_STEP11_6_price_break_by_costing_qty` (carried over from P13) | — |
| STEP11-7 | Fibre arrays have SV-REL-LOT ÷ cost lot size; C0 has SV-ARC-1310 | `test_STEP11_7_lot_qualification_per_pc`<br>`test_STEP11_7_coating_service_with_minimum_charge` (pure function: at lot size 100, per piece = 480 ÷ 100) | — |
| STEP11-8 | Conversion (set-up ÷ lot size + run) × rate, operations same as the BOM | `test_STEP11_8_conversion_formula`<br>`test_STEP11_8_ops_same_as_reviewed_routing`<br>`test_STEP11_8_sub_op_not_in_conversion` | — |
| STEP11-9 | Rates the same as §3 | `test_STEP11_9_rates_equal_rules_table` (13 work stations) | — |
| STEP11-10 | Summary adds item by item to total cost; quote rounding, margin, NRE, comparison with target price | `test_STEP11_10_summary_order_table_i`<br>`test_STEP11_10_quote_rounds_up_to_half` (pure function: 101.01 → 101.50)<br>`test_STEP11_10_target_price_compared` (A0 USD 105.00 citing R-14) | [review] Open Summary and see whether the order and marking are clear |
| STEP11-11 | Change a packaging unit price; the scrap row does not change | `test_STEP11_11_packaging_not_in_scrap_base` | — |
| STEP11-12 | Four NRE rows; pending when not found; ECR NRE from B0 onwards | `test_STEP11_12_a0_nre_four_rows`<br>`test_STEP11_12_ecr_nre_required_from_b0`<br>`test_STEP11_12_nre_amount_needs_source_or_pending` | — |
| STEP11-13 | B0 Delta split across CHs, parameter change on a separate row, sum = total difference, check cell OK | `test_STEP11_13_delta_rows_sum_to_total` (pure function)<br>`test_STEP11_13_parameter_change_row` (change only the cost lot size → only the parameter-change row has a difference)<br>`test_STEP11_13_delta_check_cell_ok` (pycel) | — |
| STEP11-14 | C1 minor change: cost changes, quote carried over, margin before and after visible | `test_STEP11_14_minor_keeps_previous_quote`<br>`test_STEP11_14_margin_before_and_after` | — |
| STEP11-15 | Approval: prepared by and date; review and finance confirmation to be confirmed | `test_STEP11_15_approval_rows` | — |
| STEP11-16 | Change the cost lot size in the conversation → the PO check uses the recalculated unit cost | `test_STEP11_16_tell_lot_size_reaches_po_check` | [live run] While reviewing the cost sheet in `/npi`, change the cost lot size verbally |

From PLANS: `test_PLANS_P72_prev_quote_source_for_ecr` (`PREV quote` is a new source, agreed by the user on 2026-11-01), `test_PLANS_P78_read_back_recomputes_from_inputs` (change a unit price directly in the xlsx and then approve; `total` follows), `test_PLANS_P79_pycel_supports_used_functions`, `test_PLANS_P73_fanout_has_no_lot_qualification` (Corvane A0), `test_PLANS_P81_parameter_change_computed_first`

## STEP 12 Batch 3 re-exam　`tests/test_step12_rerun.py`
| From | VERIFY item | Automated tests | Beyond automated tests |
| --- | --- | --- | --- |
| STEP12-1 | Kalvara A0–C1 re-run, the checks of the first two batches all pass (except STEP8-9), cost differences from the answer file listed | `test_STEP12_1_kalvara_same_as_batch2_except_table_k` (P48, table K)<br>`test_STEP12_1_compare_lists_cost_differences` (total cost, quote, scrap rate; list only) | — |
| STEP12-2 | Corvane re-run: worksheet counts, fan-out cable operations, 5 %, no lot qualification, no FAU | `test_STEP12_2_corvane_a0_fixture_bom_and_cost` (A0 verified automatically once first with P80's fixture) | [live run] Run Corvane from A0 to C1 with `/npi`, reviewing every station (step 2 of STEP 12: rename the old output first) |
| STEP12-3 | After the exam compare with Corvane's real BOM and cost sheet and note the differences | — | [review] You compare with the real documents; the differences are recorded in progress |

## Issue regression tests　`tests/test_issues.py`
From supplementary (progress.md Issues #1–#17, found by the live trial run and read-only review on 2026-11-01; **awaiting user review**):
`test_issue1_master_readers_skip_footnote_rows`, `test_issue2_po_before_spec_keeps_station_order`, `test_issue3_render_refused_when_upstream_reopened`, `test_issue4_approve_refuses_edited_spec_param`, `test_issue5_kit_rejected`, `test_issue6_missing_file_is_npi_error`, `test_issue7_date_parts_not_available_numbers`, `test_issue8_mentioned_codes_must_exist` (5 parameters, 5 tests in total), `test_issue9_title_and_po_change_checked`, `test_issue9_bom_remark_and_section_title_checked`, `test_issue10_intake_reports_chinese_kind`, `test_issue11_compare_includes_dfm`, `test_issue12_unknown_cust_rev_reported`, `test_issue13_cost_facts_include_latest_po`, `test_issue14_po_folder_non_pdf_rejected`, `test_issue15_price_break_boundary` (#14 and #15 were not caught by mutation testing), `test_issue16_letter_prefixed_numbers_checked`, `test_issue17_previous_release_sources_are_per_field` (#16 and #17 are the tightening of table D approved by the user)

From supplementary (issue #19, found in the STEP8-10 re-exam; **awaiting user review**): `test_issue19_corvane_po_header_layout` (Corvane PO Rev 0 yields the PO number, revision, date, 3,000 EA and four lots 50 / 950 / 1,000 / 1,000; the PO number and revision are also read from the "CHANGE ORDER" header of Rev 1 and Rev 2)

From supplementary (issue #21, found in the STEP8-10 re-exam; **awaiting user review**): `test_issue21_pending_part_number_not_used_as_part_number` (a row whose part number is pending does not create a `PREV BOM` source and is not counted as added / cancelled; it is listed separately as `pending_pn`)

From supplementary (issues #22–#26, not caught by Batch 2 mutation testing; **awaiting user review**): `test_issue22_fibres_per_mpo_must_split_into_legs`, `test_issue23_unknown_polarity_rejected`, `test_issue24_text_param_change_needs_ch`, `test_issue25_fanout_text_channel_count_not_checked`, `test_issue26_corvane_guard_patterns` (in `tests/test_step0_manager.py`)

From supplementary (issue #27, Batch 2 read-only review; **awaiting user review**): `test_issue27_unknown_key_table_type_reported` (the first row of the spec key-parameter table is not recognised → reports "認不出是哪種產品" (cannot tell which product this is))

From supplementary (issue #45, read-only review of 2026-11-23; **awaiting user review**): `test_issue45_manager_relays_document_kind` (step 1 of `.claude/commands/npi.md` tells the manager to relay the document kind from the line `intake` prints; this only checks the instruction is there — whether the manager actually says it is seen in step 1 of the live run, STEP0-1).

From supplementary (issues #41, #46, read-only review of 2026-11-23; **awaiting user review**): `test_issue41_change_summary_complete` (Change Summary BOM rows equal a diff computed separately from the A0 and B0 BOM sheets, with one quantity change made in the test data, each with a CH), `test_issue46_cost_sheet_material_row_formula` (pycel value of the PP-MPO12-APC-F row in the cost sheet = 2 × 5.2), `test_issue46_supply_email_quantities` (every bought item's requirement in the material-preparation email = qty per unit × 2,000).

From supplementary (issue #47, first real-use run NPI-26-124 on 2026-11-24; **awaiting user review**): `test_issue47_spec_part_no_label` (a draft spec whose part-number label is "Part no." instead of "<customer> P/N" is read, and the part number is returned).

From PLANS P96, P97 (decided on the user's delegation 2026-11-24; **awaiting user review**): `test_P96_dfm_raises_direction_without_reference` (the DFM agent instructions contain the direction / position rule with risk Medium), `test_P97_cost_general_lot_is_500` (the cost agent instructions fix the general lot at 500).

From supplementary (issue #48, found in the 2026-11-01 live run, fix drafted 2026-11-24; reviewed by the user 2026-11-24): `test_issue48_reopen_moves_old_results_out_of_station_folder` (after `reopen`, the station folder has no `reviewed.json`, `facts.json` or `*.reopened.json`; the old content is in `_reopened/<station>_1/`; a second reopen of the same station creates `_2` and leaves `_1` byte-identical).

## Development checks (PLANS S5, S6)　`tests/test_dev_checks.py`
From PLANS (S5, S6 are development tools, not VERIFY items; reviewed by the user 2026-11-24). Each test builds its own small table or toy project in a temporary folder, so they do not depend on the current progress.md, except the last test of each group.
| From | What it guards | Automated test |
| --- | --- | --- |
| PLANS S5 | A row with two dates and an empty check column is reported, naming the row | `test_S5_two_dates_without_check_blocked` |
| PLANS S5 | A row with one date and no check passes | `test_S5_one_date_without_check_passes` |
| PLANS S5 | A named check that does not exist (no such test function or file) is reported; an existing one passes | `test_S5_named_check_must_exist` |
| PLANS S5 | `文字規則：` with a location in backticks (an existing file) and a reason passes; `文字規則：` alone is reported | `test_S5_text_rule_needs_reason` |
| PLANS S5 | A row without any date, or a table whose header differs, is reported (not silently skipped) | `test_S5_malformed_rows_reported` |
| PLANS S5 | The real progress.md passes | `test_S5_repo_progress_passes` |
| PLANS S6 | A mutation the toy test catches is reported as caught | `test_S6_caught_when_tests_fail` |
| PLANS S6 | A mutation the toy test misses is reported as not caught and the run exits 1 | `test_S6_survived_when_tests_pass` |
| PLANS S6 | Text that occurs 0 or 2 times is an error and the file is untouched | `test_S6_find_must_be_unique` |
| PLANS S6 | The file is byte-identical afterwards, also when pytest itself errors | `test_S6_file_restored` |
| PLANS S6 | Every entry of the real `mutations.json` finds its text exactly once (stale entries fail here, not at gate time) | `test_S6_repo_mutations_resolve` |

From supplementary (issues #49, #50, STEP check of this batch; **awaiting user review**): `test_issue49_self_check_test_excluded` (a toy `test_S6_repo_mutations_resolve` that fails whenever the mutated text is gone does not turn a harmless mutation into caught), `test_issue50_pytest_error_reported_as_error` (a missing test file gives error, not caught).

From supplementary (issues #51–#59, read-only review of this batch, entry 93; **awaiting user review**): `test_issue51_separator_required`, `test_issue52_every_date_item_checked`, `test_issue53_only_tests_and_check_files_count`, `test_issue54_text_rule_needs_location_and_reason`, `test_issue55_baseline_must_pass`, `test_issue56_no_bytecode_from_mutated_source` (removes the caller's `PYTHONDONTWRITEBYTECODE` first), `test_issue57_target_must_be_inside_project_not_input` (2 cases), `test_issue59_main_exit_codes` in `tests/test_dev_checks.py`; `test_issue58_reopen_moves_downstream_and_later_revisions` in `tests/test_issues.py`.

From supplementary (issues #61–#63, mutations not caught, entry 95; **awaiting user review**): `test_issue61_collection_error_after_mutation_is_error`, `test_issue62_missing_check_file_reported`, `test_issue63_existing_targets_outside_or_input_refused`. Also changed with the user's P100 decision: `test_issue58` checks which files moved instead of counting 2 json files.

From supplementary (issues #64, #65, #67, second read-only review, entry 96; **awaiting user review**): `test_issue64_check_file_outside_project_refused`, `test_issue65_input_any_case_refused`, `test_issue67_impossible_date_refused`; `test_issue66_reopen_moves_subfolders` in `tests/test_issues.py`.

Old test changed (CLAUDE.md rule 6; the user agreed on 2026-11-24): `test_S5_text_rule_needs_reason` now writes the location in backticks (`文字規則：`CLAUDE.md` rule 11; …`) and creates CLAUDE.md in its temporary folder, as issue #54 requires.

From supplementary (issue #60, P100 scope decided by the user 2026-11-24): `test_issue60_reopen_keeps_only_engineer_words` (after reopen the station folder holds only `engineer.json`, unchanged; reviewed, facts, judgement and the rendered file are in `_reopened/dfm_1/`).

Evidence beyond pytest (recorded in progress, not automated): a commit with a two-date, no-check row is blocked by pre-commit; the 6 seeded mutations run with `check_mutations.py` are all caught and `git status` is clean afterwards.

## Checks beyond the automated tests
On 2026-11-23 the 15 items formerly under "must be tested by hand" (37 VERIFY items) were split into three piles. The tag at the start of each cell in the "Beyond automated tests" column of the tables:
- [machine] nobody does it by hand; it is guarded by the automated tests (they fail and block the commit); the `check_quality.py` table is only evidence attached to the report and blocks nothing; the cell keeps the original manual action.
- [live run] the live smoke run at the batch gate (CLAUDE.md rule 9 (4)), done by Claude following the script below.
- [review] done by the user (CLAUDE.md rule 9 (5)).

### 1. Guarded by machine (9 items)
| Item | Original manual action | What guards it now |
| --- | --- | --- |
| STEP1-3 | Pick 5 numbers from the DFM email and trace their sources | `number_errors` in `npi/sources.py`: `dfm.check` blocks before every render; `test_STEP1_3_*` |
| STEP2-6 | Measure the block STEP in a 3D viewer | `test_STEP2_6_block_step_bounding_box_matches_spec` (reads back the STEP and measures the bounding box) |
| STEP3-3 | Pick a row and calculate quantity × unit price by hand | `test_STEP3_3_line_cost_equals_qty_times_price`; `test_issue46_cost_sheet_material_row_formula` (the row formula in the xlsx) |
| STEP5-2 | Pick a row and calculate quantity × PO quantity by hand | `test_STEP5_2_requirement_equals_qty_per_unit_times_po_qty`; `test_issue46_supply_email_quantities` (the quantities in the email) |
| STEP8-6 | Measure the breakout-box STEP in a 3D viewer | `test_STEP8_6_box_step_bounding_box_matches_spec` |
| STEP10-9 | Compare the A0 and B0 BOMs by hand against the Change Summary | `test_STEP10_9_change_summary_lists_bom_and_routing_diffs`; `test_issue41_change_summary_complete` (completeness) |
| STEP9-3 | Open the email and spec and look at the dates | `test_STEP9_3_*` (the "信件日期" (email dates) row of `check_quality.py` is evidence only) |
| STEP10-1 | Open in Numbers and count the worksheets | `test_STEP10_1_*` count the worksheets (the "BOM：工作表" (BOM: worksheets) row of `check_quality.py` is evidence only); opening in Numbers moved to review action 3 |
| STEP11-2 | Open in Numbers and look for error values | `test_STEP11_2_*` (pycel recalculation; the "成本表：公式格數" (cost sheet: formula cells) and "成本表：重算錯誤" (cost sheet: recalculation errors) rows of `check_quality.py` are evidence only); opening in Numbers moved to review action 3 |

The first 6 items are computed by the program. On 2026-11-23 each of these 6 calculations was deliberately broken once and the corresponding tests all failed (progress entry 67), so they are no longer calculated by hand separately. When these places are changed later, include them in the mutation testing of rule 5.

### 2. Live-run script (15 items)
First rename `output/NPI-26-097` (rename only, do not delete). Open a clean session (working folder is the project root), send one line at a time, and only look at the result and send the next line after its turn has ended. The clean session is opened from the command line: the first line with `claude -p "<line>" --output-format json --allowedTools "Bash,Read,Write,Edit,Agent,Task,Glob,Grep"`, and every later line adds `--resume <the session_id returned by the previous line>`; the returned `result` is the manager's reply. For each step record: what the manager replied (excerpt of the original text), the result of `status`, and the files produced. The scripted `可以` does not look at the content or fill in pending values, so the live run only verifies the flow; for content see the `check_quality.py output` table and the user's review list. The numbers for STEP11-16, "the next station uses the recalculated unit cost", are only visible once the cost sheet is completely filled in; the live run only verifies that the verbally changed value reaches the cost sheet and that the PO check reads the same cost; the numbers are verified by `test_STEP11_16_*` with a fully filled fixture.

| Step | Line sent to the manager | Items verified | Evidence |
| --- | --- | --- | --- |
| 1 | `/npi input/NPI-26-097_CPO_Fiber_Array/A0/01_Customer_Draft_Spec/KVP-SPC-2408_RevX1_Fiber_Array_Draft_Spec.docx` | STEP0-1, 9-1, 9-15 | The reply has NPI-26-097, A0, draft spec, and the timeline (each event with a date and basis); `status` shows dfm pending review and the other stations not run; the number of pending items listed in the reply equals the number of times 「待工程師填寫」 appears in the DFM email, counted separately by opening the .eml with python (not with `npi.pending`, which the manager's list itself comes from) |
| 2 | `可以` ("OK"; no customer decision given) | STEP0-6, 2-2 | dfm reviewed; the reply asks whether the customer accepts each R; release still not run |
| 3 | `全部接受，沒有附帶條件。規格發行日改成 2026-07-14。` ("All accepted, no conditions. Change the spec release date to 2026-07-14.") | STEP9-5 | release pending review; the date on the formal spec and BOM is 2026-07-14; the date of the DFM email is unchanged |
| 4 | `Op 30 單件時間 11 分鐘` ("Op 30 run time 11 minutes") | STEP10-11 | Operation 30 of the BOM Routing is 11 with basis `ENG-n`; release still pending review |
| 5 | Claude changes the quantity of one bought row of the BOM with a tool, then sends `可以` | STEP0-7, 10-11 | That row in cost's `facts.json` has the changed quantity and Op 30 is 11; cost pending review |
| 6 | No reply; end this session; open another clean session and send `/npi status NPI-26-097` | STEP0-8, 6-3 | The reply says cost is pending review and carries on waiting for review; the modification times of dfm's and release's `judgement.json` are unchanged (not re-run) |
| 7 | `成本批量改成 ○` ("Change the cost lot size to ○"; ○ is a quantity different from the one on the cost sheet, decided after looking at the cost sheet during the run) | STEP11-16 | The cost lot size in the cost sheet's Parameters is the new value, with `ENG-n` added to the basis |
| 8 | `可以` | STEP0-6 | cost reviewed; the reply says "等下一份客戶文件" (waiting for the next customer document) |
| 9 | `/npi input/NPI-26-097_CPO_Fiber_Array/A0/05_Customer_PO/KVP-PO-7700-2614_Rev0.pdf` | STEP11-16 | po pending review; the unit cost written in the PO check result is consistent with the cost sheet (while the cost sheet still has pending values, both say "不完整" (incomplete) and the PO check writes "無法比較" (cannot compare)) |
| 10 | `可以`, and `可以` again after supply produces its output | STEP6-1 | All five A0 stations reviewed; `git status input/` shows no changes; the `check_quality.py output` table |

The Corvane re-exam (STEP7-1, 8-10, 12-2) is only done in batches where PLANS has a re-exam STEP: first rename `output/NPI-26-104`, open a clean session in the same way, run from Corvane's A0 customer document to C1, sending `可以` at every station and `全部接受` ("all accepted") as the customer decision. The evidence is that every station has output, plus the NPI-26-104 columns of `check_quality.py output`; the five items of STEP12-2 (worksheet counts, fan-out cable operations, 5 %, no lot qualification, no FAU) are checked on the output files with commands.

### 3. For the user to review (13 items, 8 actions)
In each batch only look at the documents changed in that batch, using the copy produced by the live run; how to settle the list: see CLAUDE.md rule 9 (5).
1. DFM reply email, change-impact email: open in a mail client, visible and editable; whether the citations are reasonable; the judgement for each CH (STEP1-1, 1-2, 1-4).
2. Drawing PDF: outline, annotations, channel table; for fan-out the trunk, breakout box, legs and port map (STEP2-5, 8-5).
3. BOM and unit cost sheet: open both in Numbers and see that they open without error values (STEP10-1, 11-2); whether the marking of pending and "不完整" (incomplete) is clear; the order and marking of Summary (STEP3-2, 11-10).
4. Whether the PO check result is easy to read (STEP4-1).
5. Material-preparation notice email: open in a mail client (STEP5-1).
6. The list of differences from the answer file (STEP6-4).
7. The key-parameter table of the Corvane formal spec (STEP8-2).
8. Compare against Corvane's real documents and tell Claude the differences to record in progress (STEP7-2, 12-3). Only the user can do this: the development side must not read Corvane's our-side documents.
