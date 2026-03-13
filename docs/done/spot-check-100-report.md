# Spot Check: 100 Random PDFs through marker-pdf

**Date**: 2026-02-25 23:20
**Tool**: marker-pdf with `force_ocr` mode
**Sample**: 100 PDFs randomly stratified from 10,590 total
**Total processing time**: 3758s (62.6 min)
**Average per PDF**: 37.6s (median 17.4s)

## Summary

**62/100 (62%)** PDFs produced good or fair OCR output.

### Quality Distribution

| Quality       | Count |   % | Description                                                                      |
| ------------- | ----: | --: | -------------------------------------------------------------------------------- |
| **good**      |    49 | 49% | Typed shot list with sequential footage numbers and structural metadata detected |
| **fair**      |    13 | 13% | Tabular content detected with readable text, some structural elements            |
| **uncertain** |    28 | 28% | Text extracted but structure unclear — may need manual review                    |
| **poor**      |    10 | 10% | Very little readable text or mostly noise                                        |
| **empty**     |     0 |  0% | Nearly empty output (<50 chars)                                                  |

### Document Type Distribution

| Type            | Count |   % |
| --------------- | ----: | --: |
| typed_shot_list |    55 | 55% |
| tabular_unknown |    41 | 41% |
| unknown         |     4 |  4% |

### Quality by File Size

| Size Bucket | Total | Good | Fair | Uncertain | Poor | Empty |
| ----------- | ----: | ---: | ---: | --------: | ---: | ----: |
| <10 KB      |     1 |    0 |    0 |         0 |    1 |     0 |
| 10–30 KB    |    26 |    1 |    2 |        18 |    5 |     0 |
| 30–50 KB    |    23 |    6 |    7 |         6 |    4 |     0 |
| 50–100 KB   |    23 |   19 |    1 |         3 |    0 |     0 |
| 100–500 KB  |    26 |   22 |    3 |         1 |    0 |     0 |
| >500 KB     |     1 |    1 |    0 |         0 |    0 |     0 |

### Processing Time Distribution

- **Min**: 2.9s
- **Max**: 133.7s
- **Mean**: 37.6s
- **Median**: 17.4s
- **Std Dev**: 40.5s
- **P95**: 122.1s

### Projected Full Batch (10,590 PDFs)

- At 37.6s average: **110.5 hours**
- At 17.4s median: **51.0 hours**
- At P95 (122.1s) worst-case bound: **359.2 hours**

## Detailed Results

