# Stage 1c — Transfer Verification Report

**Generated:** 2025-02-26  
**Source database:** `database/catalog.db`  
**Script:** `scripts/1c_verify_transfers.py`  
**Scope:** `O:/Master 1–4` (Discovery tape .mov files) + `O:/MPEG-2` (LTO proxy .mpg files)

> Placeholder files ("not missing — doesn't exist", "MISSING") are completely
> ignored — they represent tapes that never existed and are excluded from all
> scans and counts.

---

## Summary

| Metric                                     | Count                     |
| ------------------------------------------ | ------------------------- |
| Total files scanned                        | 972                       |
| Video files                                | 964 (287 .mov + 677 .mpg) |
| **Resolved** to film_rolls                 | 942 files → 2,433 reels   |
| Unresolved Master tapes (no transfer link) | 195                       |
| Unmatched MPEG-2 files                     | 30                        |
| Tapes in DB but not on disk                | 101                       |
| `has_transfer_on_disk = 1`                 | 2,433 / 43,269 (5.6%)     |

### Storage

| Category                | Size         |
| ----------------------- | ------------ |
| Resolved Master tapes   | ~65.5 TB     |
| Unresolved Master tapes | ~14.1 TB     |
| Matched MPEG-2 files    | ~1.2 TB      |
| Unmatched MPEG-2 files  | ~0.5 TB      |
| **Total on disk**       | **~81.3 TB** |

### Match Rules

| Rule                      | Matches   | Files   | Reels     |
| ------------------------- | --------- | ------- | --------- |
| `tape_number`             | 431       | 93      | 427       |
| `tape_number_no_transfer` | 195       | 195     | 0         |
| `mpeg2_lto`               | 1,904     | 390     | 1,904     |
| `mpeg2_vfr`               | 29        | 29      | 27        |
| `mpeg2_lto_fallback`      | 525       | 235     | 237       |
| **Total**                 | **3,084** | **942** | **2,433** |

### Per-Folder Breakdown — Masters

| Folder      | Files   | Video   | Resolved | No Transfer |
| ----------- | ------- | ------- | -------- | ----------- |
| O:/Master 1 | 61      | 61      | 20       | 41          |
| O:/Master 2 | 61      | 61      | 29       | 32          |
| O:/Master 3 | 69      | 69      | 41       | 28          |
| O:/Master 4 | 97      | 96      | 3        | 94          |
| **Total**   | **288** | **287** | **93**   | **195**     |

Master 4 has the lowest resolution rate (3.1%) because most of its tapes have no `discovery_capture` transfers in the spreadsheet.

### MPEG-2 Breakdown

| Category                              | Files   | Storage     |
| ------------------------------------- | ------- | ----------- |
| Total                                 | 684     | 1.7 TB      |
| Matched (mpeg2_lto)                   | 390     | —           |
| Matched (mpeg2_vfr)                   | 29      | —           |
| Matched (mpeg2_lto_fallback)          | 235     | —           |
| **Total matched**                     | **654** | **~1.6 TB** |
| Unmatched .mpg                        | 22      | —           |
| Unmatched non-.mpg (.aac, .mp4, .xmp) | 8       | —           |
| **Total unmatched**                   | **30**  | **~0.1 TB** |

---

## Terminology

- **Resolved (tape_number):** Tape number extracted from filename (naming convention: `Tape NNN - ...`), AND at least one `discovery_capture` transfer links it to specific `film_rolls` identifiers.
- **No transfer link (tape_number_no_transfer):** Tape file exists on disk and tape number is in the expected range (501–886), but NO `discovery_capture` transfer references it. The video is on disk but we cannot map it to specific FR-numbers via the spreadsheet alone.
- **mpeg2_lto:** Bare L-number MPEG-2 file (e.g. `L000007.mpg`) matched by `transfers.lto_number` -- maps to ALL transfers on that LTO tape.
- **mpeg2_vfr:** Suffixed MPEG-2 file (e.g. `L000003_FR-27.mpg`) matched via `transfers.video_file_ref` (where `/` becomes `_` and FR numbers may drop leading zeros). Maps to a specific transfer/reel.
- **mpeg2_lto_fallback:** Suffixed MPEG-2 file that could not exact-match via `video_file_ref` (naming conventions differ), so falls back to matching by the L-number prefix against `lto_number` or the left side of `video_file_ref`. Maps to ALL transfers on that LTO tape, same as a bare file.
- **In DB but not on disk:** Tape number is in the expected range (501–886, per the naming convention) but no corresponding file was found in Masters 1–4. Many never physically existed.

---

## Master Tapes Without Transfer Links (195)

These 195 tape files are on disk and their tape numbers are in the expected range,
but there is no `discovery_capture` transfer linking them to specific film roll
identifiers. The "Shotlist IDs" column shows identifiers from the DiscoveryShotList
tab — these are the reel identifiers that the shotlist PDF describes for that tape,
but without a matching transfer row they don't resolve to `film_rolls`.

### Master 1

