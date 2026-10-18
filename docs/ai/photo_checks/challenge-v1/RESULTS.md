# Photo-admission development challenge results

270 checks from 43 real source images; derivatives are correlated. No pooled accuracy. No reserved disease-test images. Original decisions reproduce.

| Group | Checks | Accepted | Quality blocked | Content blocked | Expected-decision disagreements | Changed from original |
|---|---:|---:|---:|---:|---:|---:|
| original_skin | 37 | 37 | 0 | 0 | 0 | 0 |
| dimmer | 37 | 36 | 0 | 1 | unlabelled probe | 1 |
| brighter | 37 | 36 | 0 | 1 | unlabelled probe | 1 |
| severe_blur | 37 | 0 | 37 | 0 | 0 | 37 |
| low_resolution | 37 | 0 | 37 | 0 | 0 | 37 |
| skin_screenshot | 37 | 35 | 0 | 2 | 35 | 2 |
| cropped_skin_screenshot | 37 | 37 | 0 | 0 | unlabelled probe | 0 |
| object | 6 | 0 | 0 | 6 | 0 | 0 |
| document | 1 | 0 | 0 | 1 | 0 | 0 |
| dashboard | 1 | 0 | 0 | 1 | 0 | 0 |
| pattern | 1 | 1 | 0 | 0 | 1 | 0 |
| black | 1 | 0 | 1 | 0 | 0 | 0 |
| white | 1 | 0 | 1 | 0 | 0 | 0 |

## All expected-decision disagreements

- `-7776857652459777696` / skin_screenshot: expected reject, accepted; checks passed.
- `3083550471820565612` / skin_screenshot: expected reject, accepted; checks passed.
- `3377584127732041409` / skin_screenshot: expected reject, accepted; checks passed.
- `-919660371744832007` / skin_screenshot: expected reject, accepted; checks passed.
- `7530181678510252673` / skin_screenshot: expected reject, accepted; checks passed.
- `5275181661240813075` / skin_screenshot: expected reject, accepted; checks passed.
- `-7743291557587090042` / skin_screenshot: expected reject, accepted; checks passed.
- `-8299809889773574040` / skin_screenshot: expected reject, accepted; checks passed.
- `3846988567346853286` / skin_screenshot: expected reject, accepted; checks passed.
- `-8111125152560753978` / skin_screenshot: expected reject, accepted; checks passed.
- `3950839687124807995` / skin_screenshot: expected reject, accepted; checks passed.
- `5604714673774290686` / skin_screenshot: expected reject, accepted; checks passed.
- `-130215202506383973` / skin_screenshot: expected reject, accepted; checks passed.
- `1850198155303184343` / skin_screenshot: expected reject, accepted; checks passed.
- `5475014386524307360` / skin_screenshot: expected reject, accepted; checks passed.
- `-4662194556963063742` / skin_screenshot: expected reject, accepted; checks passed.
- `2562611754724897853` / skin_screenshot: expected reject, accepted; checks passed.
- `255207051194135479` / skin_screenshot: expected reject, accepted; checks passed.
- `-2986702064294375651` / skin_screenshot: expected reject, accepted; checks passed.
- `4412120753157054552` / skin_screenshot: expected reject, accepted; checks passed.
- `4039144254966056317` / skin_screenshot: expected reject, accepted; checks passed.
- `-3406507834674402591` / skin_screenshot: expected reject, accepted; checks passed.
- `7327821802957291496` / skin_screenshot: expected reject, accepted; checks passed.
- `-5781127683500413767` / skin_screenshot: expected reject, accepted; checks passed.
- `-2518265086444700975` / skin_screenshot: expected reject, accepted; checks passed.
- `5080913691893238848` / skin_screenshot: expected reject, accepted; checks passed.
- `-6776518044035331491` / skin_screenshot: expected reject, accepted; checks passed.
- `-525038500404864710` / skin_screenshot: expected reject, accepted; checks passed.
- `6691291750986670327` / skin_screenshot: expected reject, accepted; checks passed.
- `4716235809681478742` / skin_screenshot: expected reject, accepted; checks passed.
- `-1694584375310842794` / skin_screenshot: expected reject, accepted; checks passed.
- `-2420670963295906064` / skin_screenshot: expected reject, accepted; checks passed.
- `2600794538114860588` / skin_screenshot: expected reject, accepted; checks passed.
- `1872413092507744029` / skin_screenshot: expected reject, accepted; checks passed.
- `-5642777666164872473` / skin_screenshot: expected reject, accepted; checks passed.
- `synthetic-pattern` / pattern: expected reject, accepted; checks passed.

Brightness probes have no ground truth for clinical usability. Screenshots are synthetic; cropped screenshots intentionally preserve skin pixels. These are not independent patients. No verified skin-tone subgroup labels, expert quality labels or new phone capture dataset. No prompts/thresholds changed in response to this run. Full case hashes, decisions and quality metrics are in results.json.