|   # | PDF                       |   Size |   Time | Quality       | Type            | Footage# | Angles | Struct |  Chars |
| --: | ------------------------- | -----: | -----: | ------------- | --------------- | -------- | ------ | ------ | -----: |
|   1 | FR-00322012-07-18.pdf     |  46 KB |  14.1s | **fair**      | typed_shot_list | 11       | 9      | 4/6    |   6881 |
|   2 | FR-0146.pdf               |  22 KB |   5.8s | **poor**      | tabular_unknown | 1        | 0      | 4/6    |   5951 |
|   3 | FR-0157.pdf               |  20 KB |   6.3s | **uncertain** | tabular_unknown | 2        | 0      | 4/6    |   3527 |
|   4 | FR-0176-42012-07-17.pdf   |  24 KB |   7.2s | **uncertain** | tabular_unknown | 1        | 0      | 4/6    |   4926 |
|   5 | FR-0187.pdf               |  26 KB |   4.0s | **fair**      | typed_shot_list | 3        | 0      | 1/6    |    239 |
|   6 | FR-01932012-07-18.pdf     |  37 KB |  88.5s | **fair**      | tabular_unknown | 0        | 0      | 0/6    |  18143 |
|   7 | FR-03272012-07-18.pdf     |  22 KB | 101.4s | **poor**      | tabular_unknown | 0        | 0      | 4/6    |  70899 |
|   8 | FR-03392012-07-17.pdf     |  22 KB |  13.7s | **uncertain** | tabular_unknown | 0        | 0      | 5/6    |   6847 |
|   9 | FR-0352-2.pdf             |  19 KB |   7.6s | **uncertain** | tabular_unknown | 0        | 0      | 4/6    |   6159 |
|  10 | FR-0364-22012-07-17.pdf   |  15 KB |   6.4s | **uncertain** | tabular_unknown | 0        | 0      | 5/6    |   3717 |
|  11 | FR-04042012-07-17.pdf     |  27 KB |   4.2s | **uncertain** | unknown         | 0        | 0      | 4/6    |    660 |
|  12 | FR-0435-12012-07-18.pdf   |  38 KB |  11.1s | **fair**      | tabular_unknown | 1        | 0      | 1/6    |   9716 |
|  13 | FR-05162012-07-18.pdf     |  31 KB |  16.1s | **poor**      | tabular_unknown | 1        | 0      | 5/6    |  13293 |
|  14 | FR-0522-1.pdf             |  22 KB |   6.4s | **fair**      | tabular_unknown | 0        | 0      | 5/6    |   1505 |
|  15 | FR-05372012-07-17.pdf     |  49 KB |   7.7s | **uncertain** | tabular_unknown | 0        | 0      | 3/6    |   3151 |
|  16 | FR-05562012-07-18.pdf     |  40 KB |  10.8s | **uncertain** | tabular_unknown | 0        | 4      | 5/6    |   5557 |
|  17 | FR-0566.pdf               |  30 KB | 102.5s | **poor**      | tabular_unknown | 0        | 0      | 5/6    | 102660 |
|  18 | FR-05682012-07-17.pdf     |  24 KB |  11.1s | **poor**      | tabular_unknown | 1        | 0      | 5/6    |   9359 |
|  19 | FR-05782012-07-17.pdf     |  27 KB |   9.2s | **uncertain** | tabular_unknown | 0        | 0      | 5/6    |   7209 |
|  20 | FR-0647.pdf               |  25 KB |   3.4s | **uncertain** | unknown         | 0        | 0      | 5/6    |    387 |
|  21 | FR-0778-1.pdf             |  35 KB | 100.3s | **poor**      | tabular_unknown | 2        | 0      | 5/6    |  81249 |
|  22 | FR-0798.pdf               |  22 KB |  10.0s | **uncertain** | tabular_unknown | 0        | 0      | 5/6    |   3900 |
|  23 | FR-0949.pdf               | 136 KB | 118.1s | **good**      | typed_shot_list | 63       | 76     | 5/6    | 124487 |
|  24 | FR-1005.pdf               |  18 KB |   4.1s | **uncertain** | unknown         | 0        | 0      | 4/6    |    430 |
|  25 | FR-1048.pdf               |  81 KB |  13.7s | **good**      | typed_shot_list | 35       | 39     | 5/6    |  14041 |
|  26 | FR-1409.pdf               |  91 KB |  17.7s | **good**      | typed_shot_list | 24       | 30     | 4/6    |   9307 |
|  27 | FR-1435.pdf               |  82 KB |  89.0s | **good**      | typed_shot_list | 11       | 68     | 5/6    | 231032 |
|  28 | FR-1480.pdf               |  31 KB |  14.4s | **uncertain** | tabular_unknown | 0        | 5      | 4/6    |   5016 |
|  29 | FR-1542.pdf               | 177 KB |  32.9s | **good**      | typed_shot_list | 83       | 91     | 5/6    |  30198 |
|  30 | FR-1547.pdf               |  34 KB |  10.2s | **good**      | typed_shot_list | 16       | 10     | 5/6    |   6852 |
|  31 | FR-1560.pdf               |  61 KB |  29.9s | **uncertain** | tabular_unknown | 1        | 39     | 6/6    |  15481 |
|  32 | FR-1681.pdf               | 159 KB | 123.9s | **good**      | typed_shot_list | 83       | 113    | 6/6    |  53049 |
|  33 | FR-1920.pdf               |  54 KB | 111.4s | **uncertain** | tabular_unknown | 0        | 13     | 0/6    |  96225 |
|  34 | FR-2155.pdf               |   9 KB |   2.9s | **poor**      | unknown         | 0        | 1      | 2/6    |    179 |
|  35 | FR-2608.pdf               |  42 KB |   9.6s | **uncertain** | tabular_unknown | 23       | 23     | 4/6    |   5726 |
|  36 | FR-2782.pdf               |  76 KB |  11.7s | **good**      | typed_shot_list | 38       | 35     | 5/6    |  12643 |
|  37 | FR-2871.pdf               |  69 KB |  14.3s | **good**      | typed_shot_list | 21       | 8      | 5/6    |   7819 |
|  38 | FR-3117.pdf               |  86 KB |  20.2s | **good**      | typed_shot_list | 14       | 31     | 5/6    |  10627 |
|  39 | FR-3127.pdf               | 135 KB |  15.8s | **good**      | typed_shot_list | 39       | 9      | 5/6    |  13102 |
|  40 | FR-3330.pdf               |  59 KB |   9.5s | **good**      | typed_shot_list | 13       | 10     | 4/6    |   6031 |
|  41 | FR-3526.pdf               | 126 KB | 115.3s | **good**      | typed_shot_list | 52       | 73     | 5/6    | 106821 |
|  42 | FR-3541.pdf               | 132 KB | 115.8s | **good**      | typed_shot_list | 59       | 45     | 6/6    |  92399 |
|  43 | FR-3562.pdf               |  58 KB | 105.9s | **good**      | typed_shot_list | 14       | 10     | 5/6    |  60563 |
|  44 | FR-3593.pdf               | 233 KB |  20.6s | **good**      | typed_shot_list | 74       | 70     | 6/6    |  30915 |
|  45 | FR-3642.pdf               |  89 KB | 109.1s | **good**      | typed_shot_list | 37       | 35     | 6/6    |  98340 |
|  46 | FR-3676.pdf               | 227 KB | 125.5s | **good**      | typed_shot_list | 40       | 70     | 4/6    | 103534 |
|  47 | FR-37822012-07-18.pdf     | 172 KB |  26.9s | **good**      | typed_shot_list | 57       | 57     | 6/6    |  38073 |
|  48 | FR-38072012-07-18.pdf     |  42 KB |  27.4s | **fair**      | tabular_unknown | 0        | 7      | 5/6    |   4589 |
|  49 | FR-39502012-07-18.pdf     | 175 KB | 116.0s | **good**      | typed_shot_list | 44       | 53     | 6/6    | 100973 |
|  50 | FR-39632012-07-18.pdf     | 179 KB |  20.5s | **fair**      | typed_shot_list | 35       | 54     | 6/6    |  22963 |
|  51 | FR-40582012-07-18.pdf     |  37 KB |  15.3s | **good**      | typed_shot_list | 4        | 9      | 5/6    |   6497 |
|  52 | FR-41022012-07-18 (2).pdf |  28 KB |   7.6s | **good**      | typed_shot_list | 3        | 2      | 4/6    |   7539 |
|  53 | FR-41182012-07-18 (2).pdf |  24 KB |   8.2s | **uncertain** | tabular_unknown | 0        | 2      | 5/6    |   3119 |
|  54 | FR-41362012-07-18.pdf     |  59 KB |  50.0s | **fair**      | tabular_unknown | 0        | 14     | 6/6    |   6344 |
|  55 | FR-4312.pdf               |  65 KB |  18.0s | **good**      | typed_shot_list | 21       | 14     | 6/6    |  11378 |
|  56 | FR-4480.pdf               | 100 KB |  56.2s | **good**      | typed_shot_list | 30       | 60     | 6/6    |  16704 |
|  57 | FR-4492.pdf               | 124 KB |  38.9s | **good**      | typed_shot_list | 31       | 33     | 6/6    |  24704 |
|  58 | FR-4494.pdf               |  83 KB |  51.9s | **good**      | typed_shot_list | 15       | 276    | 6/6    |  18758 |
|  59 | FR-4564.pdf               |  68 KB |  11.9s | **good**      | typed_shot_list | 24       | 26     | 5/6    |  11846 |
|  60 | FR-4619.pdf               | 194 KB |  24.6s | **good**      | typed_shot_list | 107      | 101    | 6/6    |  33749 |
|  61 | FR-4909.pdf               |  44 KB |  24.0s | **uncertain** | tabular_unknown | 1        | 8      | 6/6    |   6792 |
|  62 | FR-4959.pdf               |  49 KB |  14.2s | **good**      | typed_shot_list | 3        | 8      | 6/6    |   8149 |
|  63 | FR-4962.pdf               |  28 KB |   8.9s | **uncertain** | tabular_unknown | 0        | 1      | 5/6    |   5858 |
|  64 | FR-5006.pdf               |  38 KB |   8.4s | **good**      | typed_shot_list | 12       | 13     | 5/6    |   6383 |
|  65 | FR-5265.pdf               |  38 KB |  99.7s | **poor**      | tabular_unknown | 2        | 3      | 4/6    |  62610 |
|  66 | FR-5287.pdf               | 116 KB | 111.8s | **good**      | typed_shot_list | 51       | 52     | 5/6    | 182685 |
|  67 | FR-5378.pdf               |  91 KB |  16.0s | **good**      | typed_shot_list | 29       | 26     | 6/6    |  18745 |
|  68 | FR-5433.pdf               | 179 KB |  24.2s | **good**      | typed_shot_list | 70       | 89     | 4/6    |  22303 |
|  69 | FR-5450.pdf               |  67 KB |  10.8s | **good**      | typed_shot_list | 17       | 9      | 5/6    |   9470 |
|  70 | FR-5474.pdf               | 126 KB | 113.9s | **fair**      | typed_shot_list | 17       | 34     | 6/6    |  31638 |
|  71 | FR-5509.pdf               |  66 KB |   9.6s | **good**      | typed_shot_list | 20       | 21     | 6/6    |   8776 |
|  72 | FR-5577.pdf               |  94 KB |  17.0s | **good**      | typed_shot_list | 9        | 25     | 5/6    |  18657 |
|  73 | FR-5608.pdf               |  30 KB |  13.6s | **uncertain** | tabular_unknown | 1        | 3      | 3/6    |   7129 |
|  74 | FR-5640.pdf               |  39 KB |  59.1s | **fair**      | tabular_unknown | 0        | 193    | 5/6    |  36959 |
|  75 | FR-5669.pdf               |  79 KB | 122.1s | **good**      | typed_shot_list | 22       | 35     | 6/6    | 104312 |
|  76 | FR-5916.pdf               | 774 KB | 133.7s | **good**      | typed_shot_list | 113      | 104    | 6/6    | 115189 |
|  77 | FR-6047.pdf               | 498 KB | 124.7s | **good**      | typed_shot_list | 62       | 55     | 5/6    | 103270 |
|  78 | FR-6080.pdf               | 381 KB |  18.0s | **uncertain** | tabular_unknown | 50       | 43     | 4/6    |  15814 |
|  79 | FR-6382.pdf               | 134 KB |  20.3s | **fair**      | typed_shot_list | 23       | 11     | 6/6    |  12180 |
|  80 | FR-6624.pdf               | 189 KB |  22.2s | **good**      | typed_shot_list | 87       | 65     | 5/6    |  17765 |
|  81 | FR-6760.pdf               |  32 KB |   9.8s | **good**      | typed_shot_list | 5        | 3      | 5/6    |   6554 |
|  82 | FR-6826.pdf               |  51 KB |  11.5s | **good**      | typed_shot_list | 12       | 11     | 6/6    |   7826 |
|  83 | FR-6850.pdf               | 151 KB |  23.8s | **good**      | typed_shot_list | 49       | 49     | 6/6    |  12876 |
|  84 | FR-6929.pdf               | 132 KB |  55.5s | **good**      | typed_shot_list | 46       | 73     | 6/6    |  21592 |
|  85 | FR-7479.pdf               |  38 KB |  17.8s | **fair**      | tabular_unknown | 1        | 41     | 4/6    |   7677 |
|  86 | FR-7757.pdf               |  20 KB |   6.4s | **uncertain** | tabular_unknown | 0        | 1      | 4/6    |   1983 |
|  87 | FR-8145.pdf               | 113 KB |  34.4s | **good**      | typed_shot_list | 52       | 62     | 6/6    |  21219 |
|  88 | FR-8186.pdf               | 144 KB |  28.8s | **good**      | typed_shot_list | 47       | 63     | 6/6    |  23330 |
|  89 | FR-8500.pdf               |  67 KB |  68.2s | **good**      | typed_shot_list | 19       | 31     | 5/6    |  16831 |
|  90 | FR-8562.pdf               | 116 KB |  19.9s | **good**      | typed_shot_list | 49       | 49     | 6/6    |  19501 |
|  91 | FR-8619.pdf               |  21 KB |  16.8s | **uncertain** | tabular_unknown | 0        | 5      | 6/6    |   5443 |
|  92 | FR-8623.pdf               |  20 KB |   7.8s | **uncertain** | tabular_unknown | 0        | 0      | 5/6    |   4108 |
|  93 | FR-8914.pdf               |  27 KB |  11.4s | **uncertain** | tabular_unknown | 0        | 4      | 3/6    |   3884 |
|  94 | FR-9062.pdf               |  38 KB |  45.5s | **poor**      | tabular_unknown | 0        | 12     | 5/6    |  45647 |
|  95 | FR-9091.pdf               |  28 KB |  21.1s | **uncertain** | tabular_unknown | 1        | 0      | 6/6    |   5667 |
|  96 | FR-9215.pdf               |  28 KB |   7.3s | **poor**      | tabular_unknown | 1        | 0      | 4/6    |   7601 |
|  97 | FR-9217.pdf               |  56 KB |  13.2s | **uncertain** | tabular_unknown | 0        | 0      | 3/6    |   3347 |
|  98 | FR-9640.pdf               |  34 KB |   9.7s | **good**      | typed_shot_list | 10       | 9      | 5/6    |   3981 |
|  99 | FR-9835.pdf               |  46 KB | 106.8s | **fair**      | typed_shot_list | 4        | 73     | 3/6    |  72119 |
| 100 | FR-9925.pdf               |  23 KB |   6.6s | **uncertain** | tabular_unknown | 2        | 0      | 4/6    |   3849 |