| Tape | Filename                                    | Size     | Shotlist IDs                                                                                                                             |
| ---- | ------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| 501  | Tape 501 - Self Contained.mov               | 178.5 GB | FR-7404,FR-7405,FR-7406,FR-7407                                                                                                          |
| 502  | Tape 502 - Self Contained.mov               | 147.6 GB |                                                                                                                                          |
| 503  | Tape 503 - Self Contained.mov               | 133.0 GB |                                                                                                                                          |
| 504  | Tape 504 - Self Contained.mov               | 121.3 GB |                                                                                                                                          |
| 507  | Tape 507 - Self Contained - Part 1 Of 2.mov | 60.8 GB  |                                                                                                                                          |
| 507  | Tape 507 - Self Contained - Part 2 Of 2.mov | 25.3 GB  |                                                                                                                                          |
| 508  | Tape 508 - Self Contained.mov               | 148.9 GB | Film 47, Film 48, Film 52, Film 169, Film 245, Film 327, Film 454, Film 518                                                              |
| 509  | Tape 509 - Self Contained.mov               | 168.2 GB | Film 694, Film 695, Film 724, Film 725, Film 736                                                                                         |
| 510  | Tape 510 - Self Contained.mov               | 183.5 GB | Film 736, Film 737, Film 738, Film 739, Film 2192                                                                                        |
| 511  | Tape 511 - Self Contained.mov               | 173.6 GB | FR-50, Film 172, FR 231, FR 274.1, FR 274.2, FR 285, FR301, FR 319                                                                       |
| 512  | Tape 512 - Self Contained.mov               | 175.8 GB | FR 552, Film 672, FR 685, Film 343, Film 356, FR 306, FR 389, FR480, FR 710                                                              |
| 514  | Tape 514 - Self Contained.mov               | 135.0 GB | 802260, HD, Can 01, Item 08, Can 02 Item 07 : Mag 11-23, Item 09 : Mag S-66 535, : Mag 198, Can 3, Item 1, Mag S-65-4                    |
| 515  | Tape 515 - Self Contained.mov               | 167.4 GB | 802262                                                                                                                                   |
| 516  | Tape 516 - Self Contained.mov               | 166.8 GB |                                                                                                                                          |
| 517  | Tape 517 - Self Contained.mov               | 184.8 GB | 802235                                                                                                                                   |
| 519  | Tape 519 - Self Contained.mov               | 146.8 GB | 802266                                                                                                                                   |
| 520  | Tape 520 - Self Contained.mov               | 48.4 GB  | 802227                                                                                                                                   |
| 521  | Tape 521 - Self Contained.mov               | 87.1 GB  |                                                                                                                                          |
| 522  | Tape 522 - Self Contained.mov               | 75.6 GB  |                                                                                                                                          |
| 523  | Tape 523 - Self Contained.mov               | 75.0 GB  |                                                                                                                                          |
| 524  | Tape 524 - Self Contained.mov               | 56.0 GB  |                                                                                                                                          |
| 525  | Tape 525 - Self Contained.mov               | 212.7 GB |                                                                                                                                          |
| 526  | Tape 526 - Self Contained.mov               | 187.8 GB |                                                                                                                                          |
| 527  | Tape 527 - Self Contained.mov               | 221.0 GB |                                                                                                                                          |
| 529  | Tape 529 - Self Contained.mov               | 11.2 GB  |                                                                                                                                          |
| 530  | Tape 530 - Self Contained.mov               | 227.2 GB | 255-S-1031, 255-S-1109, 255-S-4329, HQ-47                                                                                                |
| 531  | Tape 531 - Self Contained.mov               | 155.0 GB | 28327                                                                                                                                    |
| 532  | Tape 532 - Self Contained.mov               | 25.1 GB  | 41770                                                                                                                                    |
| 533  | Tape 533 - Self Contained.mov               | 148.1 GB | PPP19, PPP36, PPP 41, USG 15, WHN 15                                                                                                     |
| 539  | Tape 539 - Self Contained.mov               | 155.3 GB | JSC-307, FR38.1, 158.4, 173.1, 173.2                                                                                                     |
| 548  | Tape 548 - Self Contained.mov               | 119.0 GB |                                                                                                                                          |
| 549  | Tape 549 - Self Contained.mov               | 34.4 GB  | 81781                                                                                                                                    |
| 551  | Tape 551 - Self Contained.mov               | 235.3 GB | 255 S 1915, 255-S-02235, 255-S-2357, 255 S 2922, 255 s 9096, 342 USAF 42668 Reel 1, 31097 Reel 2                                         |
| 552  | Tape 552 - Self Contained.mov               | 143.1 GB | 342 USAF 35015 Reel 2, 342 USAF 37016 Reel 1, 342 USAF 37839, 342 USAF 39925, 342 USAF 40696, 342 USF 42668 Reel 2                       |
| 553  | Tape 553 - Self Contained.mov               | 79.5 GB  | 255 S 2169, 306.7756                                                                                                                     |
| 554  | Tape 554 - Self Contained.mov               | 156.4 GB |                                                                                                                                          |
| 555  | Tape 555 - Self Contained.mov               | 140.4 GB |                                                                                                                                          |
| 556  | Tape 556 - Self Contained.mov               | 39.4 GB  | 802325                                                                                                                                   |
| 557  | Tape 557 - Self Contained.mov               | 36.9 GB  | 802326                                                                                                                                   |
| 559  | Tape 559 - Self Contained.mov               | 164.2 GB | KSC-69-71218, KSC69-71230, KSC69-71231, KSC69-71246, KSC69-71265, ksc69-71265, KSC-69 71293, KSC-69-71291, MFC-79-439, 90 OM 298, 94-307 |
| 560  | Tape 560 - Self Contained.mov               | 74.3 GB  | OM-2359, O-266, O-13                                                                                                                     |

### Master 2

