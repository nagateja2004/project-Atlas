# Synthetic Vendor Submittal — BMS-A Alternate

**SYNTHETIC EPC DEMO DATA — NOT FOR CONSTRUCTION**  
**Project ID:** `atlas-demo-dc-02` | **Document ID:** `SUB-BMSA-002`  
**Vendor:** OmniLogic Automation (fictional) | **Model:** OL-BAC-3500

## Page 1

OmniLogic Automation proposes the OL-BAC-3500 for BMS-A. This fictional submittal intentionally contains 2 comparison cases.

| Attribute | Offered value |
| --- | --- |
| Protocols | BACnet/IP only |
| Point capacity | 3,500 points |
| Alarm latency | 1.8 seconds |
| Trend storage | 12 months at one-minute resolution |
| Server redundancy | N+1 with automatic failover |

## Page 2

### Vendor deviation note

- The OL-BAC-3500 supervisory platform speaks BACnet/IP. Modbus TCP devices are reached through a separate protocol gateway.
- Licensed point capacity is 3,500 monitored points.

| Synthetic spec clause | Vendor response |
| --- | --- |
| 2.2.1 protocol support | BACnet/IP only offered |
| 2.2.2 point capacity | 3,500 points offered |

**Intentional demo deviations:** protocol support, point capacity.