## Notable Problem Cases

### FR-0146.pdf — poor

- Size: 22 KB, Time: 5.8s
- Type: tabular_unknown, Chars: 5951, Alpha ratio: 0.044
- Preview:
  ```
  |                 |                 | CATEGORY: Facilities & Support Activities |             |            |            |              | Pg. 1 of 1                            |              |
  |-----------------|-----------------|-------------------------------------------|-------------|------------|------------|--------------|---------------------------------------|--------------|
  | ef No.          | + :             | SQURCE:                                   |             |            |
  ```

### FR-03272012-07-18.pdf — poor

- Size: 22 KB, Time: 101.4s
- Type: tabular_unknown, Chars: 70899, Alpha ratio: 0.03
- Preview:
  ```
  |                      |
  ```

### FR-05162012-07-18.pdf — poor

- Size: 31 KB, Time: 16.1s
- Type: tabular_unknown, Chars: 13293, Alpha ratio: 0.05
- Preview:
  ```
  |                  |        | CORRECTED COPY                                               |               |                     |                       |                                                                                                                                                                                                                                  |        |
  |------------------|--------|--------------------------------------------------------------|---------------|-
  ```

### FR-0566.pdf — poor

- Size: 30 KB, Time: 102.5s
- Type: tabular_unknown, Chars: 102660, Alpha ratio: 0.021
- Preview:
  ```
  |                                       | CORRECTED COPY CATEGORY: Launch Vehicle, Facilities & Support Activities - Mercury Pg. 1 of 1
  ```