| Tape | Filename                      | Size     | Shotlist IDs                                                                                                                                                                                                      |
| ---- | ----------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 578  | Tape 578 - Self Contained.mov | 199.4 GB | HQ 88, HQ 167, HQ 188, HQA 200, HQA173, 255 S 1774                                                                                                                                                                |
| 579  | Tape 579 - Self Contained.mov | 204.4 GB | 255-S-02091, 255 S 02696, 255 S 02765, 255-S-2766, 255-S-9086, 255 S 1771, 255-S-2124, 255-S-1628                                                                                                                 |
| 580  | Tape 580 - Self Contained.mov | 142.2 GB | B964, B996, C027                                                                                                                                                                                                  |
| 581  | Tape 581 - Self Contained.mov | 167.9 GB | D504, D513, D514, D530                                                                                                                                                                                            |
| 582  | Tape 582 - Self Contained.mov | 171.8 GB | D535, D538, D546                                                                                                                                                                                                  |
| 583  | Tape 583 - Self Contained.mov | 101.1 GB | D659, D660, D661                                                                                                                                                                                                  |
| 584  | Tape 584 - Self Contained.mov | 160.7 GB | D588, D619, D623, D627, D655, D656                                                                                                                                                                                |
| 585  | Tape 585 - Self Contained.mov | 160.9 GB | D580, D581, D582, D583, D584, D585                                                                                                                                                                                |
| 586  | Tape 586 - Self Contained.mov | 169.2 GB | B539, B641, B678, B694, B746, B747                                                                                                                                                                                |
| 587  | Tape 587 - Self Contained.mov | 159.9 GB | B766, B967, B968, C061, C075, C076                                                                                                                                                                                |
| 588  | Tape 588 - Self Contained.mov | 161.5 GB | C141, C142, C193, C197, C204                                                                                                                                                                                      |
| 591  | Tape 591 - Self Contained.mov | 163.9 GB | 800776, 800736, 712293                                                                                                                                                                                            |
| 592  | Tape 592 - Self Contained.mov | 77.0 GB  | 800788                                                                                                                                                                                                            |
| 593  | Tape 593 - Self Contained.mov | 110.5 GB | 800720                                                                                                                                                                                                            |
| 594  | Tape 594 - Self Contained.mov | 76.9 GB  | 800781                                                                                                                                                                                                            |
| 595  | Tape 595 - Self Contained.mov | 104.8 GB | 800782                                                                                                                                                                                                            |
| 596  | Tape 596 - Self Contained.mov | 76.2 GB  | 800722                                                                                                                                                                                                            |
| 597  | Tape 597 - Self Contained.mov | 28.9 GB  | 801415                                                                                                                                                                                                            |
| 598  | Tape 598 - Self Contained.mov | 26.3 GB  | 800744                                                                                                                                                                                                            |
| 599  | Tape 599 - Self Contained.mov | 74.9 GB  | 800719                                                                                                                                                                                                            |
| 600  | Tape 600 - Self Contained.mov | 166.8 GB | 802320                                                                                                                                                                                                            |
| 601  | Tape 601 - Self Contained.mov | 151.2 GB | S67-506, S67-533, S67-545, S67-600                                                                                                                                                                                |
| 602  | Tape 602 - Self Contained.mov | 32.3 GB  | 802280                                                                                                                                                                                                            |
| 603  | Tape 603 - Self Contained.mov | 169.9 GB |                                                                                                                                                                                                                   |
| 604  | Tape 604 - Self Contained.mov | 89.0 GB  |                                                                                                                                                                                                                   |
| 611  | Tape 611 - Self Contained.mov | 151.1 GB | 255 ASR.004, 255 ASR 07, 255 ASR-08, 255 ASR 010, 255 ASR 011, 255 AS-012, 255 ASR-018, 255 ASR-21, 255 ASR-203, 255 ASR-33, 255 ASR-35, 255 ASR044, 255 ASR-046, 255 ASR-048, 255 ASR-50, 255 ASR 52, 255 ASR 54 |
| 612  | Tape 612 - Self Contained.mov | 53.9 GB  | HQ 183                                                                                                                                                                                                            |
| 613  | Tape 613 - Self Contained.mov | 66.2 GB  | 255 S 4217, 255 S, 255 S 4302, 255 S 4430                                                                                                                                                                         |
| 614  | Tape 614 - Self Contained.mov | 133.2 GB |                                                                                                                                                                                                                   |
| 615  | Tape 615 - Self Contained.mov | 73.6 GB  |                                                                                                                                                                                                                   |
| 618  | Tape 618 - Self Contained.mov | 6.2 GB   | 255 ASR-01                                                                                                                                                                                                        |
| 619  | Tape 619 - Self Contained.mov | 32.2 GB  | USG: 15 Reel 1                                                                                                                                                                                                    |

### Master 3

