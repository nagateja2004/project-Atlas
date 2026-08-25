"""
Generate a second synthetic EPC corpus: data/synthetic_epc_extended/.

Why a separate directory and a separate project id rather than adding to
data/synthetic_epc/:

  GET /projects/{id}/compliance/evaluation scores EVERY ComplianceFinding row in
  a project against the six entries in data/synthetic_epc/ground_truth.json.
  Running comparisons on new specification/submittal pairs inside the seeded
  demo project would therefore register them as false positives and destroy the
  6/0/0/6 headline metric. Atlas is project-scoped, so the clean answer is to
  load this corpus into its own project, where it carries its own ground truth.

Every value here is fictional. The corpus deliberately mirrors the conventions
of the original: three-page specifications with numbered clauses, one compliant
control submittal and one deviating submittal per equipment item, and a ground
truth file naming each planted case so detection can be scored rather than
eyeballed.

    python3 scripts/generate_extended_corpus.py            # write the corpus
    python3 scripts/generate_extended_corpus.py --check     # verify, write nothing

One deviation is deliberately expressed in different units from its
specification (chiller capacity offered in BTU/hr against a kW requirement) so
unit normalisation is exercised rather than assumed.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).parents[1]
OUT = ROOT / "data" / "synthetic_epc_extended"
PROJECT_ID = "atlas-demo-dc-02"
CLASSIFICATION = "SYNTHETIC EPC DEMO DATA"
BANNER = "**SYNTHETIC EPC DEMO DATA — NOT AN OFFICIAL STANDARD**"
SUB_BANNER = "**SYNTHETIC EPC DEMO DATA — NOT FOR CONSTRUCTION**"

BTU_PER_HOUR_TO_KW = 0.000293071


@dataclass
class Deviation:
    """
    One planted, scoreable mismatch between a specification and a submittal.

    `narrative` is the answer key and belongs in ground_truth.json only.
    `vendor_note` is what the submittal itself says. They are deliberately kept
    apart: a submittal that states the requirement it misses, or pre-converts a
    value into the specification's units, hands the comparison to retrieval as a
    quotable sentence. The engine must do the normalisation and the comparison,
    so the document states only what the vendor offers.
    """

    parameter: str
    clause: str
    required: str
    offered: str
    severity: str
    narrative: str
    vendor_note: str = ""

    def note(self) -> str:
        return self.vendor_note or self.narrative


@dataclass
class Equipment:
    tag: str
    category: str
    slug: str            # file-name stem, e.g. "Generator"
    section: str         # CSI-style section heading
    title: str
    scope: str
    electrical: list[tuple[str, str]]      # (clause, text) for page 2 / 2.2
    safety: list[tuple[str, str]]          # (clause, text) for page 2 / 2.3
    acceptance: list[tuple[str, str]]      # (clause, text) for page 3 / 2.4
    compliant_vendor: tuple[str, str, str]   # (vendor_id, name, model)
    deviating_vendor: tuple[str, str, str]
    compliant_values: list[tuple[str, str]]
    deviating_values: list[tuple[str, str]]
    deviations: list[Deviation]
    commissioning: list[tuple[str, str, str]]  # (instruction, criterion, prerequisite)
    location: str
    lead_time_days: int
    delay_days: int = 0
    notes: str = ""
    rfis: list[dict] = field(default_factory=list)


EQUIPMENT: list[Equipment] = [
    Equipment(
        tag="GEN-A",
        category="Generator",
        slug="Generator",
        section="26 32 13 — Diesel Standby Generator",
        title="Diesel Standby Generator",
        scope=(
            "Furnish one packaged diesel standby generating set designated GEN-A serving the "
            "Atlas Demo Data Hall standby bus. Ratings below are fictional and apply only to "
            "this synthetic project."
        ),
        electrical=[
            ("2.2.1", "Standby rating: not less than 2,500 kW at 0.8 power factor, 480Y/277 V, three-phase, 60 Hz."),
            ("2.2.2", "On-site fuel storage: not less than 24 hours of continuous operation at 100 percent rated load."),
            ("2.2.3", "Start and load acceptance: reach rated voltage and frequency and accept full load within 10 seconds of a start signal."),
            ("2.2.4", "Governor and voltage regulation: isochronous frequency control with steady-state voltage regulation within plus or minus 1 percent."),
        ],
        safety=[
            ("2.3.1", "Sound level: not greater than 75 dBA at 7 metres from the enclosure at full load."),
            ("2.3.2", "Enclosure: weather-protective walk-in enclosure with integral sub-base fuel tank and spill containment."),
            ("2.3.3", "Provide a factory load-bank test report for the supplied set."),
        ],
        acceptance=[
            ("2.4.1", "Witness factory testing of load acceptance, governor response, and alarm annunciation."),
            ("2.4.2", "Before handover, perform a four-hour synthetic load-bank run and record fuel consumption, coolant temperature, and exhaust back pressure."),
        ],
        compliant_vendor=("V-TG", "TitanGen Power Systems", "TG-STB-2500"),
        deviating_vendor=("V-NS", "NorthStar Genset Works", "NS-2250D"),
        compliant_values=[
            ("Standby rating", "2,500 kW at 0.8 PF, 480Y/277 V"),
            ("Fuel autonomy", "24 hours at 100 percent load"),
            ("Load acceptance", "9.5 seconds to full load"),
            ("Sound level", "73 dBA at 7 m"),
            ("Enclosure", "Weather-protective walk-in with sub-base tank"),
        ],
        deviating_values=[
            ("Standby rating", "2,250 kW at 0.8 PF, 480Y/277 V"),
            ("Fuel autonomy", "16 hours at 100 percent load"),
            ("Load acceptance", "9.8 seconds to full load"),
            ("Sound level", "74 dBA at 7 m"),
            ("Enclosure", "Weather-protective walk-in with sub-base tank"),
        ],
        deviations=[
            Deviation(
                "standby_rating", "2.2.1", "not less than 2,500 kW", "2,250 kW", "high",
                "Offered standby rating is 2,250 kW rather than the required minimum 2,500 kW.",
                vendor_note="The NS-2250D is offered at a 2,250 kW standby rating.",
            ),
            Deviation(
                "fuel_autonomy", "2.2.2", "not less than 24 hours", "16 hours", "high",
                "Offered on-site fuel autonomy is 16 hours rather than the required minimum 24 hours at full load.",
                vendor_note="Sub-base tank capacity is sized for 16 hours at 100 percent rated load.",
            ),
        ],
        commissioning=[
            ("Verify fuel system integrity and prime the day tank.", "No visible leakage after 30 minutes at operating pressure.", "Fuel delivery complete"),
            ("Perform a black-start and record time to accept full load.", "Full load accepted within 10 seconds.", "Load bank connected"),
            ("Run a four-hour load-bank test at 100 percent rated load.", "Coolant temperature stable and within vendor limits for four hours.", "Black-start passed"),
            ("Measure sound level at 7 metres on four sides at full load.", "All four readings not greater than 75 dBA.", "Load-bank test complete"),
            ("Verify alarm annunciation at the EPMS for low fuel and high coolant temperature.", "Both alarms received and logged at the EPMS.", "BMS-A integration complete"),
        ],
        location="Generator Yard GY-01",
        lead_time_days=210,
        notes="Long-lead package; delivery drives standby energization.",
        rfis=[
            {
                "id": "RFI-101",
                "slug": "generator_exhaust_routing",
                "subject": "GEN-A exhaust routing above the generator yard canopy",
                "question": "Confirm whether the GEN-A exhaust stack terminates above the yard canopy or through the side wall, and confirm the required clearance to the adjacent air intake.",
                "answer": "Route the exhaust vertically to terminate 2.0 m above the canopy. Maintain 6.0 m horizontal separation from the nearest outside-air intake in this synthetic layout.",
                "equipment": "GEN-A",
                "clause": "2.3.2",
                "duplicate_of": None,
            },
            {
                "id": "RFI-102",
                "slug": "generator_fuel_autonomy_basis",
                "subject": "GEN-A fuel autonomy basis of measurement",
                "question": "Confirm whether the 24-hour fuel autonomy requirement is measured at 100 percent rated load or at the expected operating load.",
                "answer": "The 24-hour autonomy requirement is measured at 100 percent rated load, consistent with synthetic clause 2.2.2.",
                "equipment": "GEN-A",
                "clause": "2.2.2",
                "duplicate_of": None,
            },
        ],
    ),
    Equipment(
        tag="CH-A",
        category="Chiller",
        slug="Chiller",
        section="23 64 23 — Air-Cooled Chiller",
        title="Air-Cooled Chiller",
        scope=(
            "Furnish one air-cooled screw chiller designated CH-A serving the Atlas Demo Data "
            "Hall chilled-water loop. Capacities below are fictional and apply only to this "
            "synthetic project."
        ),
        electrical=[
            ("2.2.1", "Net cooling capacity: not less than 1,400 kW at 35 degrees Celsius ambient with 12/6 degrees Celsius chilled-water temperatures."),
            ("2.2.2", "Part-load efficiency: integrated part-load value not less than 4.2 COP."),
            ("2.2.3", "Refrigerant: R-513A. Alternative refrigerants require written approval for this synthetic project."),
            ("2.2.4", "Electrical supply: 480 V, three-phase, 60 Hz, with integral disconnect and phase-loss protection."),
        ],
        safety=[
            ("2.3.1", "Provide two independent refrigeration circuits so that a single circuit fault does not remove full capacity."),
            ("2.3.2", "Provide vibration isolation and a factory-mounted control panel with BACnet/IP interface."),
            ("2.3.3", "Provide a factory performance test certificate at the specified duty."),
        ],
        acceptance=[
            ("2.4.1", "Witness factory performance testing at the specified duty point."),
            ("2.4.2", "Before handover, verify capacity by heat balance across the evaporator and record approach temperatures."),
        ],
        compliant_vendor=("V-CL", "CryoLine Thermal", "CL-ACS-1400"),
        deviating_vendor=("V-FA", "FrostArc Cooling", "FA-SCR-4000"),
        compliant_values=[
            ("Net cooling capacity", "1,420 kW at 35 degrees Celsius ambient"),
            ("Part-load efficiency", "IPLV 4.35 COP"),
            ("Refrigerant", "R-513A"),
            ("Refrigeration circuits", "Two independent circuits"),
            ("Controls interface", "BACnet/IP"),
        ],
        deviating_values=[
            ("Net cooling capacity", "4,000,000 BTU/hr at 35 degrees Celsius ambient"),
            ("Part-load efficiency", "IPLV 4.25 COP"),
            ("Refrigerant", "R-410A"),
            ("Refrigeration circuits", "Two independent circuits"),
            ("Controls interface", "BACnet/IP"),
        ],
        deviations=[
            Deviation(
                "net_cooling_capacity", "2.2.1", "not less than 1,400 kW",
                "4,000,000 BTU/hr (approximately 1,172 kW)", "high",
                "Offered capacity is stated as 4,000,000 BTU/hr, approximately 1,172 kW, "
                "against a required minimum of 1,400 kW. The offered figure requires unit "
                "conversion before the shortfall is visible.",
                vendor_note=(
                    "Rated net cooling capacity is 4,000,000 BTU/hr at 35 degrees Celsius "
                    "ambient with 12/6 degrees Celsius chilled-water temperatures."
                ),
            ),
            Deviation(
                "refrigerant", "2.2.3", "R-513A", "R-410A", "medium",
                "Offered refrigerant is R-410A rather than the specified R-513A, and no written approval is recorded.",
                vendor_note="The FA-SCR-4000 is charged with R-410A.",
            ),
        ],
        commissioning=[
            ("Flush and fill the chilled-water loop and record water quality.", "Water quality within vendor limits before start-up.", "Pipework pressure test complete"),
            ("Start each refrigeration circuit independently and record suction and discharge pressures.", "Both circuits start and hold pressures within vendor limits.", "Loop fill complete"),
            ("Verify capacity by heat balance across the evaporator at design flow.", "Measured capacity not less than 1,400 kW at design conditions.", "Circuit start-up complete"),
            ("Fail one refrigeration circuit and record retained capacity.", "Remaining circuit sustains operation without a plant trip.", "Capacity test complete"),
            ("Verify BACnet/IP point mapping at the BMS.", "All mapped points readable at the BMS with correct units.", "BMS-A integration complete"),
        ],
        location="Chiller Yard CY-01",
        lead_time_days=168,
        delay_days=28,
        notes="Planted 28-day forecast delay; drives mechanical energization risk.",
        rfis=[
            {
                "id": "RFI-103",
                "slug": "chiller_capacity_units",
                "subject": "CH-A capacity units for comparison",
                "question": "The chiller submittal states capacity in BTU/hr while the specification states kW. Confirm which basis governs the compliance comparison.",
                "answer": "The kW figure at 35 degrees Celsius ambient governs. Convert offered BTU/hr values at 0.000293071 kW per BTU/hr before comparison in this synthetic project.",
                "equipment": "CH-A",
                "clause": "2.2.1",
                "duplicate_of": None,
            },
            {
                "id": "RFI-104",
                "slug": "chiller_capacity_unit_basis",
                "subject": "Confirm unit basis for CH-A cooling capacity comparison",
                "question": "Please confirm whether offered chiller capacity given in BTU/hr should be converted to kW for the specification comparison, and at what conversion factor.",
                "answer": "Convert BTU/hr to kW at 0.000293071 kW per BTU/hr. The kW value at 35 degrees Celsius ambient is the governing figure for this synthetic project.",
                "equipment": "CH-A",
                "clause": "2.2.1",
                "duplicate_of": "RFI-103",
            },
        ],
    ),
    Equipment(
        tag="PDU-A",
        category="PDU",
        slug="PDU",
        section="26 27 16 — Power Distribution Unit",
        title="Power Distribution Unit",
        scope=(
            "Furnish one floor-mounted power distribution unit designated PDU-A serving Data "
            "Hall DH-01 rack distribution. Ratings below are fictional and apply only to this "
            "synthetic project."
        ),
        electrical=[
            ("2.2.1", "Rating: not less than 300 kVA, 480 V primary, 208Y/120 V secondary, three-phase, 60 Hz."),
            ("2.2.2", "Integral transformer: K-13 rated for harmonic loading, cast-coil or vacuum-pressure impregnated."),
            ("2.2.3", "Provide two 42-pole distribution panelboards with individual branch-circuit monitoring."),
            ("2.2.4", "Provide integral surge protection at the secondary and per-panel earth-leakage monitoring."),
        ],
        safety=[
            ("2.3.1", "Front-access-only maintenance with a minimum 1,000 mm operating aisle."),
            ("2.3.2", "Provide a lockable main input device and a clearly labelled circuit directory."),
            ("2.3.3", "Provide factory routine test certificates for the transformer and panelboards."),
        ],
        acceptance=[
            ("2.4.1", "Witness factory routine tests including turns ratio and insulation resistance."),
            ("2.4.2", "Before energization, verify branch-circuit monitoring accuracy against a reference meter."),
        ],
        compliant_vendor=("V-VH", "VoltHub Distribution", "VH-PDU-300"),
        deviating_vendor=("V-CS", "CircuitSpan Systems", "CS-PDU-225K4"),
        compliant_values=[
            ("Rating", "300 kVA, 480 V primary, 208Y/120 V secondary"),
            ("Transformer K-factor", "K-13"),
            ("Panelboards", "Two 42-pole with branch monitoring"),
            ("Access", "Front access only, 1,000 mm aisle"),
            ("Surge protection", "Integral secondary SPD"),
        ],
        deviating_values=[
            ("Rating", "225 kVA, 480 V primary, 208Y/120 V secondary"),
            ("Transformer K-factor", "K-4"),
            ("Panelboards", "Two 42-pole with branch monitoring"),
            ("Access", "Front access only, 1,000 mm aisle"),
            ("Surge protection", "Integral secondary SPD"),
        ],
        deviations=[
            Deviation(
                "rating_kva", "2.2.1", "not less than 300 kVA", "225 kVA", "high",
                "Offered PDU rating is 225 kVA rather than the required minimum 300 kVA.",
                vendor_note="The CS-PDU-225K4 is offered at 225 kVA.",
            ),
            Deviation(
                "transformer_k_factor", "2.2.2", "K-13", "K-4", "high",
                "Offered integral transformer is K-4 rated rather than the required K-13 for harmonic loading.",
                vendor_note="The integral transformer is K-4 rated.",
            ),
        ],
        commissioning=[
            ("Verify primary and secondary voltages against nameplate before load.", "Measured voltages within plus or minus 2 percent of nameplate.", "Upstream energization complete"),
            ("Perform insulation resistance testing on the integral transformer.", "Insulation resistance not less than the vendor minimum.", "Voltage verification complete"),
            ("Verify branch-circuit monitoring against a reference meter on six circuits.", "All six readings within plus or minus 2 percent of reference.", "Insulation test passed"),
            ("Confirm the circuit directory matches the as-built distribution schedule.", "Directory matches the schedule with no unlabelled breakers.", "Monitoring verified"),
        ],
        location="Data Hall DH-01",
        lead_time_days=120,
        rfis=[
            {
                "id": "RFI-105",
                "slug": "pdu_k_factor_basis",
                "subject": "PDU-A transformer K-factor basis",
                "question": "Confirm whether the K-13 requirement applies to the integral transformer only or also to any upstream dry-type unit.",
                "answer": "K-13 applies to the PDU integral transformer. The upstream unit is governed separately by synthetic clause 2.2.3 of the transformer specification.",
                "equipment": "PDU-A",
                "clause": "2.2.2",
                "duplicate_of": None,
            },
        ],
    ),
    Equipment(
        tag="XFMR-A",
        category="Transformer",
        slug="Transformer",
        section="26 12 19 — Cast-Resin Dry-Type Transformer",
        title="Cast-Resin Dry-Type Transformer",
        scope=(
            "Furnish one cast-resin dry-type transformer designated XFMR-A supplying the Atlas "
            "Demo Data Hall main switchgear. Ratings below are fictional and apply only to this "
            "synthetic project."
        ),
        electrical=[
            ("2.2.1", "Rating: not less than 2,000 kVA, 11 kV delta primary, 480Y/277 V secondary, 60 Hz."),
            ("2.2.2", "Impedance: 5.75 percent at rated capacity, tolerance plus or minus 7.5 percent."),
            ("2.2.3", "Winding temperature rise: not greater than 100 K over a 40 degrees Celsius ambient, insulation class F."),
            ("2.2.4", "No-load losses: not greater than 3.2 kW at rated voltage."),
        ],
        safety=[
            ("2.3.1", "Provide winding temperature monitoring with two-stage alarm and trip contacts."),
            ("2.3.2", "Provide an IP31 enclosure with lockable access panels and cable-box earthing."),
            ("2.3.3", "Provide factory routine and temperature-rise type test certificates."),
        ],
        acceptance=[
            ("2.4.1", "Witness factory routine tests including turns ratio, winding resistance, and applied voltage."),
            ("2.4.2", "Before energization, record insulation resistance, polarity, and temperature-monitor set points."),
        ],
        compliant_vendor=("V-MC", "MagnaCore Transformers", "MC-CR-2000"),
        deviating_vendor=("V-FL", "FerroLink Magnetics", "FL-DT-1600"),
        compliant_values=[
            ("Rating", "2,000 kVA, 11 kV / 480Y/277 V"),
            ("Impedance", "5.75 percent at rated capacity"),
            ("Winding temperature rise", "100 K, class F"),
            ("No-load losses", "3.1 kW"),
            ("Enclosure", "IP31 with lockable panels"),
        ],
        deviating_values=[
            ("Rating", "1,600 kVA, 11 kV / 480Y/277 V"),
            ("Impedance", "5.9 percent at rated capacity"),
            ("Winding temperature rise", "115 K, class F"),
            ("No-load losses", "3.0 kW"),
            ("Enclosure", "IP31 with lockable panels"),
        ],
        deviations=[
            Deviation(
                "rating_kva", "2.2.1", "not less than 2,000 kVA", "1,600 kVA", "high",
                "Offered transformer rating is 1,600 kVA rather than the required minimum 2,000 kVA.",
                vendor_note="The FL-DT-1600 is offered at 1,600 kVA.",
            ),
            Deviation(
                "winding_temperature_rise", "2.2.3", "not greater than 100 K", "115 K", "high",
                "Offered winding temperature rise is 115 K against a specified maximum of 100 K.",
                vendor_note="Winding temperature rise is 115 K over a 40 degrees Celsius ambient, class F.",
            ),
        ],
        commissioning=[
            ("Record insulation resistance on primary and secondary windings.", "Insulation resistance not less than the vendor minimum at 20 degrees Celsius.", "Delivery and placement complete"),
            ("Verify turns ratio on all tap positions.", "Turns ratio within plus or minus 0.5 percent of nameplate on every tap.", "Insulation test complete"),
            ("Verify winding temperature monitor alarm and trip set points.", "Alarm and trip operate at the scheduled set points.", "Ratio test complete"),
            ("Energize and record no-load current and audible noise.", "No-load current within vendor limits and no abnormal noise.", "Protection settings applied"),
        ],
        location="Electrical Room ER-02",
        lead_time_days=196,
        notes="Upstream of SWGR-A equivalent; feeds the main distribution bus.",
        rfis=[
            {
                "id": "RFI-106",
                "slug": "transformer_temperature_rise",
                "subject": "XFMR-A winding temperature rise ambient basis",
                "question": "Confirm the ambient temperature basis for the 100 K winding temperature rise limit.",
                "answer": "The 100 K limit is referenced to a 40 degrees Celsius ambient, consistent with synthetic clause 2.2.3.",
                "equipment": "XFMR-A",
                "clause": "2.2.3",
                "duplicate_of": None,
            },
        ],
    ),
    Equipment(
        tag="FS-A",
        category="FireSuppression",
        slug="FireSuppression",
        section="21 22 00 — Clean-Agent Fire Suppression",
        title="Clean-Agent Fire Suppression System",
        scope=(
            "Furnish one clean-agent fire suppression system designated FS-A protecting Data "
            "Hall DH-01. Design values below are fictional and apply only to this synthetic "
            "project; they are not an assertion of any external code requirement."
        ),
        electrical=[
            ("2.2.1", "Design concentration: not less than 7.0 percent by volume for the protected hazard volume."),
            ("2.2.2", "Discharge time: not greater than 10 seconds to achieve design concentration."),
            ("2.2.3", "Hold time: maintain design concentration for not less than 10 minutes."),
            ("2.2.4", "Provide agent quantity calculations for the stated hazard volume and design temperature."),
        ],
        safety=[
            ("2.3.1", "Provide dual-interlock detection so that a single detector in alarm does not release agent."),
            ("2.3.2", "Provide abort and manual release stations at each egress door with local audible and visual alarm."),
            ("2.3.3", "Provide room integrity fan test results before handover."),
        ],
        acceptance=[
            ("2.4.1", "Witness detection and release logic testing without agent discharge."),
            ("2.4.2", "Perform a room integrity fan test and record the predicted hold time."),
        ],
        compliant_vendor=("V-SG", "SafeGuard Suppression", "SG-CA-700"),
        deviating_vendor=("V-PS", "PyroShield Fire Systems", "PS-CA-620"),
        compliant_values=[
            ("Design concentration", "7.2 percent by volume"),
            ("Discharge time", "9 seconds"),
            ("Hold time", "10 minutes"),
            ("Detection", "Dual-interlock, cross-zoned"),
            ("Abort stations", "At each egress door"),
        ],
        deviating_values=[
            ("Design concentration", "6.2 percent by volume"),
            ("Discharge time", "14 seconds"),
            ("Hold time", "10 minutes"),
            ("Detection", "Dual-interlock, cross-zoned"),
            ("Abort stations", "At each egress door"),
        ],
        deviations=[
            Deviation(
                "design_concentration", "2.2.1", "not less than 7.0 percent", "6.2 percent", "high",
                "Offered design concentration is 6.2 percent by volume against a required minimum of 7.0 percent.",
                vendor_note="Agent quantity is calculated for a 6.2 percent design concentration.",
            ),
            Deviation(
                "discharge_time", "2.2.2", "not greater than 10 seconds", "14 seconds", "high",
                "Offered discharge time is 14 seconds against a specified maximum of 10 seconds.",
                vendor_note="Nozzle sizing gives a 14 second discharge to design concentration.",
            ),
        ],
        commissioning=[
            ("Verify detector addressing and zone mapping at the panel.", "All detectors report the correct zone at the panel.", "Detection install complete"),
            ("Test dual-interlock release logic without agent discharge.", "Release occurs only with both zones in alarm.", "Zone mapping verified"),
            ("Test abort and manual release stations at each egress door.", "Every station operates and annunciates locally.", "Release logic verified"),
            ("Perform a room integrity fan test.", "Predicted hold time not less than 10 minutes.", "Room sealing complete"),
        ],
        location="Data Hall DH-01",
        lead_time_days=98,
        rfis=[
            {
                "id": "RFI-107",
                "slug": "fire_suppression_hold_time",
                "subject": "FS-A hold time verification method",
                "question": "Confirm whether the 10-minute hold time is verified by room integrity fan test or by physical discharge for this synthetic project.",
                "answer": "Hold time is verified by room integrity fan test with a predicted hold time. No physical discharge is required in this synthetic project.",
                "equipment": "FS-A",
                "clause": "2.2.3",
                "duplicate_of": None,
            },
        ],
    ),
    Equipment(
        tag="BMS-A",
        category="BMS",
        slug="BMS",
        section="25 55 00 — Building Management and Power Monitoring",
        title="Building Management and Electrical Power Monitoring System",
        scope=(
            "Furnish one integrated building management and electrical power monitoring system "
            "designated BMS-A for the Atlas Demo Data Hall. Capacities below are fictional and "
            "apply only to this synthetic project."
        ),
        electrical=[
            ("2.2.1", "Protocol support: Modbus TCP and BACnet/IP concurrently on the same supervisory platform."),
            ("2.2.2", "Point capacity: not less than 5,000 monitored points with headroom for 20 percent expansion."),
            ("2.2.3", "Alarm latency: not greater than 2 seconds from field event to operator workstation annunciation."),
            ("2.2.4", "Trend storage: not less than 12 months of point history at one-minute resolution."),
        ],
        safety=[
            ("2.3.1", "Provide redundant supervisory servers in an N+1 arrangement with automatic failover."),
            ("2.3.2", "Provide role-based operator access with an immutable audit log of set-point changes."),
            ("2.3.3", "Provide a point-to-point verification record for every integrated device."),
        ],
        acceptance=[
            ("2.4.1", "Witness failover of the supervisory server pair without loss of alarm annunciation."),
            ("2.4.2", "Before handover, verify point-to-point mapping for every integrated equipment item."),
        ],
        compliant_vendor=("V-NC", "NexusControls Integration", "NC-SUP-6000"),
        deviating_vendor=("V-OL", "OmniLogic Automation", "OL-BAC-3500"),
        compliant_values=[
            ("Protocols", "Modbus TCP and BACnet/IP"),
            ("Point capacity", "6,000 points"),
            ("Alarm latency", "1.5 seconds"),
            ("Trend storage", "12 months at one-minute resolution"),
            ("Server redundancy", "N+1 with automatic failover"),
        ],
        deviating_values=[
            ("Protocols", "BACnet/IP only"),
            ("Point capacity", "3,500 points"),
            ("Alarm latency", "1.8 seconds"),
            ("Trend storage", "12 months at one-minute resolution"),
            ("Server redundancy", "N+1 with automatic failover"),
        ],
        deviations=[
            Deviation(
                "protocol_support", "2.2.1", "Modbus TCP and BACnet/IP", "BACnet/IP only", "high",
                "Offered platform supports BACnet/IP only; the required concurrent Modbus TCP support is absent.",
                vendor_note="The OL-BAC-3500 supervisory platform speaks BACnet/IP. Modbus TCP devices are reached through a separate protocol gateway.",
            ),
            Deviation(
                "point_capacity", "2.2.2", "not less than 5,000 points", "3,500 points", "high",
                "Offered point capacity is 3,500 rather than the required minimum 5,000 monitored points.",
                vendor_note="Licensed point capacity is 3,500 monitored points.",
            ),
        ],
        commissioning=[
            ("Verify point-to-point mapping for GEN-A, CH-A, PDU-A, XFMR-A and FS-A.", "Every mapped point readable with correct units and scaling.", "Field device install complete"),
            ("Measure alarm latency from field event to workstation for ten alarms.", "All ten latencies not greater than 2 seconds.", "Point mapping verified"),
            ("Fail the primary supervisory server and confirm automatic failover.", "Failover completes with no loss of alarm annunciation.", "Latency test complete"),
            ("Verify the audit log records a set-point change with operator identity.", "Audit entry present with operator identity and timestamp.", "Failover verified"),
        ],
        location="Control Room CR-01",
        lead_time_days=84,
        rfis=[
            {
                "id": "RFI-108",
                "slug": "bms_protocol_concurrency",
                "subject": "BMS-A concurrent protocol requirement",
                "question": "Confirm whether Modbus TCP and BACnet/IP must be supported concurrently on one platform or may be split across gateways.",
                "answer": "Both protocols must be supported concurrently on the same supervisory platform. A protocol gateway is not an accepted substitute in this synthetic project.",
                "equipment": "BMS-A",
                "clause": "2.2.1",
                "duplicate_of": None,
            },
        ],
    ),
]


# --------------------------------------------------------------------------- #
# renderers
# --------------------------------------------------------------------------- #

def specification(eq: Equipment) -> str:
    lines = [
        f"# Synthetic Specification — {eq.title}",
        "",
        BANNER + "  ",
        f"**Project ID:** `{PROJECT_ID}`  ",
        f"**Document ID:** `SPEC-{eq.tag.replace('-', '')}-001`  ",
        f"**Discipline:** {'Electrical' if eq.category in {'Generator', 'PDU', 'Transformer'} else 'Mechanical' if eq.category == 'Chiller' else 'Life Safety' if eq.category == 'FireSuppression' else 'Controls'}"
        f" | **Revision:** 0 | **Status:** Issued for Bid",
        "",
        "## Page 1",
        "",
        f"### {eq.section}",
        "",
        f"1.1 {eq.scope}",
        "",
        "1.2 Submit certified drawings, ratings, test certificates, and a clause-by-clause "
        "compliance matrix for every requirement below.",
        "",
        "1.3 Identify every deviation explicitly. An unstated deviation is treated as a "
        "claim of full compliance in this synthetic project.",
        "",
        "## Page 2",
        "",
        "### 2.2 Performance requirements",
        "",
    ]
    for clause, text in eq.electrical:
        lines.append(f"**{clause}** {text}")
        lines.append("")
    lines += ["### 2.3 Safety and installation requirements", ""]
    for clause, text in eq.safety:
        lines.append(f"**{clause}** {text}")
        lines.append("")
    lines += ["## Page 3", "", "### 2.4 Factory and site acceptance", ""]
    for clause, text in eq.acceptance:
        lines.append(f"**{clause}** {text}")
        lines.append("")
    lines += [
        "### 2.5 Data classification",
        "",
        "2.5.1 Every value in this document is fictional. It does not reproduce or claim any "
        "requirement of TIA-942, BICSI, Uptime Institute, UL, AHRI, NFPA, or any other "
        "standards body.",
        "",
    ]
    return "\n".join(lines)


def submittal(eq: Equipment, *, deviating: bool) -> str:
    vendor_id, vendor_name, model = eq.deviating_vendor if deviating else eq.compliant_vendor
    number = "002" if deviating else "001"
    values = eq.deviating_values if deviating else eq.compliant_values
    kind = "Alternate" if deviating else "Primary"

    lines = [
        f"# Synthetic Vendor Submittal — {eq.tag} {kind}",
        "",
        SUB_BANNER + "  ",
        f"**Project ID:** `{PROJECT_ID}` | **Document ID:** `SUB-{eq.tag.replace('-', '')}-{number}`  ",
        f"**Vendor:** {vendor_name} (fictional) | **Model:** {model}",
        "",
        "## Page 1",
        "",
        f"{vendor_name} proposes the {model} for {eq.tag}. "
        + (
            f"This fictional submittal intentionally contains {len(eq.deviations)} comparison cases."
            if deviating
            else "This fictional submittal is a compliant control and contains no planted deviations."
        ),
        "",
        "| Attribute | Offered value |",
        "| --- | --- |",
    ]
    for attribute, value in values:
        lines.append(f"| {attribute} | {value} |")
    lines.append("")

    if deviating:
        lines += [
            "## Page 2",
            "",
            "### Vendor deviation note",
            "",
        ]
        for dev in eq.deviations:
            lines.append(f"- {dev.note()}")
        lines += [
            "",
            "| Synthetic spec clause | Vendor response |",
            "| --- | --- |",
        ]
        for dev in eq.deviations:
            offered = dev.offered.split(" (approximately")[0]
            lines.append(f"| {dev.clause} {dev.parameter.replace('_', ' ')} | {offered} offered |")
        lines += [
            "",
            "**Intentional demo deviations:** "
            + ", ".join(dev.parameter.replace("_", " ") for dev in eq.deviations)
            + ".",
            "",
        ]
    else:
        lines += [
            "## Page 2",
            "",
            "### Compliance statement",
            "",
            "The offered equipment meets every clause of the synthetic specification. "
            "No deviations are claimed.",
            "",
            "| Synthetic spec clause | Vendor response |",
            "| --- | --- |",
        ]
        for clause, _ in eq.electrical:
            lines.append(f"| {clause} | Complies as offered |")
        lines.append("")
    return "\n".join(lines)


def commissioning(eq: Equipment) -> str:
    lines = [
        f"# Synthetic Commissioning Procedure — {eq.tag}",
        "",
        BANNER + "  ",
        f"**Project ID:** `{PROJECT_ID}`  ",
        f"**Document ID:** `CX-{eq.tag.replace('-', '')}-001`  ",
        f"**Equipment tag:** {eq.tag} | **Location:** {eq.location}",
        "",
        "## Page 1",
        "",
        "These ordered steps are fictional and exist to exercise deterministic pass and fail "
        "evaluation. They are not an external commissioning standard.",
        "",
    ]
    for index, (instruction, criterion, prerequisite) in enumerate(eq.commissioning, start=1):
        lines += [
            f"### Step {index}",
            "",
            f"**Prerequisite:** {prerequisite}",
            "",
            f"**Instruction:** {instruction}",
            "",
            f"**Acceptance criterion:** {criterion}",
            "",
        ]
    return "\n".join(lines)


def rfi(entry: dict) -> str:
    return "\n".join(
        [
            f"# Synthetic RFI {entry['id']} — {entry['subject']}",
            "",
            BANNER + "  ",
            f"**Project ID:** `{PROJECT_ID}`  ",
            f"**Document ID:** `{entry['id']}`  ",
            f"**Equipment tag:** {entry['equipment']} | **Referenced clause:** {entry['clause']}",
            "",
            "## Page 1",
            "",
            "### Question",
            "",
            entry["question"],
            "",
            "### Response",
            "",
            entry["answer"],
            "",
            "### Status",
            "",
            "Closed. This fictional RFI exists to exercise retrieval and near-duplicate matching.",
            "",
        ]
    )


def schedule_rows() -> list[list[str]]:
    header = [
        "project_id", "data_classification", "task_id", "task_name", "depends_on", "category",
        "is_delivery_milestone", "baseline_start", "baseline_finish", "forecast_start",
        "forecast_finish", "status", "risk_flag", "delay_days", "notes",
    ]
    rows = [header]

    def row(task_id, name, depends, category, milestone, bs, bf, fs, ff, status, flag, delay, notes):
        rows.append([
            PROJECT_ID, CLASSIFICATION, task_id, name, depends, category,
            "true" if milestone else "false", bs, bf, fs, ff, status, flag, str(delay), notes,
        ])

    row("T-200", "Detailed design release for extended scope", "", "Design", False,
        "2026-01-12", "2026-02-06", "2026-01-12", "2026-02-06", "complete", "on_track", 0,
        "Design release complete")
    row("T-210", "Release chiller purchase order", "T-200", "Procurement", False,
        "2026-02-09", "2026-02-13", "2026-02-09", "2026-02-13", "complete", "on_track", 0,
        "Purchase order released")
    row("T-220", "Chiller fabrication", "T-210", "Procurement", False,
        "2026-02-16", "2026-06-05", "2026-02-16", "2026-07-03", "in_progress", "at_risk", 28,
        "Synthetic compressor casting shortage")
    row("T-230", "Chiller factory performance test", "T-220", "Procurement", False,
        "2026-06-08", "2026-06-10", "2026-07-06", "2026-07-08", "not_started", "at_risk", 28,
        "Forecast from synthetic vendor update")
    row("T-240", "CH-A delivery milestone", "T-230", "Delivery", True,
        "2026-06-17", "2026-06-17", "2026-07-15", "2026-07-15", "not_started", "critical", 28,
        "Delivery date referenced by MM-101 and CO-101")
    row("T-250", "Chiller installation and pipework connection", "T-240", "Installation", False,
        "2026-06-22", "2026-07-17", "2026-07-20", "2026-08-14", "not_started", "at_risk", 28,
        "Follows CH-A delivery")
    row("T-260", "Mechanical plant energization", "T-250", "Commissioning", False,
        "2026-07-20", "2026-07-31", "2026-08-17", "2026-08-28", "not_started", "at_risk", 28,
        "Depends on chiller installation")
    row("T-270", "Integrated systems test", "T-260", "Commissioning", False,
        "2026-08-03", "2026-08-21", "2026-08-31", "2026-09-18", "not_started", "at_risk", 28,
        "Consumes remaining synthetic float")
    row("T-280", "Generator delivery milestone", "T-200", "Delivery", True,
        "2026-08-10", "2026-08-10", "2026-08-10", "2026-08-10", "not_started", "on_track", 0,
        "GEN-A long-lead package on plan")
    row("T-290", "Transformer delivery milestone", "T-200", "Delivery", True,
        "2026-07-27", "2026-07-27", "2026-07-27", "2026-07-27", "not_started", "on_track", 0,
        "XFMR-A on plan")

    return rows


def shipments() -> dict:
    records = []
    for index, eq in enumerate(EQUIPMENT, start=1):
        delayed = eq.delay_days > 0
        records.append(
            {
                "shipment_id": f"SHP-2{index:03d}",
                "reference": f"{eq.tag}-FRT-{index:03d}",
                "equipment_id": eq.tag,
                "status": "in_transit" if delayed else "on_schedule",
                "origin": "Synthetic Port of Origin",
                "destination": "Atlas Demo Data Hall",
                "planned_arrival": "2026-06-17" if delayed else "2026-08-10",
                "forecast_arrival": "2026-07-15" if delayed else "2026-08-10",
                "lead_time_days": eq.lead_time_days,
                "delay_days": eq.delay_days,
                "supplier_tiers": [
                    {"tier": 1, "supplier": eq.compliant_vendor[1], "location": "Synthetic Tier 1 Site"},
                    {"tier": 2, "supplier": f"{eq.category} Castings (fictional)", "location": "Synthetic Tier 2 Site"},
                ],
                "milestones": [
                    {"name": "Fabrication complete", "planned_date": "2026-06-05" if delayed else "2026-07-24",
                     "forecast_date": "2026-07-03" if delayed else "2026-07-24",
                     "status": "at_risk" if delayed else "on_track"},
                    {"name": "Port departure", "planned_date": "2026-06-10" if delayed else "2026-07-29",
                     "forecast_date": "2026-07-08" if delayed else "2026-07-29",
                     "status": "at_risk" if delayed else "on_track"},
                ],
                "schedule_task_id": "T-240" if delayed else "T-280",
                "synthetic_simulation": True,
                "live_tracking": False,
                "live_position": None,
            }
        )
    return {
        "data_classification": CLASSIFICATION,
        "project_id": PROJECT_ID,
        "disclaimer": "Synthetic shipment simulation. No live carrier, AIS, or ERP data is represented.",
        "shipments": records,
    }


def ground_truth() -> dict:
    findings = []
    for eq in EQUIPMENT:
        for order, dev in enumerate(eq.deviations, start=1):
            findings.append(
                {
                    "finding_id": f"CF-{eq.tag.replace('-', '')}-{order:03d}",
                    "submittal": f"submittals/{eq.tag}-002_{eq.deviating_vendor[1].split()[0]}_{eq.tag}.md",
                    "submittal_page": 1,
                    "equipment_tag": eq.tag,
                    "parameter": dev.parameter,
                    "finding": dev.narrative,
                    "severity": dev.severity,
                    "evidence": [
                        {
                            "document": f"submittals/{eq.tag}-002_{eq.deviating_vendor[1].split()[0]}_{eq.tag}.md",
                            "page": 1,
                            "excerpt": dev.offered.split(" (approximately")[0],
                        },
                        {
                            "document": f"specifications/{eq.slug}_Specification.md",
                            "page": 2,
                            "clause": dev.clause,
                            "excerpt": dev.required,
                        },
                    ],
                }
            )

    duplicates = [
        {"rfi_a": entry["duplicate_of"], "rfi_b": entry["id"], "reason": "Same unit-conversion question restated"}
        for eq in EQUIPMENT
        for entry in eq.rfis
        if entry["duplicate_of"]
    ]

    return {
        "data_classification": f"{CLASSIFICATION} — extended corpus, fictional values only",
        "project_id": PROJECT_ID,
        "expected_compliance_findings": findings,
        "expected_clean_submittals": [
            f"submittals/{eq.tag}-001_{eq.compliant_vendor[1].split()[0]}_{eq.tag}.md"
            for eq in EQUIPMENT
        ],
        "expected_duplicate_rfi_matches": duplicates,
        "expected_schedule_risks": [
            {
                "risk_id": "SR-CHA-001",
                "task_id": "T-240",
                "task_name": "CH-A delivery milestone",
                "analysis_date": "2026-05-18",
                "risk_level": "critical",
                "forecast_delay_days": 28,
                "impact_chain": ["T-240", "T-250", "T-260", "T-270"],
                "expected_narrative": (
                    "Chiller delivery is forecast 28 days late and delays installation, "
                    "mechanical plant energization, and the integrated systems test."
                ),
            }
        ],
        "expected_unit_normalisation_cases": [
            {
                "equipment_tag": "CH-A",
                "parameter": "net_cooling_capacity",
                "specification_unit": "kW",
                "submittal_unit": "BTU/hr",
                "submittal_value": 4_000_000,
                "converted_value_kw": round(4_000_000 * BTU_PER_HOUR_TO_KW, 2),
                "required_minimum_kw": 1400,
                "note": "The shortfall is only visible after conversion; this case exists to exercise unit normalisation.",
            }
        ],
    }


def readme(counts: dict[str, int]) -> str:
    total = sum(counts.values())
    lines = [
        "# Extended synthetic EPC corpus",
        "",
        BANNER,
        "",
        f"**Project ID:** `{PROJECT_ID}`",
        "",
        "A second, independent synthetic corpus covering six equipment items that the original",
        "`data/synthetic_epc/` corpus does not: a standby generator, an air-cooled chiller, a",
        "power distribution unit, a cast-resin transformer, a clean-agent fire suppression",
        "system, and a building management system.",
        "",
        "## Load this into its own project",
        "",
        "`GET /projects/{id}/compliance/evaluation` scores every finding in a project against",
        "`data/synthetic_epc/ground_truth.json`, which describes the original six planted",
        "deviations only. Uploading this corpus into the seeded demo project would register its",
        "findings as false positives and break the reported 6/0/0/6 result.",
        "",
        "Create a separate project and load it there. Project scoping is enforced by the API,",
        "so the two corpora stay independent.",
        "",
        "## Contents",
        "",
        "| Category | Files |",
        "| --- | --- |",
    ]
    for name, count in counts.items():
        lines.append(f"| {name} | {count} |")
    lines += [
        f"| **Total** | **{total}** |",
        "",
        "## Planted cases",
        "",
        "Every equipment item has one compliant control submittal and one deviating submittal",
        "carrying exactly two planted deviations, giving twelve expected findings and six",
        "expected clean submittals. `ground_truth.json` names each one.",
        "",
        "| Equipment | Clause | Required | Offered |",
        "| --- | --- | --- | --- |",
    ]
    for eq in EQUIPMENT:
        for dev in eq.deviations:
            lines.append(f"| {eq.tag} | {dev.clause} | {dev.required} | {dev.offered} |")
    lines += [
        "",
        "### Deliberate unit-conversion case",
        "",
        "CH-A capacity is offered as **4,000,000 BTU/hr** against a **1,400 kW** requirement.",
        f"That converts to approximately **{round(4_000_000 * BTU_PER_HOUR_TO_KW, 0):.0f} kW**, so the shortfall is invisible until the",
        "units are normalised. A comparison that comments only on the raw numbers has not",
        "actually done the work.",
        "",
        "### Deliberate near-duplicate RFI pair",
        "",
        "`RFI-103` and `RFI-104` ask the same unit-basis question in different words, for",
        "duplicate detection.",
        "",
        "### Planted schedule delay",
        "",
        "`T-240` (CH-A delivery) is forecast 28 days late and propagates through installation,",
        "mechanical energization, and the integrated systems test.",
        "",
        "## Provenance",
        "",
        "Every project, vendor, equipment, model, value, date, and clause here is fictional.",
        "Nothing reproduces or claims any requirement of TIA-942, BICSI, Uptime Institute, UL,",
        "AHRI, NFPA, or any other standards body. No customer, employer, supplier, shipment, or",
        "site data is represented.",
        "",
        "Regenerate with:",
        "",
        "```bash",
        "python3 scripts/generate_extended_corpus.py",
        "```",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #

def build() -> tuple[dict[str, int], list[Path]]:
    written: list[Path] = []

    def write(relative: str, content: str) -> None:
        path = OUT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        written.append(path)

    counts = {
        "Specifications": 0,
        "Submittals (compliant controls)": 0,
        "Submittals (with planted deviations)": 0,
        "Commissioning procedures": 0,
        "RFIs": 0,
        "Meeting minutes": 0,
        "Change orders": 0,
        "Schedule (CSV)": 0,
        "Shipment simulation (JSON)": 0,
        "Metadata (JSON)": 0,
        "Ground truth (JSON)": 0,
        "README": 0,
    }

    for eq in EQUIPMENT:
        write(f"specifications/{eq.slug}_Specification.md", specification(eq))
        counts["Specifications"] += 1

        write(
            f"submittals/{eq.tag}-001_{eq.compliant_vendor[1].split()[0]}_{eq.tag}.md",
            submittal(eq, deviating=False),
        )
        counts["Submittals (compliant controls)"] += 1

        write(
            f"submittals/{eq.tag}-002_{eq.deviating_vendor[1].split()[0]}_{eq.tag}.md",
            submittal(eq, deviating=True),
        )
        counts["Submittals (with planted deviations)"] += 1

        write(f"commissioning/{eq.slug}_Procedure_Template.md", commissioning(eq))
        counts["Commissioning procedures"] += 1

        for entry in eq.rfis:
            write(f"rfis/{entry['id']}_{entry['slug']}.md", rfi(entry))
            counts["RFIs"] += 1

    # Schedule
    rows = schedule_rows()
    write(
        "schedules/atlas_extended_schedule.csv",
        "\n".join(",".join(cell for cell in row) for row in rows) + "\n",
    )
    counts["Schedule (CSV)"] += 1

    # Meeting minutes
    write(
        "meeting_minutes/MM-101_chiller_delivery_review.md",
        "\n".join([
            "# Synthetic Meeting Minutes MM-101 — Chiller delivery risk review",
            "", BANNER + "  ",
            f"**Project ID:** `{PROJECT_ID}`  ",
            "**Document ID:** `MM-101` | **Date:** 2026-05-18",
            "", "## Page 1", "",
            "### Attendees", "",
            "Fictional project manager, mechanical lead, procurement lead, commissioning manager.",
            "", "### Discussion", "",
            "1. FrostArc reported a synthetic compressor casting shortage. CH-A fabrication is "
            "forecast 28 days late, moving the T-240 delivery milestone from 2026-06-17 to "
            "2026-07-15.",
            "",
            "2. The mechanical lead noted the FrostArc submittal states capacity in BTU/hr. "
            "Converted, the offered figure is approximately 1,172 kW against the 1,400 kW "
            "requirement in synthetic clause 2.2.1. See RFI-103.",
            "",
            "3. The offered refrigerant R-410A does not match the specified R-513A and no "
            "written approval is recorded.",
            "",
            "### Actions", "",
            "- Procurement to price expediting and an alternate supplier. See CO-101.",
            "- Commissioning manager to confirm the integrated systems test window can absorb "
            "part of the 28-day forecast slip.",
            "",
        ]),
    )
    counts["Meeting minutes"] += 1

    write(
        "meeting_minutes/MM-102_bms_integration_review.md",
        "\n".join([
            "# Synthetic Meeting Minutes MM-102 — BMS integration scope review",
            "", BANNER + "  ",
            f"**Project ID:** `{PROJECT_ID}`  ",
            "**Document ID:** `MM-102` | **Date:** 2026-05-25",
            "", "## Page 1", "",
            "### Discussion", "",
            "1. OmniLogic offers BACnet/IP only. Synthetic clause 2.2.1 requires concurrent "
            "Modbus TCP and BACnet/IP on one supervisory platform. A protocol gateway was "
            "proposed and is not accepted. See RFI-108.",
            "",
            "2. Offered point capacity is 3,500 against the 5,000 minimum in synthetic clause "
            "2.2.2, leaving no expansion headroom.",
            "",
            "3. Generator and chiller point mapping cannot be signed off until the supervisory "
            "platform is settled, which links this decision to commissioning readiness.",
            "",
            "### Actions", "",
            "- Controls lead to obtain a compliant NexusControls proposal for comparison.",
            "",
        ]),
    )
    counts["Meeting minutes"] += 1

    write(
        "change_orders/CO-101_chiller_recovery.md",
        "\n".join([
            "# Synthetic Change Order CO-101 — Chiller delivery recovery",
            "", BANNER + "  ",
            f"**Project ID:** `{PROJECT_ID}`  ",
            "**Document ID:** `CO-101` | **Status:** Pending human decision",
            "", "## Page 1", "",
            "### Background", "",
            "CH-A delivery is forecast 28 days late per MM-101, consuming synthetic float on "
            "T-250, T-260 and T-270.",
            "", "### Options", "",
            "| Option | Recovery | Added cost (synthetic) | Residual risk |",
            "| --- | --- | --- | --- |",
            "| Do nothing | 0 days | 0 | 28-day exposure to the integrated systems test |",
            "| Expedite freight | 12 days | 180,000 | 16-day exposure remains |",
            "| Resequence installation | 9 days | 45,000 | 19-day exposure, added coordination |",
            "",
            "### Decision", "",
            "No option is approved. This synthetic change order exists so that a reviewer "
            "decision, not an AI suggestion, creates the approved record.",
            "",
        ]),
    )
    counts["Change orders"] += 1

    # Metadata
    write(
        "metadata/equipment.json",
        json.dumps(
            {
                "data_classification": CLASSIFICATION,
                "project_id": PROJECT_ID,
                "equipment": [
                    {
                        "equipment_id": f"EQ-{eq.tag.replace('-', '')}",
                        "tag": eq.tag,
                        "category": eq.category,
                        "specification_id": f"SPEC-{eq.tag.replace('-', '')}-001",
                        "selected_vendor_id": eq.compliant_vendor[0],
                        "selected_model": eq.compliant_vendor[2],
                        "location": eq.location,
                        "lead_time_days": eq.lead_time_days,
                    }
                    for eq in EQUIPMENT
                ],
            },
            indent=2,
        )
        + "\n",
    )
    counts["Metadata (JSON)"] += 1

    write(
        "metadata/vendors.json",
        json.dumps(
            {
                "data_classification": CLASSIFICATION,
                "project_id": PROJECT_ID,
                "vendors": [
                    entry
                    for eq in EQUIPMENT
                    for entry in (
                        {
                            "vendor_id": eq.compliant_vendor[0],
                            "name": eq.compliant_vendor[1],
                            "equipment_category": eq.category,
                            "submittal_id": f"SUB-{eq.tag.replace('-', '')}-001",
                            "status": "compliant_control",
                        },
                        {
                            "vendor_id": eq.deviating_vendor[0],
                            "name": eq.deviating_vendor[1],
                            "equipment_category": eq.category,
                            "submittal_id": f"SUB-{eq.tag.replace('-', '')}-002",
                            "status": "intentional_deviations",
                        },
                    )
                ],
            },
            indent=2,
        )
        + "\n",
    )
    counts["Metadata (JSON)"] += 1

    write("supply_chain/shipments.json", json.dumps(shipments(), indent=2) + "\n")
    counts["Shipment simulation (JSON)"] += 1

    write("ground_truth.json", json.dumps(ground_truth(), indent=2) + "\n")
    counts["Ground truth (JSON)"] += 1

    write("README.md", readme(counts))
    counts["README"] += 1

    return counts, written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report what would be written, write nothing")
    args = parser.parse_args()

    if args.check:
        # Render everything so a template error surfaces, then discard.
        for eq in EQUIPMENT:
            specification(eq); submittal(eq, deviating=True); submittal(eq, deviating=False)
            commissioning(eq)
            for entry in eq.rfis:
                rfi(entry)
        ground_truth(); shipments(); schedule_rows()
        print("all templates render cleanly")
        return 0

    counts, written = build()
    total = sum(counts.values())

    width = max(len(name) for name in counts)
    print(f"Wrote {total} files to {OUT.relative_to(ROOT)}/\n")
    for name, count in counts.items():
        print(f"  {name.ljust(width)}  {count}")
    print(f"  {'TOTAL'.ljust(width)}  {total}")

    gt = ground_truth()
    print(
        f"\nPlanted: {len(gt['expected_compliance_findings'])} expected findings, "
        f"{len(gt['expected_clean_submittals'])} clean controls, "
        f"{len(gt['expected_duplicate_rfi_matches'])} duplicate RFI pair(s), "
        f"{len(gt['expected_schedule_risks'])} schedule risk."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