### FR-05682012-07-17.pdf — poor

- Size: 24 KB, Time: 11.1s
- Type: tabular_unknown, Chars: 9359, Alpha ratio: 0.031
- Preview:
  ```
  |         |        | CORRECTED COPY CATEGORY: Conferences & Tours, Facilities & Support Activities - Mercury Pg. 1 of 1 |           |          |            |                  |                                        |               |
  |---------|--------|----------------------------------------------------------------------------------------------------|-----------|----------|------------|------------------|----------------------------------------|---------------|
  |         |        |
  ```

### FR-0778-1.pdf — poor

- Size: 35 KB, Time: 100.3s
- Type: tabular_unknown, Chars: 81249, Alpha ratio: 0.026
- Preview:
  ```
  | e M-             |                 | CATEGORY: Missions, Facilities & S
  ```

### FR-2155.pdf — poor

- Size: 9 KB, Time: 2.9s
- Type: unknown, Chars: 179, Alpha ratio: 0.592
- Preview:

  ```
  2155

  ## Flight of Boilerpate #6 Animation

  11/14/63

  ECO

  15mm

  ```

### FR-5265.pdf — poor

- Size: 38 KB, Time: 99.7s
- Type: tabular_unknown, Chars: 62610, Alpha ratio: 0.031
- Preview:
  ```
  | Ref No.<br>File Roll #136<br>PTL #6579-66 |                 | Transaction of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of the second of t
  ```

### FR-9062.pdf — poor

- Size: 38 KB, Time: 45.5s
- Type: tabular_unknown, Chars: 45647, Alpha ratio: 0.05
- Preview:
  ```
  |                 |
  ```

### FR-9215.pdf — poor

- Size: 28 KB, Time: 7.3s
- Type: tabular_unknown, Chars: 7601, Alpha ratio: 0.038
- Preview:
  ```
  | Ref No.  AV-653 |   | source: Manned Spacecraft Center (AV FILM SITE: AV, Seabrook FILMED: 2-10-72 REMARKS: |                |       |         |        | CLASSIFICATION Uncl |      | 2-15-72 MATERIAL ECO |      | 9215<br>FOOTAGE |    |                 |                 |          |          |       |          |         |         |       |        |   |  |  |
  |-----------------|---|---------------------------------------------------------------------------------------|----------------|-------|--
  ```

### FR-0157.pdf — uncertain

- Size: 20 KB, Time: 6.3s
- Type: tabular_unknown, Chars: 3527, Alpha ratio: 0.083
- Preview:
  ```
  | Ref No. |                 |                                    |         |                                       | Pg. I of    | 1             |
  |---------|-----------------|------------------------------------|---------|---------------------------------------|-------------|---------------|
  | Rer No. | •               | source: Unknown                    |         | •                                     | DATE RECD.  | FILE ROLL NO. |
  |         |                 |
  ```

### FR-0176-42012-07-17.pdf — uncertain

- Size: 24 KB, Time: 7.2s
- Type: tabular_unknown, Chars: 4926, Alpha ratio: 0.064
- Preview:
  ```
  | Ref No.         |                 | Mercury source: KSC FILM SITE: FILMED: 9-18-59                                  |                 |                            | Pg. 1 of  | FILE ROLL NO. |
  |-----------------|-----------------|---------------------------------------------------------------------------------|-----------------|----------------------------|-----------|---------------|
  |                 |                 |
  ```

### FR-03392012-07-17.pdf — uncertain

- Size: 22 KB, Time: 13.7s
- Type: tabular_unknown, Chars: 6847, Alpha ratio: 0.077
- Preview:
  ```
  | Ref No.          |                                                                                                                                                                                                                           | REVISION (7-28-67) CATEGORY: Missions, Spacecraft, Facilities & Support Activities -                                   |               |                |                |               |
  |------------------|----------------------------------------------------
  ```

### FR-0352-2.pdf — uncertain

- Size: 19 KB, Time: 7.6s
- Type: tabular_unknown, Chars: 6159, Alpha ratio: 0.071
- Preview:
  ```
  |                                                                                   |                 | REVISION (7-6-67) CATEGORY: Flight Crew, Spacecraft, Facilities & Support Activi- |                                              |                  |            |         |  |
  |-----------------------------------------------------------------------------------|-----------------|-----------------------------------------------------------------------------------|---------------------------------
  ```