| Tape | Filename                                      | Size     | Shotlist IDs                                                                                     |
| ---- | --------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------ |
| 630  | Tape 630 - Self Contained.mov                 | 172.8 GB | 255-S-6555, 255-S-6342, 255-S-6360, 255-S-6473, 255-S-6873, 255-S-6757, 255-S-6866               |
| 631  | Tape 631 - Self Contained.mov                 | 173.4 GB | ASR-64, ASR-174, HQ-221A, 255-S-8109, 255-S-8474, 255-S-8659, 255-S-8841, 255-S-8954, 255-S-8649 |
| 632  | Tape 632 - Self Contained.mov                 | 43.9 GB  | 255-S-8500                                                                                       |
| 633  | Tape 633 - Self Contained.mov                 | 32.9 GB  | 255-S-9232                                                                                       |
| 636  | Tape 636 - Self Contained.mov                 | 89.1 GB  |                                                                                                  |
| 637  | Tape 637 - Self Contained.mov                 | 99.5 GB  |                                                                                                  |
| 638  | Tape 638 - Self Contained.mov                 | 31.8 GB  | 255 S 4598                                                                                       |
| 639  | Tape 639 - Self Contained.mov                 | 51.7 GB  | 255 S 4578, 255 S 2141, 255 S 4596                                                               |
| 641  | Tape 641 - Self Contained.mov                 | 186.9 GB | 802174                                                                                           |
| 643  | Tape 643 - Self Contained.mov                 | 78.2 GB  | 800720                                                                                           |
| 644  | Tape 644 - Self Contained.mov                 | 91.3 GB  | 255-S-9165, 255-ASR-05, 255-ASR-51, 255-ASR-74, 255-ASR-80, 255-ASR-91, 255-ASR-125              |
| 645  | Tape 645 - Self Contained.mov                 | 152.9 GB | 255-S-5511, 255-S-5517, 255-S-5518, 255-S-6296, 255-S-8236, 255-ASR-176                          |
| 646  | Tape 646 - Self Contained.mov                 | 166.5 GB | 255-HQA-159, 255-S-7155, 255-S-8519, 255-S-8530, 255-S-9161                                      |
| 647  | Tape 647 - Self Contained.mov                 | 172.1 GB | 255-S-4535, 255-S-4536, 255-S-4584, 255-S-4990, 255-S-5411, 255-S-5510                           |
| 670  | Tape 670 - Self Contained.mov                 | 42.3 GB  |                                                                                                  |
| 679  | Tape 679 - Self Contained.mov                 | 90.0 GB  | JSC-572, JSC-603                                                                                 |
| 680  | Tape 680 - Self Contained.mov                 | 146.8 GB |                                                                                                  |
| 681  | Tape 681 - Self Contained.mov                 | 92.5 GB  |                                                                                                  |
| 682  | Tape 682 - Self Contained.mov                 | 78.1 GB  | JSC-580                                                                                          |
| 683  | Tape 683 - Self Contained.mov                 | 48.1 GB  | MSFC E-8, MSFC E-16, MSFC E-72, MSFC E-77                                                        |
| 684  | Tape 684 - Part 1 of 2 - Self Contained.mov   | 45.4 GB  |                                                                                                  |
| 684  | Tape 684 - Part 2 of 2 - Self Contained.mov   | 80.1 GB  |                                                                                                  |
| 690  | Tape 690 - Self Contained.mov                 | 61.6 GB  | 803205                                                                                           |
| 700  | Tape 700 - Self Contained.mov                 | 13.9 GB  |                                                                                                  |
| 701  | Tape 701 - Self Contained.mov                 | 26.8 GB  |                                                                                                  |
| 703  | Tape 703 - Self Contained.mov                 | 3.0 GB   |                                                                                                  |
| 708  | Tape 708 - Self Contained.mov                 | 48.8 GB  | 718918                                                                                           |
| 709  | Tape 709 - Non Source TC - Self Contained.mov | 8.6 GB   | VJSC960                                                                                          |

### Master 4

