# Synthetic Commissioning Procedure — CH-A

**SYNTHETIC EPC DEMO DATA — NOT AN OFFICIAL STANDARD**  
**Project ID:** `atlas-demo-dc-02`  
**Document ID:** `CX-CHA-001`  
**Equipment tag:** CH-A | **Location:** Chiller Yard CY-01

## Page 1

These ordered steps are fictional and exist to exercise deterministic pass and fail evaluation. They are not an external commissioning standard.

### Step 1

**Prerequisite:** Pipework pressure test complete

**Instruction:** Flush and fill the chilled-water loop and record water quality.

**Acceptance criterion:** Water quality within vendor limits before start-up.

### Step 2

**Prerequisite:** Loop fill complete

**Instruction:** Start each refrigeration circuit independently and record suction and discharge pressures.

**Acceptance criterion:** Both circuits start and hold pressures within vendor limits.

### Step 3

**Prerequisite:** Circuit start-up complete

**Instruction:** Verify capacity by heat balance across the evaporator at design flow.

**Acceptance criterion:** Measured capacity not less than 1,400 kW at design conditions.

### Step 4

**Prerequisite:** Capacity test complete

**Instruction:** Fail one refrigeration circuit and record retained capacity.

**Acceptance criterion:** Remaining circuit sustains operation without a plant trip.

### Step 5

**Prerequisite:** BMS-A integration complete

**Instruction:** Verify BACnet/IP point mapping at the BMS.

**Acceptance criterion:** All mapped points readable at the BMS with correct units.