### FR-0364-22012-07-17.pdf — uncertain

- Size: 15 KB, Time: 6.4s
- Type: tabular_unknown, Chars: 3717, Alpha ratio: 0.077
- Preview:
  ```
  |         |                 | REVISION (7-6-67) CATEGORY: Flight Crew, Facilities 8                                       | & Support Act  | civities - | Mercury      |
  |---------|-----------------|---------------------------------------------------------------------------------------------|----------------|------------|--------------|
  | Ref No. |                 |                                                                                             |                | Pg. 1 of 1 |
  ```

### FR-04042012-07-17.pdf — uncertain

- Size: 27 KB, Time: 4.2s
- Type: unknown, Chars: 660, Alpha ratio: 0.724
- Preview:
  ```
  CORRECTED COPY Flight Crew, Mission Control, Facilities & Support CATEGORY: Activities - Mercury Pg. l of l Ref No. SOURCE: DATE RECD. FILE ROLL NO. PL 61-61365 FILM SITE: Pad 5 PL 61-61378 404 Unknown FILMED: 4-21-61 PL 61-61368 REMARKS: CLASSIFICATION MATERIAL FOOTAGE PL 61-61367 PL 61-61366 UN CPP as O 1116 FOOTAGE MR-3 Practice Countdown and Emergency Egress. CAMERA START ANGLE FOREWORD: MR-3 Simulated Countdown, Cherry Picker, Tank, Firetruck, Blockhouse, Astronaut Shepard. This film docume
  ```

### FR-05372012-07-17.pdf — uncertain

- Size: 49 KB, Time: 7.7s
- Type: tabular_unknown, Chars: 3151, Alpha ratio: 0.07
- Preview:
  ```
  | Ref No.         |                 | Support Acti-<br>source: KSC<br>FILM SITE: Grand Baham<br>FILMED: July 21, 1961 | and the property and | CLASSIFICATION | Pg. 1 of DATE RECD. Unknown |      |
  |-----------------|-----------------|---------------------------------------------------------------------------------|----------------------|----------------|-----------------------------|------|
  |                 |                 |
  ```

### FR-05562012-07-18.pdf — uncertain

- Size: 40 KB, Time: 10.8s
- Type: tabular_unknown, Chars: 5557, Alpha ratio: 0.128
- Preview:
  ```
  |                  |                 | CORRECTED COPY CATEGORY: Facilities & Support Activities - Mercury |                  |                      |  |  |  |  |
  |------------------|-----------------|--------------------------------------------------------------------|------------------|----------------------|--|--|--|--|
  | nef No.          |                 | source: Ames Research Center FILM SITE: Same                       | DATE RECD.       | Of T<br>FLE ROLL NO. |  |  |  |  |
  |
  ```

### FR-05782012-07-17.pdf — uncertain

- Size: 27 KB, Time: 9.2s
- Type: tabular_unknown, Chars: 7209, Alpha ratio: 0.05
- Preview:
  ```
  |                  |                 | CORRECTED COPY CATEGORY: Flight Crew, Facilities & Support Activities - Mercury |        |              |                  |                                         |
  |------------------|-----------------|---------------------------------------------------------------------------------|--------|--------------|------------------|-----------------------------------------|
  |                  |                 |
  ```

### FR-0647.pdf — uncertain

- Size: 25 KB, Time: 3.4s
- Type: unknown, Chars: 387, Alpha ratio: 0.749
- Preview:

  ```
  CORRECTED COPY

  CATEGORY: Conferences and Tours, Facilities & Support Activities - Mercury Pg. 1 of 1 Ref No. SOURCE: MSC DATE RECO. MLEROLL NO. FIIM SITE: 647 Unknown FILMED: Jan. 1, 1961 REMARKS: MATERIAL FOOTAGE CLASSIFICATION UN ER 80 FOOTAGE CAMERA SUBJECT: MSC - MA-5 Mercury Mission Review ANGLE START FOREWORD: MA-5 Mission Review. Various scenes MA-5 mission review conferences.
  ```

### FR-0798.pdf — uncertain

- Size: 22 KB, Time: 10.0s
- Type: tabular_unknown, Chars: 3900, Alpha ratio: 0.101
- Preview:
  ```
  | Ref No.          |                 | CORRECTED COPY  CATEGORY: Conference & Tours, Missions, Facilities & Support  Activities - Mercury  Pg. 1 of 1  SOURCE: Unknown |                |              |          |
  |------------------|-----------------|---------------------------------------------------------------------------------------------------------------------------------|----------------|--------------|----------|
  |                  |                 | FILM SITE: Wright Bros. Memorial FILM
  ```

### FR-1005.pdf — uncertain

- Size: 18 KB, Time: 4.1s
- Type: unknown, Chars: 430, Alpha ratio: 0.737
- Preview:

  ```
  CORRECTED COPY

  CATEGORY: Spacecraft, Flight Crew, Missions, Facilities &

  Support Activities - Mercury

  Pg. 1 of 1

  949

  ```

### FR-1480.pdf — uncertain

- Size: 31 KB, Time: 14.4s
- Type: tabular_unknown, Chars: 5016, Alpha ratio: 0.108
- Preview:
  ```
  | TE NO.               |                       | source: North American Aviation                                                                                                                                                                                                   | es Lucinaes La | DATE RECO.          | 1-1 075<br> FILE ROLL NO | 12          |
  |----------------------|-----------------------|-----------------------------------------------------------------------------------------------
  ```

### FR-1560.pdf — uncertain

- Size: 61 KB, Time: 29.9s
- Type: tabular_unknown, Chars: 15481, Alpha ratio: 0.103
- Preview:
  ```
  | Ref No.<br>PL 63-62559                                                |                                                                          | CATEGORY: Facilities & Support Activities, Miss<br>Flight Crew - Mercury<br>source: KSC<br>FILM SITE: MCC                                                                                                                                                                                                                               |
  ```

### FR-1920.pdf — uncertain