| Tape | Filename                                                       | Size     | Shotlist IDs                                                                 |
| ---- | -------------------------------------------------------------- | -------- | ---------------------------------------------------------------------------- |
| 713  | Tape 713 - Non Source TC - Self Contained.mov                  | 45.7 GB  | VJSC1425L                                                                    |
| 714  | Tape 714 - Non Source TC - Self Contained.mov                  | 37.5 GB  | 607009                                                                       |
| 715  | Tape 715 - Non Source TC - Self Contained.mov                  | 16.5 GB  | 608024                                                                       |
| 716  | Tape 716 - Non Source TC - Self Contained.mov                  | 38.7 GB  | 461702                                                                       |
| 717  | Tape 717 - Non Source TC - Self Contained.mov                  | 8.8 GB   | 461804, 461805                                                               |
| 718  | Tape 718 - Non Source TC - Self Contained.mov                  | 48.0 GB  | 461826                                                                       |
| 719  | Tape 719 - Non Source TC - Self Contained.mov                  | 28.5 GB  |                                                                              |
| 720  | Tape 720 - Non Source TC - Self Contained.mov                  | 13.2 GB  |                                                                              |
| 721  | Tape 721 - Non Source TC - Self Contained.mov.[Files@Toke.Com] | n/a      |                                                                              |
| 722  | Tape 722 - Non Source TC - Self Contained.mov                  | 12.9 GB  |                                                                              |
| 723  | Tape 723 - Non Source TC - Self Contained.mov                  | 30.4 GB  | 0360-1M-S295-35Aa, 0660-2T-S647-237b&c, 06270-4T-W415-I67, 06270-5T-W315-632 |
| 724  | Tape 724 - Self Contained.mov                                  | 89.0 GB  |                                                                              |
| 725  | Tape 725 - Self Contained.mov                                  | 113.1 GB |                                                                              |
| 726  | Tape 726 - Non Source TC - Self Contained.mov                  | 30.7 GB  | 461920, 461924                                                               |
| 727  | Tape 727 - Non Source TC - Self Contained.mov                  | 2.0 GB   |                                                                              |
| 728  | Tape 728 - Non Source TC - Self Contained.mov                  | 16.8 GB  |                                                                              |
| 729  | Tape 729 - Non Source TC - Self Contained.mov                  | 12.8 GB  |                                                                              |
| 731  | Tape 731 - Non Source TC - Self Contained.mov                  | 27.4 GB  |                                                                              |
| 744  | Tape 744 - Non Source TC - Self Contained.mov                  | 12.5 GB  | JSC 1962                                                                     |
| 747  | Tape 747 - Non Source TC - Self Contained.mov                  | 40.6 GB  | JSC 1969                                                                     |
| 748  | Tape 748 - Non Source TC - Self Contained.mov                  | 34.2 GB  | CMP662                                                                       |
| 754  | Tape 754 - Non Source TC - Self Contained.mov                  | 18.4 GB  | FR-596                                                                       |
| 755  | Tape 755 - Non Source TC - Self Contained.mov                  | 29.2 GB  | FR-598                                                                       |
| 756  | Tape 756 - Non Source TC - Self Contained.mov                  | 30.2 GB  | 719724, 732830, 722439                                                       |
| 757  | Tape 757 - Non Source TC - Self Contained.mov                  | 52.9 GB  | 718299, 717558                                                               |
| 758  | Tape 758 - Non Source TC - Self Contained.mov                  | 48.5 GB  | 720071                                                                       |
| 759  | Tape 759 - Non Source TC - Self Contained.mov                  | 39.0 GB  |                                                                              |
| 760  | Tape 760 - Self Contained.mov                                  | 52.2 GB  | 720301                                                                       |
| 761  | Tape 761 - Self Contained.mov                                  | 60.7 GB  | 720069                                                                       |
| 762  | Tape 762 - Non Source TC - Self Contained.mov                  | 46.1 GB  |                                                                              |
| 763  | Tape 763 - Non Source TC - Self Contained.mov                  | 24.2 GB  |                                                                              |
| 764  | Tape 764 - Self Contained.mov                                  | 33.4 GB  | VJSC1395-2                                                                   |
| 765  | Tape 765 - Self Contained.mov                                  | 33.5 GB  | VJSC1395-1                                                                   |
| 766  | Tape 766 - Self Contained.mov                                  | 46.7 GB  | VJSC1168                                                                     |
| 780  | Tape 780 - Non Source TC - Self Contained.mov                  | 4.1 GB   |                                                                              |
| 786  | Tape 786 - Non Source TC - Self Contained.mov                  | 10.8 GB  |                                                                              |
| 787  | Tape 787 - Non Source TC - Self Contained.mov                  | 12.5 GB  |                                                                              |
| 788  | Tape 788 - Self Contained.mov                                  | 32.9 GB  | JSC-1632                                                                     |
| 789  | Tape 789 - Self Contained.mov                                  | 48.1 GB  | JSC-1814                                                                     |
| 790  | Tape 790 - Self Contained.mov                                  | 31.8 GB  | JSC-1814                                                                     |
| 791  | Tape 791 - Self Contained.mov                                  | 33.0 GB  | JSC-1916                                                                     |
| 792  | Tape 792 - Self Contained.mov                                  | 46.3 GB  | JSC-1916                                                                     |
| 793  | Tape 793 - Self Contained.mov                                  | 32.5 GB  | JSC-1916                                                                     |
| 794  | Tape 794 - Non Source TC - Self Contained.mov                  | 50.1 GB  | JSC-1916                                                                     |
| 795  | Tape 795 - Self Contained.mov                                  | 59.2 GB  | 715953, 715916, 715966, 718356, 718904                                       |
| 796  | Tape 796 - Self Contained.mov                                  | 34.2 GB  | 734456                                                                       |
| 797  | Tape 797 - Non Source TC - Self Contained.mov                  | 29.7 GB  | 734457                                                                       |
| 798  | Tape 798 - Self Contained.mov                                  | 32.2 GB  | 734459                                                                       |
| 799  | Tape 799 - Non Source TC - Self Contained.mov                  | 27.0 GB  | 734458                                                                       |
| 800  | Tape 800 - Non Source TC - Self Contained.mov                  | 44.8 GB  |                                                                              |
| 801  | Tape 801 - Non Source TC - Self Contained.mov                  | 51.3 GB  | 734460                                                                       |
| 802  | Tape 802 - Non Source TC - Self Contained.mov                  | 50.5 GB  | 718356                                                                       |
| 803  | Tape 803 - Self Contained.mov                                  | 11.6 GB  |                                                                              |
| 804  | Tape 804 - Self Contained.mov                                  | 20.3 GB  |                                                                              |
| 805  | Tape 805 - Self Contained.mov                                  | 42.2 GB  |                                                                              |
| 806  | Tape 806 - Non Source TC - Self Contained.mov                  | 7.4 GB   |                                                                              |
| 808  | Tape 808 - Non Source TC - Self Contained.mov                  | 16.8 GB  |                                                                              |
| 809  | Tape 809 - Self Contained.mov                                  | 69.0 GB  | 117780, 117761, 117784, 117687, 117752                                       |
| 810  | Tape 810 - Self Contained.mov                                  | 60.3 GB  | 117712                                                                       |
| 813  | Tape 813 - Non Source TC - Self Contained.mov                  | 6.5 GB   | G94-001                                                                      |
| 814  | Tape 814 - Non Source TC - Self Contained.mov                  | 5.6 GB   | G90-001                                                                      |
| 815  | Tape 815 - Self Contained.mov                                  | 7.4 GB   | G90-006                                                                      |
| 816  | Tape 816 - Non Source TC - Self Contained.mov                  | 16.6 GB  | G90-012                                                                      |
| 817  | Tape 817 - Non Source TC - Self Contained.mov                  | 10.9 GB  | G89-003                                                                      |
| 818  | Tape 818 - Non Source TC - Self Contained.mov                  | 16.7 GB  |                                                                              |
| 823  | Tape 823 - Self Contained.mov                                  | 33.6 GB  | JSC1906                                                                      |
| 828  | Tape 828 - Non Source TC - Self Contained.mov                  | 47.5 GB  |                                                                              |
| 832  | Tape 832 - Non Source TC - Self Contained.mov                  | 2.0 GB   |                                                                              |
| 833  | Tape 833 - Non Source TC - Self Contained.mov                  | 27.2 GB  |                                                                              |
| 835  | Tape 835 - Non Source TC - Self Contained.mov                  | 21.6 GB  |                                                                              |
| 837  | Tape 837 - Non Source TC - Self Contained.mov                  | 3.6 GB   |                                                                              |
| 839  | Tape 839 - Non Source TC - Self Contained.mov                  | 48.6 GB  |                                                                              |
| 840  | Tape 840 - Non Source TC - Self Contained.mov                  | 1.9 GB   |                                                                              |
| 845  | Tape 845 - Non Source TC - Self Contained.mov                  | 46.1 GB  |                                                                              |
| 847  | Tape 847 - Non Source TC - Self Contained.mov                  | 37.0 GB  |                                                                              |
| 850  | Tape 850 - Non Source TC - Self Contained.mov                  | 7.1 GB   |                                                                              |
| 859  | Tape 859 - Non Source TC - Self Contained.mov                  | 53.7 GB  |                                                                              |
| 860  | Tape 860 - Non Source TC - Self Contained.mov                  | 29.6 GB  | JSC-1625                                                                     |
| 861  | Tape 861 - Non Source TC - Self Contained.mov                  | 36.4 GB  | JSC-1648                                                                     |
| 864  | Tape 864 - Non Source TC - Self Contained.mov                  | 24.6 GB  | JSC1660                                                                      |
| 867  | Tape 867 - Non Source TC - Self Contained.mov                  | 3.8 GB   |                                                                              |
| 873  | Tape 873 - Non Source TC - Self Contained.mov                  | 10.8 GB  |                                                                              |
| 874  | Tape 874 - Non Source TC - Self Contained.mov                  | 37.1 GB  |                                                                              |
| 875  | Tape 875 - Non Source TC - Self Contained.mov                  | 32.1 GB  |                                                                              |
| 876  | Tape 876 - Non Source TC - Self Contained.mov                  | 46.8 GB  |                                                                              |
| 877  | Tape 877 - Non Source TC - Self Contained.mov                  | 11.3 GB  |                                                                              |
| 878  | Tape 878 - Non Source TC - Self Contained.mov                  | 47.5 GB  |                                                                              |
| 879  | Tape 879 - Non Source TC - Self Contained.mov                  | 21.8 GB  |                                                                              |
| 880  | Tape 880 - Non Source TC - Self Contained.mov                  | 20.6 GB  |                                                                              |
| 882  | Tape 882 - Non Source TC - Self Contained.mov                  | 66.5 GB  | 502373, 506620, 715807, 715996                                               |
| 883  | Tape 883 - Non Source TC - Self Contained.mov                  | 2.9 GB   |                                                                              |
| 884  | Tape 884 - Non Source TC - Self Contained.mov                  | 5.0 GB   |                                                                              |
| 885  | Tape 885 - Non Source TC - Self Contained.mov                  | 4.7 GB   |                                                                              |
| 886  | Tape 886 - Non Source TC - Self Contained.mov                  | 5.1 GB   |                                                                              |

