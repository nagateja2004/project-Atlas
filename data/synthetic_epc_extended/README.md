# Extended synthetic EPC corpus

**SYNTHETIC EPC DEMO DATA — NOT AN OFFICIAL STANDARD**

**Project ID:** `atlas-demo-dc-02`

A second, independent synthetic corpus covering six equipment items that the original
`data/synthetic_epc/` corpus does not: a standby generator, an air-cooled chiller, a
power distribution unit, a cast-resin transformer, a clean-agent fire suppression
system, and a building management system.

## Load this into its own project

`GET /projects/{id}/compliance/evaluation` scores every finding in a project against
`data/synthetic_epc/ground_truth.json`, which describes the original six planted
deviations only. Uploading this corpus into the seeded demo project would register its
findings as false positives and break the reported 6/0/0/6 result.

Create a separate project and load it there. Project scoping is enforced by the API,
so the two corpora stay independent.

## Contents

| Category | Files |
| --- | --- |
| Specifications | 6 |
| Submittals (compliant controls) | 6 |
| Submittals (with planted deviations) | 6 |
| Commissioning procedures | 6 |
| RFIs | 8 |
| Meeting minutes | 2 |
| Change orders | 1 |
| Schedule (CSV) | 1 |
| Shipment simulation (JSON) | 1 |
| Metadata (JSON) | 2 |
| Ground truth (JSON) | 1 |
| README | 0 |
| **Total** | **40** |

## Planted cases

Every equipment item has one compliant control submittal and one deviating submittal
carrying exactly two planted deviations, giving twelve expected findings and six
expected clean submittals. `ground_truth.json` names each one.

| Equipment | Clause | Required | Offered |
| --- | --- | --- | --- |
| GEN-A | 2.2.1 | not less than 2,500 kW | 2,250 kW |
| GEN-A | 2.2.2 | not less than 24 hours | 16 hours |
| CH-A | 2.2.1 | not less than 1,400 kW | 4,000,000 BTU/hr (approximately 1,172 kW) |
| CH-A | 2.2.3 | R-513A | R-410A |
| PDU-A | 2.2.1 | not less than 300 kVA | 225 kVA |
| PDU-A | 2.2.2 | K-13 | K-4 |
| XFMR-A | 2.2.1 | not less than 2,000 kVA | 1,600 kVA |
| XFMR-A | 2.2.3 | not greater than 100 K | 115 K |
| FS-A | 2.2.1 | not less than 7.0 percent | 6.2 percent |
| FS-A | 2.2.2 | not greater than 10 seconds | 14 seconds |
| BMS-A | 2.2.1 | Modbus TCP and BACnet/IP | BACnet/IP only |
| BMS-A | 2.2.2 | not less than 5,000 points | 3,500 points |

### Deliberate unit-conversion case

CH-A capacity is offered as **4,000,000 BTU/hr** against a **1,400 kW** requirement.
That converts to approximately **1172 kW**, so the shortfall is invisible until the
units are normalised. A comparison that comments only on the raw numbers has not
actually done the work.

### Deliberate near-duplicate RFI pair

`RFI-103` and `RFI-104` ask the same unit-basis question in different words, for
duplicate detection.

### Planted schedule delay

`T-240` (CH-A delivery) is forecast 28 days late and propagates through installation,
mechanical energization, and the integrated systems test.

## Provenance

Every project, vendor, equipment, model, value, date, and clause here is fictional.
Nothing reproduces or claims any requirement of TIA-942, BICSI, Uptime Institute, UL,
AHRI, NFPA, or any other standards body. No customer, employer, supplier, shipment, or
site data is represented.

Regenerate with:

```bash
python3 scripts/generate_extended_corpus.py
```