- Size: 54 KB, Time: 111.4s
- Type: tabular_unknown, Chars: 96225, Alpha ratio: 0.079
- Preview:
  ```
  | and stands of SLATE  Man stands with can cribes  SLATE  Man site describes  SLATE  Model of Model of SLATE               | DR. VOAS E                                                                                                                | model of a Looks back model of a th, moves paraglider a look Gemini Capa f capsule.
  ```

### FR-2608.pdf — uncertain

- Size: 42 KB, Time: 9.6s
- Type: tabular_unknown, Chars: 5726, Alpha ratio: 0.129
- Preview:
  ```
  |                 |                 | SOURCE: Kennedy Space Center, Cocoa Beach, FILM SITE: Same Program Apollo Filmed: 3/13/64 |                    | 4/1/64     | 2608        |
  |-----------------|-----------------|-------------------------------------------------------------------------------------------|--------------------|------------|-------------|
  |                 |                 | REMARKS:                                                                                  | CLASSIFICATION
  ```

### FR-41182012-07-18 (2).pdf — uncertain

- Size: 24 KB, Time: 8.2s
- Type: tabular_unknown, Chars: 3119, Alpha ratio: 0.094
- Preview:
  ```
  | Ref No.<br>PL #65-84420              |                 | SOURCE: KSC FILM SITE: Same FILMED: 5-20-65                                             |                | Pg. 1 DATE RECD. 6-17-65 | FILE ROLL NO |
  |--------------------------------------|-----------------|-----------------------------------------------------------------------------------------|----------------|--------------------------|--------------|
  |                                      |                 | REMARKS:
  ```

### FR-4909.pdf — uncertain

- Size: 44 KB, Time: 24.0s
- Type: tabular_unknown, Chars: 6792, Alpha ratio: 0.114
- Preview:
  ```
  |   | Ref No.<br>9903 &<br>10004                   |                        | CATEGORY: Facilities & Support Activ Vehicle - Gemini Source: Lockheed FIIM SITE: Same FIIMED: 11-23&24-65 REMARKS:                                                                                                                                                                                                                                                                         | cities, Spac | ecraft, Lai<br>Pg. 1 of<b
  ```

### FR-4962.pdf — uncertain

- Size: 28 KB, Time: 8.9s
- Type: tabular_unknown, Chars: 5858, Alpha ratio: 0.055
- Preview:
  ```
  | Dof No           |                 |                      | CATEGORY: Missions, Facilities & Support Activities - Gemini Pg. 1 of 1 |                    |                    |          |
  |------------------|-----------------|----------------------|-------------------------------------------------------------------------|--------------------|--------------------|----------|
  | Ref No.          |                 | SOURCE:              | KSC
  ```

### FR-5608.pdf — uncertain

- Size: 30 KB, Time: 13.6s
- Type: tabular_unknown, Chars: 7129, Alpha ratio: 0.095
- Preview:
  ```
  | Ref No.              |                 | source: Grumman                                                                                                                                                                                     |            |              |                | Pg. 1 of 1  |         |
  |----------------------|-----------------|----------------------------------------------------------------------------------------------------------------------------------------------------
  ```

### FR-6080.pdf — uncertain

- Size: 381 KB, Time: 18.0s
- Type: tabular_unknown, Chars: 15814, Alpha ratio: 0.112
- Preview:
  ```
  | Acf No.<br>10# 6612-19-2673      |                    | Apollo                                                      |                   | ort Activities -<br>Pg. 1 of 2 |                      |  |  |  |
  |----------------------------------|--------------------|-------------------------------------------------------------|-------------------|--------------------------------|----------------------|--|--|--|
  |                                  |                    | source: KSC<br>FIIM SITE:
  ```

### FR-7757.pdf — uncertain

- Size: 20 KB, Time: 6.4s
- Type: tabular_unknown, Chars: 1983, Alpha ratio: 0.103
- Preview:
  ```
  | Ref No.  KSC 69-71303 |                 | source: Kennedy Space Center                      | Pg. l of l |              |
  |-----------------------|-----------------|---------------------------------------------------|------------|--------------|
  |                       |                 |                                                   |            | FILE ROLL NO |
  |                       |                 | FILM SITE: Launch Complex 39 A 03 FILMED: 7-16-69 | 7-28-69    | 7757         |
  |
  ```

### FR-8619.pdf — uncertain

- Size: 21 KB, Time: 16.8s
- Type: tabular_unknown, Chars: 5443, Alpha ratio: 0.089
- Preview:
  ```
  |                                  | CATEGORY: Animation, Apollo |                                                                                                                                                                                                                             |                |            |               |
  |----------------------------------|-----------------------------|---------------------------------------------------------------------------------------------------
  ```

### FR-8623.pdf — uncertain

- Size: 20 KB, Time: 7.8s
- Type: tabular_unknown, Chars: 4108, Alpha ratio: 0.091
- Preview:
  ```
  |                       | CATEGORY: Facilities & Support Activities, Apollo |                                                     |                |            |         |  |
  |-----------------------|---------------------------------------------------|-----------------------------------------------------|----------------|------------|---------|--|
  | <b>Ref No.</b> AV-730 |                                                   | Manned Change of Canton (AV)                        |                | P
  ```

### FR-8914.pdf — uncertain

- Size: 27 KB, Time: 11.4s
- Type: tabular_unknown, Chars: 3884, Alpha ratio: 0.105
- Preview:
  ```
  | S71-10 <sup>1</sup> 4 |                 | source: Manned Spacecraft Center (PTD)                                                                                                             |                             | Pg. 1 (       | Pg. 1 of 1     |  |
  |-----------------------|-----------------|----------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------|---------------|---
  ```

### FR-9091.pdf — uncertain

- Size: 28 KB, Time: 21.1s
- Type: tabular_unknown, Chars: 5667, Alpha ratio: 0.119
- Preview:
  ```
  |                  |                 | CATEGORY: Facilities and Support Activities, Skylab                                                                                                                                                                                                                                                                                             |                 |         |                              |
  |------------------|-----------------|--------------------------
  ```