---

## MPEG-2 Files (684)

The `O:/MPEG-2` folder contains 684 files — mostly MPEG-2 proxy encodes keyed by LTO
tape number. Filenames follow one of two patterns:

- **Bare L-number:** `L000007.mpg` — represents the entire LTO tape; matched to ALL
  `lto_copy` transfers sharing that `lto_number` (rule: `mpeg2_lto`).
- **Suffixed:** `L000003_FR-27.mpg` — a specific reel on an LTO tape; first attempts
  exact match via `transfers.video_file_ref` (rule: `mpeg2_vfr`). If that fails (naming
  convention differences), falls back to matching the L-number prefix against `lto_number`
  or the left side of `video_file_ref` (rule: `mpeg2_lto_fallback`).

### Matched via video_file_ref (29 files → 27 reels)

| Filename                  | Reel       |
| ------------------------- | ---------- |
| L000003_FR-27.mpg         | FR-0027    |
| L000003_FR-419.mpg        | FR-0419    |
| L000003_FR-425.mpg        | FR-0425    |
| L000003_FR-544.mpg        | FR-0544    |
| L000799_FR-9014.mpg       | FR-9014    |
| L000799_FR-9016.mpg       | FR-9016    |
| L000799_FR-9017.mpg       | FR-9017    |
| L000801_FR-9018.mpg       | FR-9018    |
| L000801_FR-9019.mpg       | FR-9019    |
| L000801_FR-9021.mpg       | FR-9021    |
| L000879_FR-AK-185.mpg     | AK-185     |
| L000879_FR-AK-186.mpg     | AK-185     |
| L000923_FR-Slezak-006.mpg | SLEZAK-007 |
| L000923_FR-Slezak-007.mpg | SLEZAK-007 |
| L001013_FR-B292.mpg       | FR-B292    |
| L001021_FR-B402.mpg       | FR-B402    |
| L001021_FR-B403.mpg       | FR-B403    |
| L001021_FR-B407.mpg       | FR-B407    |
| L001021_FR-B660.mpg       | FR-B660    |
| L001045_FR-4313.mpg       | FR-4313    |
| L001045_FR-4779.mpg       | FR-4779    |
| L001045_FR-D564.mpg       | FR-D564    |
| L001045_FR-D570.mpg       | FR-D570    |
| L001357_FR-F524.mpg       | FR-F524    |
| L001357_FR-F525.mpg       | FR-F525    |
| L001357_FR-F526.mpg       | FR-F526    |
| L001357_FR-F528.mpg       | FR-F528    |
| L001357_FR-F529.mpg       | FR-F529    |
| L001385_FR-F633.mpg       | FR-F633    |

