# Synthetic Commissioning Procedure — BMS-A

**SYNTHETIC EPC DEMO DATA — NOT AN OFFICIAL STANDARD**  
**Project ID:** `atlas-demo-dc-02`  
**Document ID:** `CX-BMSA-001`  
**Equipment tag:** BMS-A | **Location:** Control Room CR-01

## Page 1

These ordered steps are fictional and exist to exercise deterministic pass and fail evaluation. They are not an external commissioning standard.

### Step 1

**Prerequisite:** Field device install complete

**Instruction:** Verify point-to-point mapping for GEN-A, CH-A, PDU-A, XFMR-A and FS-A.

**Acceptance criterion:** Every mapped point readable with correct units and scaling.

### Step 2

**Prerequisite:** Point mapping verified

**Instruction:** Measure alarm latency from field event to workstation for ten alarms.

**Acceptance criterion:** All ten latencies not greater than 2 seconds.

### Step 3

**Prerequisite:** Latency test complete

**Instruction:** Fail the primary supervisory server and confirm automatic failover.

**Acceptance criterion:** Failover completes with no loss of alarm annunciation.

### Step 4

**Prerequisite:** Failover verified

**Instruction:** Verify the audit log records a set-point change with operator identity.

**Acceptance criterion:** Audit entry present with operator identity and timestamp.