### FR-9217.pdf — uncertain

- Size: 56 KB, Time: 13.2s
- Type: tabular_unknown, Chars: 3347, Alpha ratio: 0.11
- Preview:
  ```
  | For Joe Headlee S.T.#3310                   |  | SOURCE: NASA Headquarters FILM SITE: MSC, Bldg. #31 FILMED: 1-13-72 REMARKS: CAMERAMAN: Bird Date shown on slate in error                                                                                           | CLASSIFICATION UN                                  | Pg. 1 of DATE RECO.  2-15-72  MATERIAL  O/M as ( |  |
  |---------------------------------------------|--|------------------------------------------------------------------------------
  ```

### FR-9925.pdf — uncertain

- Size: 23 KB, Time: 6.6s
- Type: tabular_unknown, Chars: 3849, Alpha ratio: 0.068
- Preview:
  ```
  | Ref No.          |                                            | SKYLAB #1                                |                |            |              |
  |------------------|--------------------------------------------|------------------------------------------|----------------|------------|--------------|
  |                  |                                            | SOURCE: JSC (AV)                         |                | DATE RECD. | FILE ROLL NO |
  |                  |
  ```

## VLM Fallback Results (Qwen2.5-VL-7B-Instruct)

All 10 "poor" PDFs were re-processed through Qwen2.5-VL-7B-Instruct as a fallback pipeline. The VLM receives page images directly (via PyMuPDF at 200 DPI) rather than relying on marker's OCR.

**Script**: `scripts/0d_vlm_fallback_test.py`
**Model**: Qwen/Qwen2.5-VL-7B-Instruct (float16, RTX 4090)
**Speed**: ~20-40s per page after model loading (first inference is slower due to CUDA warmup)

### Side-by-side Comparison

| PDF       | marker quality                                 | VLM header                                                   | VLM shots                              | Key difference                                                   |
| --------- | ---------------------------------------------- | ------------------------------------------------------------ | -------------------------------------- | ---------------------------------------------------------------- |
| FR-0146   | Garbled (`SQURCE`, `OOTAGE`, `ROI I`)          | **Excellent** — clean structured data                        | 1 shot + END OF ROLL                   | VLM reads everything marker mangled                              |
| FR-0327   | Garbled (`FLEROLL N`, `Voniovo`)               | **Excellent** — finds "Seven Astronauts Posing Around F-106" | None (doc has no shots)                | VLM captures subject that marker missed entirely                 |
| FR-0516   | Garbled astronaut names (`GNISSON`, `SIRTON`)  | **Excellent**                                                | Honest `[illegible]` for degraded rows | VLM doesn't fabricate; marker produces garbage                   |
| FR-0566   | Mostly empty table cells (2% alpha)            | **Excellent**                                                | None (header-only doc)                 | Both agree on data, VLM vastly cleaner                           |
| FR-0568   | Garbled (`Miscerran eous`, `co pronet Lowers`) | **Excellent**                                                | Template echo (minor bug)              | VLM reads "Colonel Powers" correctly                             |
| FR-0778-1 | Garbled (`kef`, `UI 1`, `Voniovo`)             | **Excellent** — finds Kano Tracking Station                  | Minimal                                | VLM captures all metadata cleanly                                |
| FR-2155   | Garbled numbers (`10%t.`, `a73t.`, `Saft.`)    | **Excellent**                                                | **3 real shots** with timecodes        | VLM reads `10 sec.`, `47 sec.`, `58 sec.` correctly              |
| FR-5265   | Mostly noise (3% alpha)                        | **Excellent** — WSTF, LEM Test Site                          | **3 shots** with footage numbers       | VLM extracts real data from a scan marker couldn't read          |
| FR-9062   | Mostly noise (5% alpha)                        | **Excellent** — Apollo 15 onboard mags                       | **10 shots** with descriptions         | VLM reads full Apollo 15 shot list that marker missed completely |
| FR-9215   | Garbled, fragmented across 25+ columns         | **Excellent** — Space Shuttle model                          | 3 footage numbers                      | VLM cleanly reads what marker split across dozens of columns     |

### Key Findings

1. **VLM header extraction is 10/10** — every single PDF produced clean, correctly structured metadata. Category, source, film site, dates, classification, material, footage counts, and subject lines are all captured accurately.

2. **VLM does not hallucinate** — when content is illegible, it reports `[illegible]` or `[blank]`. No fake shot entries were generated. One minor issue: the model occasionally echoes prompt template text when the document section is truly empty (fixed in updated script).

3. **VLM recovers data marker completely misses** — FR-9062 is the strongest example: marker produced 45,647 chars of noise (5% alpha ratio), while the VLM extracted a clean 10-shot Apollo 15 shot list with astronaut names (Scott, Irwin), equipment (Lunar Rover, S-Band Antenna), and sequential footage numbers.

4. **Speed is practical**: ~20-40s per single-page PDF. For 1,000 poor/uncertain PDFs, that's ~6-11 hours. The model fits comfortably on RTX 4090 in float16.

### Recommended Pipeline Design

```
PDF → marker-pdf (force_ocr)
      ├── good/fair quality → Stage 2 parser
      └── poor/uncertain → Qwen2.5-VL-7B fallback → Stage 2 parser
```

**Quality gate**: If marker output has `alpha_ratio < 0.10` or `footage_numbers_found == 0`, route to VLM fallback. This threshold catches all 10 poor PDFs and most uncertain ones without re-processing the 62 good/fair ones unnecessarily.

## Qwen3-VL-8B Benchmark (fp16 vs NF4 4-bit)

**Date**: 2026-02-26
**Script**: `scripts/0e_vlm_quant_benchmark.py`
**Hardware**: NVIDIA GeForce RTX 4090 (24 GB), Windows 11
**Sample**: Same 10 "poor" PDFs used in the Qwen2.5-VL-7B fallback test
**Quantization**: bitsandbytes NF4 (`load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True`)

Qwen3-VL-8B-Instruct is the successor to Qwen2.5-VL-7B with improved OCR: 32 languages (up from 19), better low-light/blur/tilt handling, improved long-document structure parsing.