### LTO Fallback Matches (235 files → 237 reels)

235 suffixed MPEG-2 files could not exact-match via `video_file_ref` due to naming
convention differences (e.g. `FR-AK-3` on disk vs `AK-003` in DB, missing hyphens,
extra qualifiers like `A&B`). These are now resolved by falling back to the L-number
prefix — matching against `lto_number` or the left side of `video_file_ref`. This
links the file to ALL transfers on that LTO tape rather than a specific reel.

### Unmatched MPEG-2 (30 files)

30 files could not be matched to any transfer:

| Category                                    | Count | Examples                                       |
| ------------------------------------------- | ----- | ---------------------------------------------- |
| `.mpg` files — L-number not in any transfer | 16    | `L001603_FR-9152.mpg`, `L003219_FR-G390.mpg`   |
| `.mpg` files — bare L-number not in DB      | 4     | `L000533.mpg`, `L000603.mpg`                   |
| `.mpg` — unusual filename format            | 2     | `L000571Restricted.mpg`, `L000907-FR-AK45.mpg` |
| Non-`.mpg` files (`.aac`, `.mp4`, `.xmp`)   | 8     | `L000437.xmp`, `L001237_FR-F074.mp4`           |

These represent LTO numbers not present in the master spreadsheet, sidecar files,
or edge-case naming that doesn't match the expected `L######[_suffix].mpg` pattern.

---

## Tapes in DB but Not on Disk (101)

These tape numbers are in the expected range (501–886, derived from the naming
convention: tapes 501–562 = Master 1, 563–625 = Master 2, etc.) but no
corresponding `.mov` file was found in Masters 1–4. Many of
these tapes never physically existed — they were represented on disk only by
placeholder `.txt` files ("not missing — doesn't exist") which are now ignored.
Some (especially Master 1 and Master 3) may be genuinely missing.

### Master 1

| Tape | Expected Path                             |
| ---- | ----------------------------------------- |
| 528  | /o/Master 1/Tape 528 - Self Contained.mov |
| 550  | /o/Master 1/Tape 550 - Self Contained.mov |

### Master 2

| Tape | Expected Path                             |
| ---- | ----------------------------------------- |
| 589  | /o/Master 2/Tape 589 - Self Contained.mov |
| 590  | /o/Master 2/Tape 590 - Self Contained.mov |

### Master 3

| Tape | Expected Path                             |
| ---- | ----------------------------------------- |
| 634  | /o/Master 3/Tape 634 - Self Contained.mov |
| 635  | /o/Master 3/Tape 635 - Self Contained.mov |
| 648  | /o/Master 3/Tape 648 - Self Contained.mov |
| 649  | /o/Master 3/Tape 649 - Self Contained.mov |
| 666  | /o/Master 3/Tape 666 - Self Contained.mov |
| 675  | /o/Master 3/Tape 675 - Self Contained.mov |
| 676  | /o/Master 3/Tape 676 - Self Contained.mov |
| 686  | /o/Master 3/Tape 686 - Self Contained.mov |
| 692  | /o/Master 3/Tape 692 - Self Contained.mov |
| 693  | /o/Master 3/Tape 693 - Self Contained.mov |
| 694  | /o/Master 3/Tape 694 - Self Contained.mov |
| 695  | /o/Master 3/Tape 695 - Self Contained.mov |
| 696  | /o/Master 3/Tape 696 - Self Contained.mov |
| 697  | /o/Master 3/Tape 697 - Self Contained.mov |
| 698  | /o/Master 3/Tape 698 - Self Contained.mov |
| 699  | /o/Master 3/Tape 699 - Self Contained.mov |
| 702  | /o/Master 3/Tape 702 - Self Contained.mov |
| 710  | /o/Master 3/Tape 710 - Self Contained.mov |
| 711  | /o/Master 3/Tape 711 - Self Contained.mov |
| 712  | /o/Master 3/Tape 712 - Self Contained.mov |

### Master 4