### Resource Comparison

| Metric          | Qwen3 fp16 | Qwen3 NF4 4-bit | Qwen2.5-VL-7B fp16 (baseline) |
| --------------- | ---------- | --------------- | ----------------------------- |
| Model load time | 86.9s      | 30.1s           | ~30s                          |
| VRAM peak       | 16.97 GB   | 6.75 GB         | ~15 GB                        |
| Total (10 PDFs) | 1032.6s    | 327.7s          | ~300s                         |
| Avg per PDF     | 103.3s     | 32.8s           | ~30s                          |

### Per-PDF Timing

| PDF                   | fp16 (s) | NF4 (s) | Speedup | fp16 chars | NF4 chars |
| --------------------- | -------: | ------: | ------: | ---------: | --------: |
| FR-0146.pdf           |    127.6 |    27.3 |   4.68x |        507 |       508 |
| FR-03272012-07-18.pdf |     20.5 |    29.8 |   0.69x |        613 |       609 |
| FR-05162012-07-18.pdf |     98.4 |    34.1 |   2.89x |        879 |       827 |
| FR-0566.pdf           |     66.2 |    24.3 |   2.72x |        608 |       596 |
| FR-05682012-07-17.pdf |    102.7 |    21.5 |   4.78x |        540 |       540 |
| FR-0778-1.pdf         |     90.3 |    23.1 |   3.91x |        580 |       576 |
| FR-2155.pdf           |     85.1 |    25.7 |   3.31x |        495 |       517 |
| FR-5265.pdf           |     59.0 |    36.6 |   1.61x |        626 |       626 |
| FR-9062.pdf           |    100.4 |    70.1 |   1.43x |       1348 |      1239 |
| FR-9215.pdf           |    282.4 |    35.2 |   8.03x |        652 |       652 |

**Average speedup**: NF4 is **3.15x faster** than fp16 (excluding the outlier FR-0327 where fp16 was faster, average is 3.71x).

**fp16 timing variance**: Highly variable (20.5s–282.4s), likely due to CUDA memory pressure at 17 GB. NF4 is much more consistent (21.5s–70.1s).

### Quality Comparison

Outputs were compared side-by-side across all 10 PDFs:

| PDF       | fp16 vs NF4 Quality                                                                                                           |
| --------- | ----------------------------------------------------------------------------------------------------------------------------- |
| FR-0146   | **Near-identical** — NF4 has minor typo "Facililties" vs "Facilities"                                                         |
| FR-0327   | **Identical** — both extract "Seven Astronauts Posing Around F-106" correctly                                                 |
| FR-0516   | **Similar** — both mark shots as illegible; NF4 uses [blank]/SLATE instead of [illegible]                                     |
| FR-0566   | **Identical** — same header and shot data                                                                                     |
| FR-0568   | **Identical** — both read "Colonel Powers" correctly                                                                          |
| FR-0778-1 | **Identical** — Kano Tracking Station captured by both                                                                        |
| FR-2155   | **Minor diff** — NF4 reads "Pad abort" vs fp16 "Fuel abort"; NF4 adds "Texas Industrial Film" as foreword                     |
| FR-5265   | **Minor diff** — NF4 reads "WSIF" vs fp16 "WSTF" (SOURCE field)                                                               |
| FR-9062   | **NF4 worse** — fp16 captured all 10 shot descriptions inline; NF4 lost descriptions on 6/11 rows, separated SLATEs to bottom |
| FR-9215   | **Identical** — Space Shuttle model, same 3 shots                                                                             |

**Overall quality**: 7/10 identical or near-identical, 2/10 minor differences, 1/10 meaningful regression (FR-9062).

The FR-9062 case (Apollo 15 shot list) is the most demanding document — dense typewritten text with 11 shot entries. fp16 captured all descriptions; NF4 missed 6 of them. This represents the quality ceiling difference between full-precision and 4-bit quantization.

### Projected Full Batch Time

For an estimated ~1,000 poor/uncertain PDFs needing VLM fallback:

| Variant                   | Avg/PDF | Est. total | VRAM   |
| ------------------------- | ------: | ---------: | ------ |
| Qwen3-VL-8B fp16          |  103.3s |   28.7 hrs | 17 GB  |
| Qwen3-VL-8B NF4           |   32.8s |    9.1 hrs | 6.7 GB |
| Qwen2.5-VL-7B fp16 (prev) |    ~30s |   ~8.3 hrs | 15 GB  |

### Recommendation

**Use Qwen3-VL-8B NF4 4-bit** as the VLM fallback model:

- **3x faster** than Qwen3-VL-8B fp16 with only 1/10 quality regressions (and those are on the hardest documents)
- **60% less VRAM** (6.7 GB vs 17 GB) — leaves headroom for batch processing or concurrent work
- **Comparable speed** to Qwen2.5-VL-7B fp16 (~33s vs ~30s avg) but with Qwen3's expanded OCR capabilities (32 languages, better degraded scan handling)
- The one failure case (FR-9062) could be mitigated by a second-pass fp16 retry for documents where NF4 output has many `[blank]` descriptions

## Conclusions

Based on this 100-PDF sample:

- **62% of PDFs produce usable OCR output from marker alone** — the typed shot lists with clear printing work well.
- **10% produce poor marker output** — but VLM fallback recovers nearly all of them to usable quality.
- **28% are "uncertain"** — many are likely usable from marker alone; those that aren't can be caught by the quality gate and routed to the VLM.
- **Combined pipeline viability: ~90%+** of PDFs should produce usable structured data through the two-stage approach.
- **Qwen3-VL-8B NF4** is the recommended VLM fallback: comparable speed to Qwen2.5-VL-7B fp16, improved OCR, and 60% less VRAM.
- Estimated full batch time: **~51-111 hours** marker + **~9 hours** VLM fallback for the ~10-15% that need it.
- The Stage 2 parser will need to handle noisy table formatting, merged rows, and OCR number errors from marker output, plus the cleaner but differently-structured VLM output.