| Tape | Expected Path                             |
| ---- | ----------------------------------------- |
| 730  | /o/Master 4/Tape 730 - Self Contained.mov |
| 732  | /o/Master 4/Tape 732 - Self Contained.mov |
| 733  | /o/Master 4/Tape 733 - Self Contained.mov |
| 734  | /o/Master 4/Tape 734 - Self Contained.mov |
| 735  | /o/Master 4/Tape 735 - Self Contained.mov |
| 736  | /o/Master 4/Tape 736 - Self Contained.mov |
| 737  | /o/Master 4/Tape 737 - Self Contained.mov |
| 738  | /o/Master 4/Tape 738 - Self Contained.mov |
| 739  | /o/Master 4/Tape 739 - Self Contained.mov |
| 740  | /o/Master 4/Tape 740 - Self Contained.mov |
| 741  | /o/Master 4/Tape 741 - Self Contained.mov |
| 742  | /o/Master 4/Tape 742 - Self Contained.mov |
| 743  | /o/Master 4/Tape 743 - Self Contained.mov |
| 745  | /o/Master 4/Tape 745 - Self Contained.mov |
| 746  | /o/Master 4/Tape 746 - Self Contained.mov |
| 749  | /o/Master 4/Tape 749 - Self Contained.mov |
| 750  | /o/Master 4/Tape 750 - Self Contained.mov |
| 751  | /o/Master 4/Tape 751 - Self Contained.mov |
| 752  | /o/Master 4/Tape 752 - Self Contained.mov |
| 753  | /o/Master 4/Tape 753 - Self Contained.mov |
| 768  | /o/Master 4/Tape 768 - Self Contained.mov |
| 769  | /o/Master 4/Tape 769 - Self Contained.mov |
| 770  | /o/Master 4/Tape 770 - Self Contained.mov |
| 771  | /o/Master 4/Tape 771 - Self Contained.mov |
| 772  | /o/Master 4/Tape 772 - Self Contained.mov |
| 773  | /o/Master 4/Tape 773 - Self Contained.mov |
| 774  | /o/Master 4/Tape 774 - Self Contained.mov |
| 775  | /o/Master 4/Tape 775 - Self Contained.mov |
| 776  | /o/Master 4/Tape 776 - Self Contained.mov |
| 777  | /o/Master 4/Tape 777 - Self Contained.mov |
| 778  | /o/Master 4/Tape 778 - Self Contained.mov |
| 779  | /o/Master 4/Tape 779 - Self Contained.mov |
| 781  | /o/Master 4/Tape 781 - Self Contained.mov |
| 782  | /o/Master 4/Tape 782 - Self Contained.mov |
| 783  | /o/Master 4/Tape 783 - Self Contained.mov |
| 784  | /o/Master 4/Tape 784 - Self Contained.mov |
| 785  | /o/Master 4/Tape 785 - Self Contained.mov |
| 807  | /o/Master 4/Tape 807 - Self Contained.mov |
| 811  | /o/Master 4/Tape 811 - Self Contained.mov |
| 812  | /o/Master 4/Tape 812 - Self Contained.mov |
| 820  | /o/Master 4/Tape 820 - Self Contained.mov |
| 821  | /o/Master 4/Tape 821 - Self Contained.mov |
| 822  | /o/Master 4/Tape 822 - Self Contained.mov |
| 824  | /o/Master 4/Tape 824 - Self Contained.mov |
| 825  | /o/Master 4/Tape 825 - Self Contained.mov |
| 826  | /o/Master 4/Tape 826 - Self Contained.mov |
| 827  | /o/Master 4/Tape 827 - Self Contained.mov |
| 829  | /o/Master 4/Tape 829 - Self Contained.mov |
| 830  | /o/Master 4/Tape 830 - Self Contained.mov |
| 831  | /o/Master 4/Tape 831 - Self Contained.mov |
| 834  | /o/Master 4/Tape 834 - Self Contained.mov |
| 836  | /o/Master 4/Tape 836 - Self Contained.mov |
| 838  | /o/Master 4/Tape 838 - Self Contained.mov |
| 841  | /o/Master 4/Tape 841 - Self Contained.mov |
| 842  | /o/Master 4/Tape 842 - Self Contained.mov |
| 843  | /o/Master 4/Tape 843 - Self Contained.mov |
| 844  | /o/Master 4/Tape 844 - Self Contained.mov |
| 846  | /o/Master 4/Tape 846 - Self Contained.mov |
| 848  | /o/Master 4/Tape 848 - Self Contained.mov |
| 849  | /o/Master 4/Tape 849 - Self Contained.mov |
| 851  | /o/Master 4/Tape 851 - Self Contained.mov |
| 852  | /o/Master 4/Tape 852 - Self Contained.mov |
| 853  | /o/Master 4/Tape 853 - Self Contained.mov |
| 854  | /o/Master 4/Tape 854 - Self Contained.mov |
| 855  | /o/Master 4/Tape 855 - Self Contained.mov |
| 856  | /o/Master 4/Tape 856 - Self Contained.mov |
| 857  | /o/Master 4/Tape 857 - Self Contained.mov |
| 858  | /o/Master 4/Tape 858 - Self Contained.mov |
| 863  | /o/Master 4/Tape 863 - Self Contained.mov |
| 865  | /o/Master 4/Tape 865 - Self Contained.mov |
| 866  | /o/Master 4/Tape 866 - Self Contained.mov |
| 868  | /o/Master 4/Tape 868 - Self Contained.mov |
| 869  | /o/Master 4/Tape 869 - Self Contained.mov |
| 870  | /o/Master 4/Tape 870 - Self Contained.mov |
| 871  | /o/Master 4/Tape 871 - Self Contained.mov |
| 872  | /o/Master 4/Tape 872 - Self Contained.mov |
| 881  | /o/Master 4/Tape 881 - Self Contained.mov |

---

## Notes

- **"Non Source TC"** in filenames indicates the video has non-source timecode
  (burned-in or regenerated), not the original camera/recorder timecode.
- **Tape 721** has a corrupt/renamed extension: `.mov.[Files@Toke.Com]` — likely
  a download artifact.
- The tapes without transfer links represent compilation captures where the
  DiscoveryShotList tab may have reel identifiers but no `discovery_capture`
  transfer row was created in the Master List to bridge them to `film_rolls`.
  The shotlist PDFs are the primary path to resolving these.
- MPEG-2 `mpeg2_lto` matches are one-to-many: a single bare `.mpg` file may
  represent multiple film rolls on the same LTO tape (390 files → 1,904 reels).
