# This file is generated from the vendored CCSDS NDM/XML schemas by
# scripts/regen_ccsds_xsd.py (xsdata 26.2). DO NOT EDIT BY HAND — re-run the
# script to regenerate. See schemas/ccsds-ndm/README.md for schema provenance.
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AccUnits(Enum):
    KM_S_2 = "km/s**2"


class AcmAttitudeType(Enum):
    QUATERNION = "QUATERNION"
    QUATERNION_1 = "quaternion"
    EULER_ANGLES = "EULER_ANGLES"
    EULER_ANGLES_1 = "euler_angles"
    DCM = "DCM"
    DCM_1 = "dcm"
    ANGVEL = "ANGVEL"
    ANGVEL_1 = "angvel"
    Q_DOT = "Q_DOT"
    Q_DOT_1 = "q_dot"
    EULER_RATE = "EULER_RATE"
    EULER_RATE_1 = "euler_rate"
    GYRO_BIAS = "GYRO_BIAS"
    GYRO_BIAS_1 = "gyro_bias"


class AcmCovarianceLineType(Enum):
    ANGLE = "ANGLE"
    ANGLE_1 = "angle"
    ANGLE_GYROBIAS = "ANGLE_GYROBIAS"
    ANGLE_GYROBIAS_1 = "angle_gyrobias"
    ANGLE_ANGVEL = "ANGLE_ANGVEL"
    ANGLE_ANGVEL_1 = "angle_angvel"
    QUATERNION = "QUATERNION"
    QUATERNION_1 = "quaternion"
    QUATERNION_GYROBIAS = "QUATERNION_GYROBIAS"
    QUATERNION_GYROBIAS_1 = "quaternion_gyrobias"
    QUATERNION_ANGVEL = "QUATERNION_ANGVEL"
    QUATERNION_ANGVEL_1 = "quaternion_angvel"


class AdMethodType(Enum):
    EKF = "EKF"
    EKF_1 = "ekf"
    TRIAD = "TRIAD"
    TRIAD_1 = "triad"
    QUEST = "QUEST"
    QUEST_1 = "quest"
    BATCH = "BATCH"
    BATCH_1 = "batch"
    Q_METHOD = "Q_METHOD"
    Q_METHOD_1 = "q_method"
    FILTER_SMOOTHER = "FILTER_SMOOTHER"
    FILTER_SMOOTHER_1 = "filter_smoother"
    OTHER = "OTHER"
    OTHER_1 = "other"


@dataclass(kw_only=True)
class AdmHeader:
    class Meta:
        name = "admHeader"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    classification: None | str = field(
        default=None,
        metadata={
            "name": "CLASSIFICATION",
            "type": "Element",
            "namespace": "",
        },
    )
    creation_date: str = field(
        metadata={
            "name": "CREATION_DATE",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    originator: str = field(
        metadata={
            "name": "ORIGINATOR",
            "type": "Element",
            "namespace": "",
        }
    )
    message_id: None | str = field(
        default=None,
        metadata={
            "name": "MESSAGE_ID",
            "type": "Element",
            "namespace": "",
        },
    )


class AgomUnits(Enum):
    M_2_KG = "m**2/kg"


class AngMomentumUnits(Enum):
    N_M_S = "N*m*s"


class AngleRateUnits(Enum):
    DEG_S = "deg/s"


class AngleTypeType(Enum):
    AZEL = "AZEL"
    AZEL_1 = "azel"
    RADEC = "RADEC"
    RADEC_1 = "radec"
    XEYN = "XEYN"
    XEYN_1 = "xeyn"
    XSYE = "XSYE"
    XSYE_1 = "xsye"


class AngleUnits(Enum):
    DEG = "deg"


@dataclass(kw_only=True)
class ApmMetadata:
    class Meta:
        name = "apmMetadata"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    object_name: str = field(
        metadata={
            "name": "OBJECT_NAME",
            "type": "Element",
            "namespace": "",
        }
    )
    object_id: str = field(
        metadata={
            "name": "OBJECT_ID",
            "type": "Element",
            "namespace": "",
        }
    )
    center_name: None | str = field(
        default=None,
        metadata={
            "name": "CENTER_NAME",
            "type": "Element",
            "namespace": "",
        },
    )
    time_system: str = field(
        metadata={
            "name": "TIME_SYSTEM",
            "type": "Element",
            "namespace": "",
        }
    )


class AreaUnits(Enum):
    M_2 = "m**2"


class AttBasisType(Enum):
    PREDICTED = "PREDICTED"
    PREDICTED_1 = "predicted"
    DETERMINED_GND = "DETERMINED_GND"
    DETERMINED_GND_1 = "determined_gnd"
    DETERMINED_OBC = "DETERMINED_OBC"
    DETERMINED_OBC_1 = "determined_obc"
    SIMULATED = "SIMULATED"
    SIMULATED_1 = "simulated"


class AttRateType(Enum):
    ANGVEL = "ANGVEL"
    ANGVEL_1 = "angvel"
    Q_DOT = "Q_DOT"
    Q_DOT_1 = "q_dot"
    EULER_RATE = "EULER_RATE"
    EULER_RATE_1 = "euler_rate"
    GYRO_BIAS = "GYRO_BIAS"
    GYRO_BIAS_1 = "gyro_bias"


class AttitudeTypeType(Enum):
    QUATERNION = "quaternion"
    QUATERNION_1 = "QUATERNION"
    QUATERNION_DERIVATIVE = "quaternion/derivative"
    QUATERNION_DERIVATIVE_1 = "QUATERNION/DERIVATIVE"
    QUATERNION_ANGVEL = "quaternion/angvel"
    QUATERNION_ANGVEL_1 = "QUATERNION/ANGVEL"
    EULER_ANGLE = "euler_angle"
    EULER_ANGLE_1 = "EULER_ANGLE"
    EULER_ANGLE_DERIVATIVE = "euler_angle/derivative"
    EULER_ANGLE_DERIVATIVE_1 = "EULER_ANGLE/DERIVATIVE"
    EULER_ANGLE_ANGVEL = "euler_angle/angvel"
    EULER_ANGLE_ANGVEL_1 = "EULER_ANGLE/ANGVEL"
    SPIN = "spin"
    SPIN_1 = "SPIN"
    SPIN_NUTATION = "spin/nutation"
    SPIN_NUTATION_1 = "SPIN/NUTATION"
    SPIN_NUTATION_MOM = "spin/nutation_mom"
    SPIN_NUTATION_MOM_1 = "SPIN/NUTATION_MOM"


class BStarUnits(Enum):
    VALUE_1_ER = "1/ER"


class BTermUnits(Enum):
    M_2_KG = "m**2/kg"


class BallisticCoeffUnitsType(Enum):
    KG_M_2 = "kg/m**2"


@dataclass(kw_only=True)
class CdmHeader:
    class Meta:
        name = "cdmHeader"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    creation_date: str = field(
        metadata={
            "name": "CREATION_DATE",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    originator: str = field(
        metadata={
            "name": "ORIGINATOR",
            "type": "Element",
            "namespace": "",
        }
    )
    message_for: None | str = field(
        default=None,
        metadata={
            "name": "MESSAGE_FOR",
            "type": "Element",
            "namespace": "",
        },
    )
    message_id: str = field(
        metadata={
            "name": "MESSAGE_ID",
            "type": "Element",
            "namespace": "",
        }
    )


class ControlledType(Enum):
    YES = "YES"
    YES_1 = "yes"
    NO = "NO"
    NO_1 = "no"
    UNKNOWN = "UNKNOWN"
    UNKNOWN_1 = "unknown"


class CovBasisType(Enum):
    PREDICTED = "PREDICTED"
    DETERMINED = "DETERMINED"
    EMPIRICAL = "EMPIRICAL"
    SIMULATED = "SIMULATED"
    OTHER = "OTHER"


class CovOrderType(Enum):
    LTM = "LTM"
    UTM = "UTM"
    FULL = "FULL"
    LTMWCC = "LTMWCC"
    UTMWCC = "UTMWCC"


class CovarianceMethodType(Enum):
    CALCULATED = "CALCULATED"
    CALCULATED_1 = "calculated"
    DEFAULT = "DEFAULT"
    DEFAULT_1 = "default"


class DRevUnits(Enum):
    REV_DAY_2 = "rev/day**2"
    REV_DAY_2_1 = "REV/DAY**2"


class DataQualityType(Enum):
    RAW = "raw"
    RAW_1 = "RAW"
    VALIDATED = "validated"
    VALIDATED_1 = "VALIDATED"
    DEGRADED = "degraded"
    DEGRADED_1 = "DEGRADED"


class DayIntervalUnits(Enum):
    D = "d"


class DdRevUnits(Enum):
    REV_DAY_3 = "rev/day**3"
    REV_DAY_3_1 = "REV/DAY**3"


class DisintegrationType(Enum):
    NONE = "NONE"
    MASS_LOSS = "MASS-LOSS"
    BREAK_UP = "BREAK-UP"
    MASS_LOSS_BREAK_UP = "MASS-LOSS + BREAK-UP"


class DvUnits(Enum):
    M_S = "m/s"


class FrequencyUnits(Enum):
    HZ = "Hz"


class GeomagUnits(Enum):
    N_T = "nT"


class GmUnits(Enum):
    KM_3_S_2 = "km**3/s**2"
    KM_3_S_2_1 = "KM**3/S**2"


class ImpactUncertaintyType(Enum):
    NONE = "NONE"
    ANALYTICAL = "ANALYTICAL"
    STOCHASTIC = "STOCHASTIC"
    EMPIRICAL = "EMPIRICAL"


class IntegrationRefType(Enum):
    START = "START"
    START_1 = "start"
    MIDDLE = "MIDDLE"
    MIDDLE_1 = "middle"
    END = "END"
    END_1 = "end"


class Km2Units(Enum):
    KM_2 = "km**2"


class Km2S2Units(Enum):
    KM_2_S_2 = "km**2/s**2"


class Km2SUnits(Enum):
    KM_2_S = "km**2/s"


class LatLonUnits(Enum):
    DEG = "deg"


class LengthUnits(Enum):
    M = "m"


class M2Units(Enum):
    M_2 = "m**2"


class M2KgUnits(Enum):
    M_2_KG = "m**2/kg"


class M2S2Units(Enum):
    M_2_S_2 = "m**2/s**2"


class M2S3Units(Enum):
    M_2_S_3 = "m**2/s**3"


class M2S4Units(Enum):
    M_2_S_4 = "m**2/s**4"


class M2SUnits(Enum):
    M_2_S = "m**2/s"


class M3KgUnits(Enum):
    M_3_KG = "m**3/kg"


class M3Kgs2Units(Enum):
    M_3_KG_S_2 = "m**3/(kg*s**2)"


class M3KgsUnits(Enum):
    M_3_KG_S = "m**3/(kg*s)"


class M4Kg2Units(Enum):
    M_4_KG_2 = "m**4/kg**2"


class ManBasisType(Enum):
    CANDIDATE = "CANDIDATE"
    PLANNED = "PLANNED"
    ANTICIPATED = "ANTICIPATED"
    TELEMETRY = "TELEMETRY"
    DETERMINED = "DETERMINED"
    SIMULATED = "SIMULATED"
    OTHER = "OTHER"


class ManDctype(Enum):
    CONTINUOUS = "CONTINUOUS"
    TIME = "TIME"
    TIME_AND_ANGLE = "TIME_AND_ANGLE"


class ManeuverableType(Enum):
    YES = "YES"
    YES_1 = "yes"
    NO = "NO"
    NO_1 = "no"
    N_A = "N/A"
    N_A_1 = "n/a"


class MassUnits(Enum):
    KG = "kg"


class ModeType(Enum):
    SEQUENTIAL = "SEQUENTIAL"
    SEQUENTIAL_1 = "sequential"
    SINGLE_DIFF = "SINGLE_DIFF"
    SINGLE_DIFF_1 = "single_diff"


class MomentUnits(Enum):
    KG_M_2 = "kg*m**2"


class Ms2Units(Enum):
    M_S_2 = "m/s**2"


@dataclass(kw_only=True)
class NdmHeader:
    class Meta:
        name = "ndmHeader"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    creation_date: str = field(
        metadata={
            "name": "CREATION_DATE",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    originator: str = field(
        metadata={
            "name": "ORIGINATOR",
            "type": "Element",
            "namespace": "",
        }
    )


class NumPerYearUnits(Enum):
    YR = "#/yr"


class ObjectDescriptionType(Enum):
    PAYLOAD = "PAYLOAD"
    PAYLOAD_1 = "payload"
    ROCKET_BODY = "ROCKET BODY"
    ROCKET_BODY_1 = "rocket body"
    DEBRIS = "DEBRIS"
    DEBRIS_1 = "debris"
    UNKNOWN = "UNKNOWN"
    UNKNOWN_1 = "unknown"
    OTHER = "OTHER"
    OTHER_1 = "other"


class ObjectType(Enum):
    OBJECT1 = "OBJECT1"
    OBJECT1_1 = "object1"
    OBJECT2 = "OBJECT2"
    OBJECT2_1 = "object2"


@dataclass(kw_only=True)
class OdmHeader:
    class Meta:
        name = "odmHeader"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    classification: None | str = field(
        default=None,
        metadata={
            "name": "CLASSIFICATION",
            "type": "Element",
            "namespace": "",
        },
    )
    creation_date: str = field(
        metadata={
            "name": "CREATION_DATE",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    originator: str = field(
        metadata={
            "name": "ORIGINATOR",
            "type": "Element",
            "namespace": "",
        }
    )
    message_id: None | str = field(
        default=None,
        metadata={
            "name": "MESSAGE_ID",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class OemCovarianceMatrixAbstractType:
    class Meta:
        name = "oemCovarianceMatrixAbstractType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    epoch: str = field(
        metadata={
            "name": "EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    cov_ref_frame: None | str = field(
        default=None,
        metadata={
            "name": "COV_REF_FRAME",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class OemMetadata:
    class Meta:
        name = "oemMetadata"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    object_name: str = field(
        metadata={
            "name": "OBJECT_NAME",
            "type": "Element",
            "namespace": "",
        }
    )
    object_id: str = field(
        metadata={
            "name": "OBJECT_ID",
            "type": "Element",
            "namespace": "",
        }
    )
    center_name: str = field(
        metadata={
            "name": "CENTER_NAME",
            "type": "Element",
            "namespace": "",
        }
    )
    ref_frame: str = field(
        metadata={
            "name": "REF_FRAME",
            "type": "Element",
            "namespace": "",
        }
    )
    ref_frame_epoch: None | str = field(
        default=None,
        metadata={
            "name": "REF_FRAME_EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    time_system: str = field(
        metadata={
            "name": "TIME_SYSTEM",
            "type": "Element",
            "namespace": "",
        }
    )
    start_time: str = field(
        metadata={
            "name": "START_TIME",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    useable_start_time: None | str = field(
        default=None,
        metadata={
            "name": "USEABLE_START_TIME",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    useable_stop_time: None | str = field(
        default=None,
        metadata={
            "name": "USEABLE_STOP_TIME",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    stop_time: str = field(
        metadata={
            "name": "STOP_TIME",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    interpolation: None | str = field(
        default=None,
        metadata={
            "name": "INTERPOLATION",
            "type": "Element",
            "namespace": "",
        },
    )
    interpolation_degree: None | int = field(
        default=None,
        metadata={
            "name": "INTERPOLATION_DEGREE",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class OmmMetadata:
    class Meta:
        name = "ommMetadata"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    object_name: str = field(
        metadata={
            "name": "OBJECT_NAME",
            "type": "Element",
            "namespace": "",
        }
    )
    object_id: str = field(
        metadata={
            "name": "OBJECT_ID",
            "type": "Element",
            "namespace": "",
        }
    )
    center_name: str = field(
        metadata={
            "name": "CENTER_NAME",
            "type": "Element",
            "namespace": "",
        }
    )
    ref_frame: str = field(
        metadata={
            "name": "REF_FRAME",
            "type": "Element",
            "namespace": "",
        }
    )
    ref_frame_epoch: None | str = field(
        default=None,
        metadata={
            "name": "REF_FRAME_EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    time_system: str = field(
        metadata={
            "name": "TIME_SYSTEM",
            "type": "Element",
            "namespace": "",
        }
    )
    mean_element_theory: str = field(
        metadata={
            "name": "MEAN_ELEMENT_THEORY",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class OpmCovarianceMatrixAbstractType:
    class Meta:
        name = "opmCovarianceMatrixAbstractType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    cov_ref_frame: None | str = field(
        default=None,
        metadata={
            "name": "COV_REF_FRAME",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class OpmMetadata:
    class Meta:
        name = "opmMetadata"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    object_name: str = field(
        metadata={
            "name": "OBJECT_NAME",
            "type": "Element",
            "namespace": "",
        }
    )
    object_id: str = field(
        metadata={
            "name": "OBJECT_ID",
            "type": "Element",
            "namespace": "",
        }
    )
    center_name: str = field(
        metadata={
            "name": "CENTER_NAME",
            "type": "Element",
            "namespace": "",
        }
    )
    ref_frame: str = field(
        metadata={
            "name": "REF_FRAME",
            "type": "Element",
            "namespace": "",
        }
    )
    ref_frame_epoch: None | str = field(
        default=None,
        metadata={
            "name": "REF_FRAME_EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    time_system: str = field(
        metadata={
            "name": "TIME_SYSTEM",
            "type": "Element",
            "namespace": "",
        }
    )


class PercentageUnits(Enum):
    PERCENT_SIGN = "%"


class PositionCovarianceUnits(Enum):
    KM_2 = "km**2"


class PositionUnits(Enum):
    KM = "km"


class PositionVelocityCovarianceUnits(Enum):
    KM_2_S = "km**2/s"


class QuaternionDotUnits(Enum):
    VALUE_1_S = "1/s"


@dataclass(kw_only=True)
class QuaternionType:
    class Meta:
        name = "quaternionType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    q1: float = field(
        metadata={
            "name": "Q1",
            "type": "Element",
            "namespace": "",
            "min_inclusive": -1.0,
            "max_inclusive": 1.0,
        }
    )
    q2: float = field(
        metadata={
            "name": "Q2",
            "type": "Element",
            "namespace": "",
            "min_inclusive": -1.0,
            "max_inclusive": 1.0,
        }
    )
    q3: float = field(
        metadata={
            "name": "Q3",
            "type": "Element",
            "namespace": "",
            "min_inclusive": -1.0,
            "max_inclusive": 1.0,
        }
    )
    qc: float = field(
        metadata={
            "name": "QC",
            "type": "Element",
            "namespace": "",
            "min_inclusive": -1.0,
            "max_inclusive": 1.0,
        }
    )


class RangeUnitsType(Enum):
    KM = "km"
    KM_1 = "KM"
    RU = "ru"
    RU_1 = "RU"
    S = "s"
    S_1 = "S"


class RangemodeType(Enum):
    COHERENT = "coherent"
    COHERENT_1 = "COHERENT"
    CONSTANT = "constant"
    CONSTANT_1 = "CONSTANT"
    ONE_WAY = "one_way"
    ONE_WAY_1 = "ONE_WAY"


@dataclass(kw_only=True)
class RdmHeader:
    class Meta:
        name = "rdmHeader"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    creation_date: str = field(
        metadata={
            "name": "CREATION_DATE",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    originator: str = field(
        metadata={
            "name": "ORIGINATOR",
            "type": "Element",
            "namespace": "",
        }
    )
    message_id: str = field(
        metadata={
            "name": "MESSAGE_ID",
            "type": "Element",
            "namespace": "",
        }
    )


class ReentryUncertaintyMethodType(Enum):
    NONE = "NONE"
    ANALYTICAL = "ANALYTICAL"
    STOCHASTIC = "STOCHASTIC"
    EMPIRICAL = "EMPIRICAL"


class RefFrameType(Enum):
    EME2000 = "EME2000"
    EME2000_1 = "eme2000"
    ICRF = "ICRF"
    ICRF_1 = "icrf"
    ITRF2000 = "ITRF2000"
    ITRF2000_1 = "itrf2000"
    ITRF_93 = "ITRF-93"
    ITRF_93_1 = "itrf-93"
    ITRF_97 = "ITRF-97"
    ITRF_97_1 = "itrf-97"
    TOD = "TOD"
    TOD_1 = "tod"


class ReferenceFrameType(Enum):
    EME2000 = "EME2000"
    EME2000_1 = "eme2000"
    GCRF = "GCRF"
    GCRF_1 = "gcrf"
    ITRF = "ITRF"
    ITRF_1 = "itrf"


class RevNumBasisType(Enum):
    VALUE_0 = 0
    VALUE_1 = 1


class RevUnits(Enum):
    REV_DAY = "rev/day"
    REV_DAY_1 = "REV/DAY"


class RotseqType(Enum):
    XYX = "XYX"
    XYZ = "XYZ"
    XZX = "XZX"
    XZY = "XZY"
    YXY = "YXY"
    YXZ = "YXZ"
    YZX = "YZX"
    YZY = "YZY"
    ZXY = "ZXY"
    ZXZ = "ZXZ"
    ZYX = "ZYX"
    ZYZ = "ZYZ"


class ScreenVolumeFrameType(Enum):
    RTN = "RTN"
    RTN_1 = "rtn"
    TVN = "TVN"
    TVN_1 = "tvn"


class ScreenVolumeShapeType(Enum):
    ELLIPSOID = "ELLIPSOID"
    ELLIPSOID_1 = "ellipsoid"
    BOX = "BOX"
    BOX_1 = "box"


class SigmaUunits(Enum):
    DEG_S_1_5 = "deg/s**1.5"


class SigmaVunits(Enum):
    DEG_S_0_5 = "deg/s**0.5"


class SolarFluxUnits(Enum):
    SFU = "SFU"
    VALUE_10_4_JANSKY = "10**4 Jansky"
    VALUE_10_22_W_M_2_HZ = "10**-22 W/(m**2/Hz)"
    VALUE_10_19_ERG_S_CM_2_HZ = "10**-19 erg/(s*cm**2*Hz)"


@dataclass(kw_only=True)
class TdmHeader:
    class Meta:
        name = "tdmHeader"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    creation_date: str = field(
        metadata={
            "name": "CREATION_DATE",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    originator: str = field(
        metadata={
            "name": "ORIGINATOR",
            "type": "Element",
            "namespace": "",
        }
    )
    message_id: None | str = field(
        default=None,
        metadata={
            "name": "MESSAGE_ID",
            "type": "Element",
            "namespace": "",
        },
    )


class ThrustUnits(Enum):
    N = "N"


class TimeUnits(Enum):
    S = "s"


class TimetagRefType(Enum):
    TRANSMIT = "TRANSMIT"
    TRANSMIT_1 = "transmit"
    RECEIVE = "RECEIVE"
    RECEIVE_1 = "receive"


class TorqueUnits(Enum):
    N_M = "N*m"


class TrajBasisType(Enum):
    PREDICTED = "PREDICTED"
    DETERMINED = "DETERMINED"
    TELEMETRY = "TELEMETRY"
    SIMULATED = "SIMULATED"
    OTHER = "OTHER"


@dataclass(kw_only=True)
class UserDefinedParameterType:
    class Meta:
        name = "userDefinedParameterType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: str = field(default="")
    parameter: str = field(
        metadata={
            "type": "Attribute",
        }
    )


class VelocityCovarianceUnits(Enum):
    KM_2_S_2 = "km**2/s**2"


class VelocityUnits(Enum):
    KM_S = "km/s"


class WkgUnits(Enum):
    W_KG = "W/kg"


class YesNoType(Enum):
    YES = "YES"
    YES_1 = "yes"
    NO = "NO"
    NO_1 = "no"


@dataclass(kw_only=True)
class AccType:
    class Meta:
        name = "accType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | AccUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class AcmAttitudeStateType:
    class Meta:
        name = "acmAttitudeStateType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    att_id: None | str = field(
        default=None,
        metadata={
            "name": "ATT_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    att_prev_id: None | str = field(
        default=None,
        metadata={
            "name": "ATT_PREV_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    att_basis: None | AttBasisType = field(
        default=None,
        metadata={
            "name": "ATT_BASIS",
            "type": "Element",
            "namespace": "",
        },
    )
    att_basis_id: None | str = field(
        default=None,
        metadata={
            "name": "ATT_BASIS_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    ref_frame_a: str = field(
        metadata={
            "name": "REF_FRAME_A",
            "type": "Element",
            "namespace": "",
        }
    )
    ref_frame_b: str = field(
        metadata={
            "name": "REF_FRAME_B",
            "type": "Element",
            "namespace": "",
        }
    )
    number_states: int = field(
        metadata={
            "name": "NUMBER_STATES",
            "type": "Element",
            "namespace": "",
        }
    )
    att_type: AcmAttitudeType = field(
        metadata={
            "name": "ATT_TYPE",
            "type": "Element",
            "namespace": "",
        }
    )
    euler_rot_seq: None | RotseqType = field(
        default=None,
        metadata={
            "name": "EULER_ROT_SEQ",
            "type": "Element",
            "namespace": "",
        },
    )
    rate_type: None | AttRateType = field(
        default=None,
        metadata={
            "name": "RATE_TYPE",
            "type": "Element",
            "namespace": "",
        },
    )
    att_line: list[str] = field(
        default_factory=list,
        metadata={
            "name": "attLine",
            "type": "Element",
            "namespace": "",
            "min_occurs": 1,
        },
    )


@dataclass(kw_only=True)
class AcmCovarianceMatrixType:
    class Meta:
        name = "acmCovarianceMatrixType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    cov_id: None | str = field(
        default=None,
        metadata={
            "name": "COV_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    cov_prev_id: None | str = field(
        default=None,
        metadata={
            "name": "COV_PREV_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    cov_basis: None | AttBasisType = field(
        default=None,
        metadata={
            "name": "COV_BASIS",
            "type": "Element",
            "namespace": "",
        },
    )
    cov_basis_id: None | str = field(
        default=None,
        metadata={
            "name": "COV_BASIS_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    cov_ref_frame: None | str = field(
        default=None,
        metadata={
            "name": "COV_REF_FRAME",
            "type": "Element",
            "namespace": "",
        },
    )
    cov_type: AcmCovarianceLineType = field(
        metadata={
            "name": "COV_TYPE",
            "type": "Element",
            "namespace": "",
        }
    )
    cov_line: list[str] = field(
        default_factory=list,
        metadata={
            "name": "covLine",
            "type": "Element",
            "namespace": "",
            "min_occurs": 1,
        },
    )


@dataclass(kw_only=True)
class AemMetadata:
    class Meta:
        name = "aemMetadata"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    object_name: str = field(
        metadata={
            "name": "OBJECT_NAME",
            "type": "Element",
            "namespace": "",
        }
    )
    object_id: str = field(
        metadata={
            "name": "OBJECT_ID",
            "type": "Element",
            "namespace": "",
        }
    )
    center_name: None | str = field(
        default=None,
        metadata={
            "name": "CENTER_NAME",
            "type": "Element",
            "namespace": "",
        },
    )
    ref_frame_a: str = field(
        metadata={
            "name": "REF_FRAME_A",
            "type": "Element",
            "namespace": "",
        }
    )
    ref_frame_b: str = field(
        metadata={
            "name": "REF_FRAME_B",
            "type": "Element",
            "namespace": "",
        }
    )
    time_system: str = field(
        metadata={
            "name": "TIME_SYSTEM",
            "type": "Element",
            "namespace": "",
        }
    )
    start_time: str = field(
        metadata={
            "name": "START_TIME",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    useable_start_time: None | str = field(
        default=None,
        metadata={
            "name": "USEABLE_START_TIME",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    useable_stop_time: None | str = field(
        default=None,
        metadata={
            "name": "USEABLE_STOP_TIME",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    stop_time: str = field(
        metadata={
            "name": "STOP_TIME",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    attitude_type: AttitudeTypeType = field(
        metadata={
            "name": "ATTITUDE_TYPE",
            "type": "Element",
            "namespace": "",
        }
    )
    euler_rot_seq: None | RotseqType = field(
        default=None,
        metadata={
            "name": "EULER_ROT_SEQ",
            "type": "Element",
            "namespace": "",
        },
    )
    angvel_frame: None | str = field(
        default=None,
        metadata={
            "name": "ANGVEL_FRAME",
            "type": "Element",
            "namespace": "",
        },
    )
    interpolation_method: None | str = field(
        default=None,
        metadata={
            "name": "INTERPOLATION_METHOD",
            "type": "Element",
            "namespace": "",
        },
    )
    interpolation_degree: None | int = field(
        default=None,
        metadata={
            "name": "INTERPOLATION_DEGREE",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class AgomType:
    class Meta:
        name = "agomType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | AgomUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class AltType:
    class Meta:
        name = "altType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field(
        metadata={
            "min_inclusive": -430.5,
            "max_inclusive": 8848.0,
        }
    )
    units: None | LengthUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class AngMomentumType:
    class Meta:
        name = "angMomentumType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | AngMomentumUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class AngVelComponentType:
    class Meta:
        name = "angVelComponentType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | AngleRateUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class AngleRateType:
    class Meta:
        name = "angleRateType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | AngleRateUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class AngleType:
    class Meta:
        name = "angleType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field(
        metadata={
            "min_inclusive": -360.0,
            "max_exclusive": 360.0,
        }
    )
    units: None | AngleUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class AreaType:
    class Meta:
        name = "areaType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field(
        metadata={
            "min_inclusive": 0.0,
        }
    )
    units: None | AreaUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class BStarType:
    class Meta:
        name = "bStarType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | BStarUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class BTermType:
    class Meta:
        name = "bTermType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | BTermUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class BallisticCoeffType:
    class Meta:
        name = "ballisticCoeffType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field(
        metadata={
            "min_inclusive": 0.0,
        }
    )
    units: None | BallisticCoeffUnitsType = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class CdmMetadata:
    class Meta:
        name = "cdmMetadata"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    object_value: ObjectType = field(
        metadata={
            "name": "OBJECT",
            "type": "Element",
            "namespace": "",
        }
    )
    object_designator: str = field(
        metadata={
            "name": "OBJECT_DESIGNATOR",
            "type": "Element",
            "namespace": "",
        }
    )
    catalog_name: str = field(
        metadata={
            "name": "CATALOG_NAME",
            "type": "Element",
            "namespace": "",
        }
    )
    object_name: str = field(
        metadata={
            "name": "OBJECT_NAME",
            "type": "Element",
            "namespace": "",
        }
    )
    international_designator: str = field(
        metadata={
            "name": "INTERNATIONAL_DESIGNATOR",
            "type": "Element",
            "namespace": "",
        }
    )
    object_type: None | ObjectDescriptionType = field(
        default=None,
        metadata={
            "name": "OBJECT_TYPE",
            "type": "Element",
            "namespace": "",
        },
    )
    operator_contact_position: None | str = field(
        default=None,
        metadata={
            "name": "OPERATOR_CONTACT_POSITION",
            "type": "Element",
            "namespace": "",
        },
    )
    operator_organization: None | str = field(
        default=None,
        metadata={
            "name": "OPERATOR_ORGANIZATION",
            "type": "Element",
            "namespace": "",
        },
    )
    operator_phone: None | str = field(
        default=None,
        metadata={
            "name": "OPERATOR_PHONE",
            "type": "Element",
            "namespace": "",
        },
    )
    operator_email: None | str = field(
        default=None,
        metadata={
            "name": "OPERATOR_EMAIL",
            "type": "Element",
            "namespace": "",
        },
    )
    ephemeris_name: str = field(
        metadata={
            "name": "EPHEMERIS_NAME",
            "type": "Element",
            "namespace": "",
        }
    )
    covariance_method: CovarianceMethodType = field(
        metadata={
            "name": "COVARIANCE_METHOD",
            "type": "Element",
            "namespace": "",
        }
    )
    maneuverable: ManeuverableType = field(
        metadata={
            "name": "MANEUVERABLE",
            "type": "Element",
            "namespace": "",
        }
    )
    orbit_center: None | str = field(
        default=None,
        metadata={
            "name": "ORBIT_CENTER",
            "type": "Element",
            "namespace": "",
        },
    )
    ref_frame: ReferenceFrameType = field(
        metadata={
            "name": "REF_FRAME",
            "type": "Element",
            "namespace": "",
        }
    )
    gravity_model: None | str = field(
        default=None,
        metadata={
            "name": "GRAVITY_MODEL",
            "type": "Element",
            "namespace": "",
        },
    )
    atmospheric_model: None | str = field(
        default=None,
        metadata={
            "name": "ATMOSPHERIC_MODEL",
            "type": "Element",
            "namespace": "",
        },
    )
    n_body_perturbations: None | str = field(
        default=None,
        metadata={
            "name": "N_BODY_PERTURBATIONS",
            "type": "Element",
            "namespace": "",
        },
    )
    solar_rad_pressure: None | YesNoType = field(
        default=None,
        metadata={
            "name": "SOLAR_RAD_PRESSURE",
            "type": "Element",
            "namespace": "",
        },
    )
    earth_tides: None | YesNoType = field(
        default=None,
        metadata={
            "name": "EARTH_TIDES",
            "type": "Element",
            "namespace": "",
        },
    )
    intrack_thrust: None | YesNoType = field(
        default=None,
        metadata={
            "name": "INTRACK_THRUST",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class CpType:
    class Meta:
        name = "cpType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: list[float] = field(
        default_factory=list,
        metadata={
            "length": 3,
            "tokens": True,
        },
    )
    units: None | LengthUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class DRevType:
    class Meta:
        name = "dRevType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | DRevUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class DayIntervalTypeUo:
    class Meta:
        name = "dayIntervalTypeUO"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field(
        metadata={
            "min_inclusive": 0.0,
        }
    )
    units: None | DayIntervalUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class DayIntervalTypeUr:
    class Meta:
        name = "dayIntervalTypeUR"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field(
        metadata={
            "min_exclusive": 0.0,
        }
    )
    units: DayIntervalUnits = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class DdRevType:
    class Meta:
        name = "ddRevType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | DdRevUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class DeltamassType:
    class Meta:
        name = "deltamassType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field(
        metadata={
            "max_exclusive": 0.0,
        }
    )
    units: None | MassUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class DeltamassTypeZ:
    class Meta:
        name = "deltamassTypeZ"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field(
        metadata={
            "max_inclusive": 0.0,
        }
    )
    units: None | MassUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class DistanceType:
    class Meta:
        name = "distanceType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | PositionUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class DurationType:
    class Meta:
        name = "durationType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field(
        metadata={
            "min_inclusive": 0.0,
        }
    )
    units: None | TimeUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class DvType:
    class Meta:
        name = "dvType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: DvUnits = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class FrequencyType:
    class Meta:
        name = "frequencyType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field(
        metadata={
            "min_exclusive": 0.0,
        }
    )
    units: None | FrequencyUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class GeomagType:
    class Meta:
        name = "geomagType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | GeomagUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class GmType:
    class Meta:
        name = "gmType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field(
        metadata={
            "min_exclusive": 0.0,
        }
    )
    units: None | GmUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class InclinationType:
    class Meta:
        name = "inclinationType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field(
        metadata={
            "min_inclusive": 0.0,
            "max_exclusive": 360.0,
            "max_inclusive": 180.0,
        }
    )
    units: None | AngleUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class Km2Type:
    class Meta:
        name = "km2Type"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | Km2Units = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class Km2S2Type:
    class Meta:
        name = "km2s2Type"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | Km2S2Units = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class Km2SType:
    class Meta:
        name = "km2sType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | Km2SUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class LatType:
    class Meta:
        name = "latType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field(
        metadata={
            "min_inclusive": -90.0,
            "max_inclusive": 90.0,
        }
    )
    units: LatLonUnits = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class LengthTypeUo:
    class Meta:
        name = "lengthTypeUO"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | LengthUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class LengthTypeUr:
    class Meta:
        name = "lengthTypeUR"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: LengthUnits = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class LonType:
    class Meta:
        name = "lonType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field(
        metadata={
            "min_inclusive": -180.0,
            "max_inclusive": 180.0,
        }
    )
    units: LatLonUnits = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class M2Type:
    class Meta:
        name = "m2Type"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: M2Units = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class M2KgType:
    class Meta:
        name = "m2kgType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field(
        metadata={
            "min_inclusive": 0.0,
        }
    )
    units: M2KgUnits = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class M2S2Type:
    class Meta:
        name = "m2s2Type"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: M2S2Units = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class M2S3Type:
    class Meta:
        name = "m2s3Type"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: M2S3Units = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class M2S4Type:
    class Meta:
        name = "m2s4Type"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: M2S4Units = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class M2SType:
    class Meta:
        name = "m2sType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: M2SUnits = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class M3KgType:
    class Meta:
        name = "m3kgType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: M3KgUnits = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class M3Kgs2Type:
    class Meta:
        name = "m3kgs2Type"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: M3Kgs2Units = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class M3KgsType:
    class Meta:
        name = "m3kgsType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: M3KgsUnits = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class M4Kg2Type:
    class Meta:
        name = "m4kg2Type"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: M4Kg2Units = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class ManeuverFreqType:
    class Meta:
        name = "maneuverFreqType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | NumPerYearUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class MassType:
    class Meta:
        name = "massType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field(
        metadata={
            "min_inclusive": 0.0,
        }
    )
    units: None | MassUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class MomentType:
    class Meta:
        name = "momentType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | MomentUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class Ms2Type:
    class Meta:
        name = "ms2Type"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: Ms2Units = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class OcmTrajStateType:
    class Meta:
        name = "ocmTrajStateType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    traj_id: None | str = field(
        default=None,
        metadata={
            "name": "TRAJ_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    traj_prev_id: None | str = field(
        default=None,
        metadata={
            "name": "TRAJ_PREV_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    traj_next_id: None | str = field(
        default=None,
        metadata={
            "name": "TRAJ_NEXT_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    traj_basis: None | TrajBasisType = field(
        default=None,
        metadata={
            "name": "TRAJ_BASIS",
            "type": "Element",
            "namespace": "",
        },
    )
    traj_basis_id: None | str = field(
        default=None,
        metadata={
            "name": "TRAJ_BASIS_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    interpolation: None | str = field(
        default=None,
        metadata={
            "name": "INTERPOLATION",
            "type": "Element",
            "namespace": "",
        },
    )
    interpolation_degree: None | int = field(
        default=None,
        metadata={
            "name": "INTERPOLATION_DEGREE",
            "type": "Element",
            "namespace": "",
        },
    )
    propagator: None | str = field(
        default=None,
        metadata={
            "name": "PROPAGATOR",
            "type": "Element",
            "namespace": "",
        },
    )
    center_name: str = field(
        metadata={
            "name": "CENTER_NAME",
            "type": "Element",
            "namespace": "",
        }
    )
    traj_ref_frame: str = field(
        metadata={
            "name": "TRAJ_REF_FRAME",
            "type": "Element",
            "namespace": "",
        }
    )
    traj_frame_epoch: None | str = field(
        default=None,
        metadata={
            "name": "TRAJ_FRAME_EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    useable_start_time: None | str = field(
        default=None,
        metadata={
            "name": "USEABLE_START_TIME",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    useable_stop_time: None | str = field(
        default=None,
        metadata={
            "name": "USEABLE_STOP_TIME",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    orb_revnum: None | float = field(
        default=None,
        metadata={
            "name": "ORB_REVNUM",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )
    orb_revnum_basis: None | RevNumBasisType = field(
        default=None,
        metadata={
            "name": "ORB_REVNUM_BASIS",
            "type": "Element",
            "namespace": "",
        },
    )
    traj_type: str = field(
        metadata={
            "name": "TRAJ_TYPE",
            "type": "Element",
            "namespace": "",
        }
    )
    orb_averaging: None | str = field(
        default=None,
        metadata={
            "name": "ORB_AVERAGING",
            "type": "Element",
            "namespace": "",
        },
    )
    traj_units: None | str = field(
        default=None,
        metadata={
            "name": "TRAJ_UNITS",
            "type": "Element",
            "namespace": "",
        },
    )
    traj_line: list[str] = field(
        default_factory=list,
        metadata={
            "name": "trajLine",
            "type": "Element",
            "namespace": "",
            "min_occurs": 1,
        },
    )


@dataclass(kw_only=True)
class PercentageTypeUo:
    class Meta:
        name = "percentageTypeUO"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field(
        metadata={
            "min_inclusive": 0.0,
            "max_inclusive": 100.0,
        }
    )
    units: None | PercentageUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class PercentageTypeUr:
    class Meta:
        name = "percentageTypeUR"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field(
        metadata={
            "min_inclusive": 0.0,
            "max_inclusive": 100.0,
        }
    )
    units: PercentageUnits = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class PositionCovarianceType:
    class Meta:
        name = "positionCovarianceType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | PositionCovarianceUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class PositionTypeUo:
    class Meta:
        name = "positionTypeUO"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | PositionUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class PositionTypeUr:
    class Meta:
        name = "positionTypeUR"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: PositionUnits = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class PositionVelocityCovarianceType:
    class Meta:
        name = "positionVelocityCovarianceType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | PositionVelocityCovarianceUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class QuaternionDotComponentType:
    class Meta:
        name = "quaternionDotComponentType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | QuaternionDotUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class QuaternionEphemerisType:
    class Meta:
        name = "quaternionEphemerisType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    epoch: str = field(
        metadata={
            "name": "EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    quaternion: QuaternionType = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class RelTimeType:
    class Meta:
        name = "relTimeType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | TimeUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class RevType:
    class Meta:
        name = "revType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | RevUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class SensorNoiseType:
    class Meta:
        name = "sensorNoiseType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: str = field(default="")
    units: None | AngleUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class SigmaUtype:
    class Meta:
        name = "sigmaUType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | SigmaUunits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class SigmaVtype:
    class Meta:
        name = "sigmaVType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | SigmaVunits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class SolarFluxType:
    class Meta:
        name = "solarFluxType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | SolarFluxUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class TargetMomentumType:
    class Meta:
        name = "targetMomentumType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: list[float] = field(
        default_factory=list,
        metadata={
            "length": 3,
            "tokens": True,
        },
    )
    units: None | AngMomentumUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class TdmAngleType:
    class Meta:
        name = "tdmAngleType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field(
        metadata={
            "min_inclusive": -180.0,
            "max_exclusive": 360.0,
        }
    )
    units: None | AngleUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class TdmMetadata:
    class Meta:
        name = "tdmMetadata"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    track_id: None | str = field(
        default=None,
        metadata={
            "name": "TRACK_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    data_types: None | str = field(
        default=None,
        metadata={
            "name": "DATA_TYPES",
            "type": "Element",
            "namespace": "",
        },
    )
    time_system: str = field(
        metadata={
            "name": "TIME_SYSTEM",
            "type": "Element",
            "namespace": "",
        }
    )
    start_time: None | str = field(
        default=None,
        metadata={
            "name": "START_TIME",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    stop_time: None | str = field(
        default=None,
        metadata={
            "name": "STOP_TIME",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    participant_1: str = field(
        metadata={
            "name": "PARTICIPANT_1",
            "type": "Element",
            "namespace": "",
        }
    )
    participant_2: None | str = field(
        default=None,
        metadata={
            "name": "PARTICIPANT_2",
            "type": "Element",
            "namespace": "",
        },
    )
    participant_3: None | str = field(
        default=None,
        metadata={
            "name": "PARTICIPANT_3",
            "type": "Element",
            "namespace": "",
        },
    )
    participant_4: None | str = field(
        default=None,
        metadata={
            "name": "PARTICIPANT_4",
            "type": "Element",
            "namespace": "",
        },
    )
    participant_5: None | str = field(
        default=None,
        metadata={
            "name": "PARTICIPANT_5",
            "type": "Element",
            "namespace": "",
        },
    )
    mode: None | ModeType = field(
        default=None,
        metadata={
            "name": "MODE",
            "type": "Element",
            "namespace": "",
        },
    )
    path: None | str = field(
        default=None,
        metadata={
            "name": "PATH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\d{1},\d{1}(,\d{1})*",
        },
    )
    path_1: None | str = field(
        default=None,
        metadata={
            "name": "PATH_1",
            "type": "Element",
            "namespace": "",
            "pattern": r"\d{1},\d{1}(,\d{1})*",
        },
    )
    path_2: None | str = field(
        default=None,
        metadata={
            "name": "PATH_2",
            "type": "Element",
            "namespace": "",
            "pattern": r"\d{1},\d{1}(,\d{1})*",
        },
    )
    ephemeris_name_1: None | str = field(
        default=None,
        metadata={
            "name": "EPHEMERIS_NAME_1",
            "type": "Element",
            "namespace": "",
        },
    )
    ephemeris_name_2: None | str = field(
        default=None,
        metadata={
            "name": "EPHEMERIS_NAME_2",
            "type": "Element",
            "namespace": "",
        },
    )
    ephemeris_name_3: None | str = field(
        default=None,
        metadata={
            "name": "EPHEMERIS_NAME_3",
            "type": "Element",
            "namespace": "",
        },
    )
    ephemeris_name_4: None | str = field(
        default=None,
        metadata={
            "name": "EPHEMERIS_NAME_4",
            "type": "Element",
            "namespace": "",
        },
    )
    ephemeris_name_5: None | str = field(
        default=None,
        metadata={
            "name": "EPHEMERIS_NAME_5",
            "type": "Element",
            "namespace": "",
        },
    )
    transmit_band: None | str = field(
        default=None,
        metadata={
            "name": "TRANSMIT_BAND",
            "type": "Element",
            "namespace": "",
        },
    )
    receive_band: None | str = field(
        default=None,
        metadata={
            "name": "RECEIVE_BAND",
            "type": "Element",
            "namespace": "",
        },
    )
    turnaround_numerator: None | int = field(
        default=None,
        metadata={
            "name": "TURNAROUND_NUMERATOR",
            "type": "Element",
            "namespace": "",
        },
    )
    turnaround_denominator: None | int = field(
        default=None,
        metadata={
            "name": "TURNAROUND_DENOMINATOR",
            "type": "Element",
            "namespace": "",
        },
    )
    timetag_ref: None | TimetagRefType = field(
        default=None,
        metadata={
            "name": "TIMETAG_REF",
            "type": "Element",
            "namespace": "",
        },
    )
    integration_interval: None | float = field(
        default=None,
        metadata={
            "name": "INTEGRATION_INTERVAL",
            "type": "Element",
            "namespace": "",
            "min_exclusive": 0.0,
        },
    )
    integration_ref: None | IntegrationRefType = field(
        default=None,
        metadata={
            "name": "INTEGRATION_REF",
            "type": "Element",
            "namespace": "",
        },
    )
    freq_offset: None | float = field(
        default=None,
        metadata={
            "name": "FREQ_OFFSET",
            "type": "Element",
            "namespace": "",
        },
    )
    range_mode: None | RangemodeType = field(
        default=None,
        metadata={
            "name": "RANGE_MODE",
            "type": "Element",
            "namespace": "",
        },
    )
    range_modulus: None | float = field(
        default=None,
        metadata={
            "name": "RANGE_MODULUS",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )
    range_units: None | RangeUnitsType = field(
        default=None,
        metadata={
            "name": "RANGE_UNITS",
            "type": "Element",
            "namespace": "",
        },
    )
    angle_type: None | AngleTypeType = field(
        default=None,
        metadata={
            "name": "ANGLE_TYPE",
            "type": "Element",
            "namespace": "",
        },
    )
    reference_frame: None | RefFrameType = field(
        default=None,
        metadata={
            "name": "REFERENCE_FRAME",
            "type": "Element",
            "namespace": "",
        },
    )
    interpolation: None | str = field(
        default=None,
        metadata={
            "name": "INTERPOLATION",
            "type": "Element",
            "namespace": "",
        },
    )
    interpolation_degree: None | int = field(
        default=None,
        metadata={
            "name": "INTERPOLATION_DEGREE",
            "type": "Element",
            "namespace": "",
        },
    )
    doppler_count_bias: None | float = field(
        default=None,
        metadata={
            "name": "DOPPLER_COUNT_BIAS",
            "type": "Element",
            "namespace": "",
            "min_exclusive": 0.0,
        },
    )
    doppler_count_scale: None | int = field(
        default=None,
        metadata={
            "name": "DOPPLER_COUNT_SCALE",
            "type": "Element",
            "namespace": "",
        },
    )
    doppler_count_rollover: None | YesNoType = field(
        default=None,
        metadata={
            "name": "DOPPLER_COUNT_ROLLOVER",
            "type": "Element",
            "namespace": "",
        },
    )
    transmit_delay_1: None | float = field(
        default=None,
        metadata={
            "name": "TRANSMIT_DELAY_1",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )
    transmit_delay_2: None | float = field(
        default=None,
        metadata={
            "name": "TRANSMIT_DELAY_2",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )
    transmit_delay_3: None | float = field(
        default=None,
        metadata={
            "name": "TRANSMIT_DELAY_3",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )
    transmit_delay_4: None | float = field(
        default=None,
        metadata={
            "name": "TRANSMIT_DELAY_4",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )
    transmit_delay_5: None | float = field(
        default=None,
        metadata={
            "name": "TRANSMIT_DELAY_5",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )
    receive_delay_1: None | float = field(
        default=None,
        metadata={
            "name": "RECEIVE_DELAY_1",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )
    receive_delay_2: None | float = field(
        default=None,
        metadata={
            "name": "RECEIVE_DELAY_2",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )
    receive_delay_3: None | float = field(
        default=None,
        metadata={
            "name": "RECEIVE_DELAY_3",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )
    receive_delay_4: None | float = field(
        default=None,
        metadata={
            "name": "RECEIVE_DELAY_4",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )
    receive_delay_5: None | float = field(
        default=None,
        metadata={
            "name": "RECEIVE_DELAY_5",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )
    data_quality: None | DataQualityType = field(
        default=None,
        metadata={
            "name": "DATA_QUALITY",
            "type": "Element",
            "namespace": "",
        },
    )
    correction_angle_1: None | float = field(
        default=None,
        metadata={
            "name": "CORRECTION_ANGLE_1",
            "type": "Element",
            "namespace": "",
        },
    )
    correction_angle_2: None | float = field(
        default=None,
        metadata={
            "name": "CORRECTION_ANGLE_2",
            "type": "Element",
            "namespace": "",
        },
    )
    correction_doppler: None | float = field(
        default=None,
        metadata={
            "name": "CORRECTION_DOPPLER",
            "type": "Element",
            "namespace": "",
        },
    )
    correction_mag: None | float = field(
        default=None,
        metadata={
            "name": "CORRECTION_MAG",
            "type": "Element",
            "namespace": "",
        },
    )
    correction_range: None | float = field(
        default=None,
        metadata={
            "name": "CORRECTION_RANGE",
            "type": "Element",
            "namespace": "",
        },
    )
    correction_rcs: None | float = field(
        default=None,
        metadata={
            "name": "CORRECTION_RCS",
            "type": "Element",
            "namespace": "",
        },
    )
    correction_receive: None | float = field(
        default=None,
        metadata={
            "name": "CORRECTION_RECEIVE",
            "type": "Element",
            "namespace": "",
        },
    )
    correction_transmit: None | float = field(
        default=None,
        metadata={
            "name": "CORRECTION_TRANSMIT",
            "type": "Element",
            "namespace": "",
        },
    )
    correction_aberration_yearly: None | float = field(
        default=None,
        metadata={
            "name": "CORRECTION_ABERRATION_YEARLY",
            "type": "Element",
            "namespace": "",
        },
    )
    correction_aberration_diurnal: None | float = field(
        default=None,
        metadata={
            "name": "CORRECTION_ABERRATION_DIURNAL",
            "type": "Element",
            "namespace": "",
        },
    )
    corrections_applied: None | YesNoType = field(
        default=None,
        metadata={
            "name": "CORRECTIONS_APPLIED",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class ThrustType:
    class Meta:
        name = "thrustType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | ThrustUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class TimeOffsetType:
    class Meta:
        name = "timeOffsetType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | TimeUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class TorqueType:
    class Meta:
        name = "torqueType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | TorqueUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class UserDefinedType:
    class Meta:
        name = "userDefinedType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
            "sequence": 1,
        },
    )
    user_defined: list[UserDefinedParameterType] = field(
        default_factory=list,
        metadata={
            "name": "USER_DEFINED",
            "type": "Element",
            "namespace": "",
            "sequence": 1,
        },
    )


@dataclass(kw_only=True)
class VelocityCovarianceType:
    class Meta:
        name = "velocityCovarianceType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | VelocityCovarianceUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class VelocityTypeUo:
    class Meta:
        name = "velocityTypeUO"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: None | VelocityUnits = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class VelocityTypeUr:
    class Meta:
        name = "velocityTypeUR"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field()
    units: VelocityUnits = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class WkgType:
    class Meta:
        name = "wkgType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    value: float = field(
        metadata={
            "min_inclusive": 0.0,
        }
    )
    units: WkgUnits = field(
        metadata={
            "type": "Attribute",
        }
    )


@dataclass(kw_only=True)
class AcmManeuverParametersType:
    class Meta:
        name = "acmManeuverParametersType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    man_id: None | str = field(
        default=None,
        metadata={
            "name": "MAN_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    man_prev_id: None | str = field(
        default=None,
        metadata={
            "name": "MAN_PREV_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    man_purpose: str = field(
        metadata={
            "name": "MAN_PURPOSE",
            "type": "Element",
            "namespace": "",
        }
    )
    man_begin_time: RelTimeType = field(
        metadata={
            "name": "MAN_BEGIN_TIME",
            "type": "Element",
            "namespace": "",
        }
    )
    man_end_time: None | RelTimeType = field(
        default=None,
        metadata={
            "name": "MAN_END_TIME",
            "type": "Element",
            "namespace": "",
        },
    )
    man_duration: None | DurationType = field(
        default=None,
        metadata={
            "name": "MAN_DURATION",
            "type": "Element",
            "namespace": "",
        },
    )
    actuator_used: None | str = field(
        default=None,
        metadata={
            "name": "ACTUATOR_USED",
            "type": "Element",
            "namespace": "",
        },
    )
    target_momentum: None | TargetMomentumType = field(
        default=None,
        metadata={
            "name": "TARGET_MOMENTUM",
            "type": "Element",
            "namespace": "",
        },
    )
    target_mom_frame: None | str = field(
        default=None,
        metadata={
            "name": "TARGET_MOM_FRAME",
            "type": "Element",
            "namespace": "",
        },
    )
    target_attitude: list[float] = field(
        default_factory=list,
        metadata={
            "name": "TARGET_ATTITUDE",
            "type": "Element",
            "namespace": "",
            "length": 4,
            "tokens": True,
        },
    )
    target_spinrate: None | AngleRateType = field(
        default=None,
        metadata={
            "name": "TARGET_SPINRATE",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class AcmMetadata:
    class Meta:
        name = "acmMetadata"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    object_name: str = field(
        metadata={
            "name": "OBJECT_NAME",
            "type": "Element",
            "namespace": "",
        }
    )
    international_designator: None | str = field(
        default=None,
        metadata={
            "name": "INTERNATIONAL_DESIGNATOR",
            "type": "Element",
            "namespace": "",
        },
    )
    catalog_name: None | str = field(
        default=None,
        metadata={
            "name": "CATALOG_NAME",
            "type": "Element",
            "namespace": "",
        },
    )
    object_designator: None | str = field(
        default=None,
        metadata={
            "name": "OBJECT_DESIGNATOR",
            "type": "Element",
            "namespace": "",
        },
    )
    originator_poc: None | str = field(
        default=None,
        metadata={
            "name": "ORIGINATOR_POC",
            "type": "Element",
            "namespace": "",
        },
    )
    originator_position: None | str = field(
        default=None,
        metadata={
            "name": "ORIGINATOR_POSITION",
            "type": "Element",
            "namespace": "",
        },
    )
    originator_phone: None | str = field(
        default=None,
        metadata={
            "name": "ORIGINATOR_PHONE",
            "type": "Element",
            "namespace": "",
        },
    )
    originator_email: None | str = field(
        default=None,
        metadata={
            "name": "ORIGINATOR_EMAIL",
            "type": "Element",
            "namespace": "",
        },
    )
    originator_address: None | str = field(
        default=None,
        metadata={
            "name": "ORIGINATOR_ADDRESS",
            "type": "Element",
            "namespace": "",
        },
    )
    odm_msg_link: None | str = field(
        default=None,
        metadata={
            "name": "ODM_MSG_LINK",
            "type": "Element",
            "namespace": "",
        },
    )
    center_name: None | str = field(
        default=None,
        metadata={
            "name": "CENTER_NAME",
            "type": "Element",
            "namespace": "",
        },
    )
    time_system: str = field(
        metadata={
            "name": "TIME_SYSTEM",
            "type": "Element",
            "namespace": "",
        }
    )
    epoch_tzero: str = field(
        metadata={
            "name": "EPOCH_TZERO",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    acm_data_elements: None | str = field(
        default=None,
        metadata={
            "name": "ACM_DATA_ELEMENTS",
            "type": "Element",
            "namespace": "",
        },
    )
    start_time: None | str = field(
        default=None,
        metadata={
            "name": "START_TIME",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    stop_time: None | str = field(
        default=None,
        metadata={
            "name": "STOP_TIME",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    taimutc_at_tzero: None | TimeOffsetType = field(
        default=None,
        metadata={
            "name": "TAIMUTC_AT_TZERO",
            "type": "Element",
            "namespace": "",
        },
    )
    next_leap_epoch: None | str = field(
        default=None,
        metadata={
            "name": "NEXT_LEAP_EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    next_leap_taimutc: None | TimeOffsetType = field(
        default=None,
        metadata={
            "name": "NEXT_LEAP_TAIMUTC",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class AcmPhysicalDescriptionType:
    class Meta:
        name = "acmPhysicalDescriptionType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    drag_coeff: None | float = field(
        default=None,
        metadata={
            "name": "DRAG_COEFF",
            "type": "Element",
            "namespace": "",
        },
    )
    wet_mass: None | MassType = field(
        default=None,
        metadata={
            "name": "WET_MASS",
            "type": "Element",
            "namespace": "",
        },
    )
    dry_mass: None | MassType = field(
        default=None,
        metadata={
            "name": "DRY_MASS",
            "type": "Element",
            "namespace": "",
        },
    )
    cp_ref_frame: None | str = field(
        default=None,
        metadata={
            "name": "CP_REF_FRAME",
            "type": "Element",
            "namespace": "",
        },
    )
    cp: None | CpType = field(
        default=None,
        metadata={
            "name": "CP",
            "type": "Element",
            "namespace": "",
        },
    )
    inertia_ref_frame: None | str = field(
        default=None,
        metadata={
            "name": "INERTIA_REF_FRAME",
            "type": "Element",
            "namespace": "",
        },
    )
    ixx: None | MomentType = field(
        default=None,
        metadata={
            "name": "IXX",
            "type": "Element",
            "namespace": "",
        },
    )
    iyy: None | MomentType = field(
        default=None,
        metadata={
            "name": "IYY",
            "type": "Element",
            "namespace": "",
        },
    )
    izz: None | MomentType = field(
        default=None,
        metadata={
            "name": "IZZ",
            "type": "Element",
            "namespace": "",
        },
    )
    ixy: None | MomentType = field(
        default=None,
        metadata={
            "name": "IXY",
            "type": "Element",
            "namespace": "",
        },
    )
    ixz: None | MomentType = field(
        default=None,
        metadata={
            "name": "IXZ",
            "type": "Element",
            "namespace": "",
        },
    )
    iyz: None | MomentType = field(
        default=None,
        metadata={
            "name": "IYZ",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class AdditionalParametersType:
    class Meta:
        name = "additionalParametersType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    area_pc: None | AreaType = field(
        default=None,
        metadata={
            "name": "AREA_PC",
            "type": "Element",
            "namespace": "",
        },
    )
    area_drg: None | AreaType = field(
        default=None,
        metadata={
            "name": "AREA_DRG",
            "type": "Element",
            "namespace": "",
        },
    )
    area_srp: None | AreaType = field(
        default=None,
        metadata={
            "name": "AREA_SRP",
            "type": "Element",
            "namespace": "",
        },
    )
    mass: None | MassType = field(
        default=None,
        metadata={
            "name": "MASS",
            "type": "Element",
            "namespace": "",
        },
    )
    cd_area_over_mass: None | M2KgType = field(
        default=None,
        metadata={
            "name": "CD_AREA_OVER_MASS",
            "type": "Element",
            "namespace": "",
        },
    )
    cr_area_over_mass: None | M2KgType = field(
        default=None,
        metadata={
            "name": "CR_AREA_OVER_MASS",
            "type": "Element",
            "namespace": "",
        },
    )
    thrust_acceleration: None | Ms2Type = field(
        default=None,
        metadata={
            "name": "THRUST_ACCELERATION",
            "type": "Element",
            "namespace": "",
        },
    )
    sedr: None | WkgType = field(
        default=None,
        metadata={
            "name": "SEDR",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class AngVelStateType:
    class Meta:
        name = "angVelStateType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    ref_frame_a: str = field(
        metadata={
            "name": "REF_FRAME_A",
            "type": "Element",
            "namespace": "",
        }
    )
    ref_frame_b: str = field(
        metadata={
            "name": "REF_FRAME_B",
            "type": "Element",
            "namespace": "",
        }
    )
    angvel_frame: str = field(
        metadata={
            "name": "ANGVEL_FRAME",
            "type": "Element",
            "namespace": "",
        }
    )
    angvel_x: AngVelComponentType = field(
        metadata={
            "name": "ANGVEL_X",
            "type": "Element",
            "namespace": "",
        }
    )
    angvel_y: AngVelComponentType = field(
        metadata={
            "name": "ANGVEL_Y",
            "type": "Element",
            "namespace": "",
        }
    )
    angvel_z: AngVelComponentType = field(
        metadata={
            "name": "ANGVEL_Z",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class AngVelType:
    class Meta:
        name = "angVelType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    angvel_x: AngVelComponentType = field(
        metadata={
            "name": "ANGVEL_X",
            "type": "Element",
            "namespace": "",
        }
    )
    angvel_y: AngVelComponentType = field(
        metadata={
            "name": "ANGVEL_Y",
            "type": "Element",
            "namespace": "",
        }
    )
    angvel_z: AngVelComponentType = field(
        metadata={
            "name": "ANGVEL_Z",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class AtmosphericReentryParametersType:
    class Meta:
        name = "atmosphericReentryParametersType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    orbit_lifetime: DayIntervalTypeUr = field(
        metadata={
            "name": "ORBIT_LIFETIME",
            "type": "Element",
            "namespace": "",
        }
    )
    reentry_altitude: PositionTypeUr = field(
        metadata={
            "name": "REENTRY_ALTITUDE",
            "type": "Element",
            "namespace": "",
        }
    )
    orbit_lifetime_window_start: None | DayIntervalTypeUr = field(
        default=None,
        metadata={
            "name": "ORBIT_LIFETIME_WINDOW_START",
            "type": "Element",
            "namespace": "",
        },
    )
    orbit_lifetime_window_end: None | DayIntervalTypeUr = field(
        default=None,
        metadata={
            "name": "ORBIT_LIFETIME_WINDOW_END",
            "type": "Element",
            "namespace": "",
        },
    )
    nominal_reentry_epoch: None | str = field(
        default=None,
        metadata={
            "name": "NOMINAL_REENTRY_EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    reentry_window_start: None | str = field(
        default=None,
        metadata={
            "name": "REENTRY_WINDOW_START",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    reentry_window_end: None | str = field(
        default=None,
        metadata={
            "name": "REENTRY_WINDOW_END",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    orbit_lifetime_confidence_level: None | PercentageTypeUr = field(
        default=None,
        metadata={
            "name": "ORBIT_LIFETIME_CONFIDENCE_LEVEL",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class AttManeuverStateType:
    class Meta:
        name = "attManeuverStateType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    man_epoch_start: str = field(
        metadata={
            "name": "MAN_EPOCH_START",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    man_duration: DurationType = field(
        metadata={
            "name": "MAN_DURATION",
            "type": "Element",
            "namespace": "",
        }
    )
    man_ref_frame: str = field(
        metadata={
            "name": "MAN_REF_FRAME",
            "type": "Element",
            "namespace": "",
        }
    )
    man_tor_x: TorqueType = field(
        metadata={
            "name": "MAN_TOR_X",
            "type": "Element",
            "namespace": "",
        }
    )
    man_tor_y: TorqueType = field(
        metadata={
            "name": "MAN_TOR_Y",
            "type": "Element",
            "namespace": "",
        }
    )
    man_tor_z: TorqueType = field(
        metadata={
            "name": "MAN_TOR_Z",
            "type": "Element",
            "namespace": "",
        }
    )
    man_delta_mass: None | DeltamassTypeZ = field(
        default=None,
        metadata={
            "name": "MAN_DELTA_MASS",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class CdmCovarianceMatrixType:
    class Meta:
        name = "cdmCovarianceMatrixType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    cr_r: M2Type = field(
        metadata={
            "name": "CR_R",
            "type": "Element",
            "namespace": "",
        }
    )
    ct_r: M2Type = field(
        metadata={
            "name": "CT_R",
            "type": "Element",
            "namespace": "",
        }
    )
    ct_t: M2Type = field(
        metadata={
            "name": "CT_T",
            "type": "Element",
            "namespace": "",
        }
    )
    cn_r: M2Type = field(
        metadata={
            "name": "CN_R",
            "type": "Element",
            "namespace": "",
        }
    )
    cn_t: M2Type = field(
        metadata={
            "name": "CN_T",
            "type": "Element",
            "namespace": "",
        }
    )
    cn_n: M2Type = field(
        metadata={
            "name": "CN_N",
            "type": "Element",
            "namespace": "",
        }
    )
    crdot_r: M2SType = field(
        metadata={
            "name": "CRDOT_R",
            "type": "Element",
            "namespace": "",
        }
    )
    crdot_t: M2SType = field(
        metadata={
            "name": "CRDOT_T",
            "type": "Element",
            "namespace": "",
        }
    )
    crdot_n: M2SType = field(
        metadata={
            "name": "CRDOT_N",
            "type": "Element",
            "namespace": "",
        }
    )
    crdot_rdot: M2S2Type = field(
        metadata={
            "name": "CRDOT_RDOT",
            "type": "Element",
            "namespace": "",
        }
    )
    ctdot_r: M2SType = field(
        metadata={
            "name": "CTDOT_R",
            "type": "Element",
            "namespace": "",
        }
    )
    ctdot_t: M2SType = field(
        metadata={
            "name": "CTDOT_T",
            "type": "Element",
            "namespace": "",
        }
    )
    ctdot_n: M2SType = field(
        metadata={
            "name": "CTDOT_N",
            "type": "Element",
            "namespace": "",
        }
    )
    ctdot_rdot: M2S2Type = field(
        metadata={
            "name": "CTDOT_RDOT",
            "type": "Element",
            "namespace": "",
        }
    )
    ctdot_tdot: M2S2Type = field(
        metadata={
            "name": "CTDOT_TDOT",
            "type": "Element",
            "namespace": "",
        }
    )
    cndot_r: M2SType = field(
        metadata={
            "name": "CNDOT_R",
            "type": "Element",
            "namespace": "",
        }
    )
    cndot_t: M2SType = field(
        metadata={
            "name": "CNDOT_T",
            "type": "Element",
            "namespace": "",
        }
    )
    cndot_n: M2SType = field(
        metadata={
            "name": "CNDOT_N",
            "type": "Element",
            "namespace": "",
        }
    )
    cndot_rdot: M2S2Type = field(
        metadata={
            "name": "CNDOT_RDOT",
            "type": "Element",
            "namespace": "",
        }
    )
    cndot_tdot: M2S2Type = field(
        metadata={
            "name": "CNDOT_TDOT",
            "type": "Element",
            "namespace": "",
        }
    )
    cndot_ndot: M2S2Type = field(
        metadata={
            "name": "CNDOT_NDOT",
            "type": "Element",
            "namespace": "",
        }
    )
    cdrg_r: None | M3KgType = field(
        default=None,
        metadata={
            "name": "CDRG_R",
            "type": "Element",
            "namespace": "",
        },
    )
    cdrg_t: None | M3KgType = field(
        default=None,
        metadata={
            "name": "CDRG_T",
            "type": "Element",
            "namespace": "",
        },
    )
    cdrg_n: None | M3KgType = field(
        default=None,
        metadata={
            "name": "CDRG_N",
            "type": "Element",
            "namespace": "",
        },
    )
    cdrg_rdot: None | M3KgsType = field(
        default=None,
        metadata={
            "name": "CDRG_RDOT",
            "type": "Element",
            "namespace": "",
        },
    )
    cdrg_tdot: None | M3KgsType = field(
        default=None,
        metadata={
            "name": "CDRG_TDOT",
            "type": "Element",
            "namespace": "",
        },
    )
    cdrg_ndot: None | M3KgsType = field(
        default=None,
        metadata={
            "name": "CDRG_NDOT",
            "type": "Element",
            "namespace": "",
        },
    )
    cdrg_drg: None | M4Kg2Type = field(
        default=None,
        metadata={
            "name": "CDRG_DRG",
            "type": "Element",
            "namespace": "",
        },
    )
    csrp_r: None | M3KgType = field(
        default=None,
        metadata={
            "name": "CSRP_R",
            "type": "Element",
            "namespace": "",
        },
    )
    csrp_t: None | M3KgType = field(
        default=None,
        metadata={
            "name": "CSRP_T",
            "type": "Element",
            "namespace": "",
        },
    )
    csrp_n: None | M3KgType = field(
        default=None,
        metadata={
            "name": "CSRP_N",
            "type": "Element",
            "namespace": "",
        },
    )
    csrp_rdot: None | M3KgsType = field(
        default=None,
        metadata={
            "name": "CSRP_RDOT",
            "type": "Element",
            "namespace": "",
        },
    )
    csrp_tdot: None | M3KgsType = field(
        default=None,
        metadata={
            "name": "CSRP_TDOT",
            "type": "Element",
            "namespace": "",
        },
    )
    csrp_ndot: None | M3KgsType = field(
        default=None,
        metadata={
            "name": "CSRP_NDOT",
            "type": "Element",
            "namespace": "",
        },
    )
    csrp_drg: None | M4Kg2Type = field(
        default=None,
        metadata={
            "name": "CSRP_DRG",
            "type": "Element",
            "namespace": "",
        },
    )
    csrp_srp: None | M4Kg2Type = field(
        default=None,
        metadata={
            "name": "CSRP_SRP",
            "type": "Element",
            "namespace": "",
        },
    )
    cthr_r: None | M2S2Type = field(
        default=None,
        metadata={
            "name": "CTHR_R",
            "type": "Element",
            "namespace": "",
        },
    )
    cthr_t: None | M2S2Type = field(
        default=None,
        metadata={
            "name": "CTHR_T",
            "type": "Element",
            "namespace": "",
        },
    )
    cthr_n: None | M2S2Type = field(
        default=None,
        metadata={
            "name": "CTHR_N",
            "type": "Element",
            "namespace": "",
        },
    )
    cthr_rdot: None | M2S3Type = field(
        default=None,
        metadata={
            "name": "CTHR_RDOT",
            "type": "Element",
            "namespace": "",
        },
    )
    cthr_tdot: None | M2S3Type = field(
        default=None,
        metadata={
            "name": "CTHR_TDOT",
            "type": "Element",
            "namespace": "",
        },
    )
    cthr_ndot: None | M2S3Type = field(
        default=None,
        metadata={
            "name": "CTHR_NDOT",
            "type": "Element",
            "namespace": "",
        },
    )
    cthr_drg: None | M3Kgs2Type = field(
        default=None,
        metadata={
            "name": "CTHR_DRG",
            "type": "Element",
            "namespace": "",
        },
    )
    cthr_srp: None | M3Kgs2Type = field(
        default=None,
        metadata={
            "name": "CTHR_SRP",
            "type": "Element",
            "namespace": "",
        },
    )
    cthr_thr: None | M2S4Type = field(
        default=None,
        metadata={
            "name": "CTHR_THR",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class CdmStateVectorType:
    class Meta:
        name = "cdmStateVectorType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    x: PositionTypeUr = field(
        metadata={
            "name": "X",
            "type": "Element",
            "namespace": "",
        }
    )
    y: PositionTypeUr = field(
        metadata={
            "name": "Y",
            "type": "Element",
            "namespace": "",
        }
    )
    z: PositionTypeUr = field(
        metadata={
            "name": "Z",
            "type": "Element",
            "namespace": "",
        }
    )
    x_dot: VelocityTypeUr = field(
        metadata={
            "name": "X_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    y_dot: VelocityTypeUr = field(
        metadata={
            "name": "Y_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    z_dot: VelocityTypeUr = field(
        metadata={
            "name": "Z_DOT",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class EulerAngleAngVelType:
    class Meta:
        name = "eulerAngleAngVelType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    epoch: str = field(
        metadata={
            "name": "EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    angle_1: AngleType = field(
        metadata={
            "name": "ANGLE_1",
            "type": "Element",
            "namespace": "",
        }
    )
    angle_2: AngleType = field(
        metadata={
            "name": "ANGLE_2",
            "type": "Element",
            "namespace": "",
        }
    )
    angle_3: AngleType = field(
        metadata={
            "name": "ANGLE_3",
            "type": "Element",
            "namespace": "",
        }
    )
    angvel_x: AngVelComponentType = field(
        metadata={
            "name": "ANGVEL_X",
            "type": "Element",
            "namespace": "",
        }
    )
    angvel_y: AngVelComponentType = field(
        metadata={
            "name": "ANGVEL_Y",
            "type": "Element",
            "namespace": "",
        }
    )
    angvel_z: AngVelComponentType = field(
        metadata={
            "name": "ANGVEL_Z",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class EulerAngleDerivativeType:
    class Meta:
        name = "eulerAngleDerivativeType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    epoch: str = field(
        metadata={
            "name": "EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    angle_1: AngleType = field(
        metadata={
            "name": "ANGLE_1",
            "type": "Element",
            "namespace": "",
        }
    )
    angle_2: AngleType = field(
        metadata={
            "name": "ANGLE_2",
            "type": "Element",
            "namespace": "",
        }
    )
    angle_3: AngleType = field(
        metadata={
            "name": "ANGLE_3",
            "type": "Element",
            "namespace": "",
        }
    )
    angle_1_dot: AngleRateType = field(
        metadata={
            "name": "ANGLE_1_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    angle_2_dot: AngleRateType = field(
        metadata={
            "name": "ANGLE_2_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    angle_3_dot: AngleRateType = field(
        metadata={
            "name": "ANGLE_3_DOT",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class EulerAngleStateType:
    class Meta:
        name = "eulerAngleStateType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    ref_frame_a: str = field(
        metadata={
            "name": "REF_FRAME_A",
            "type": "Element",
            "namespace": "",
        }
    )
    ref_frame_b: str = field(
        metadata={
            "name": "REF_FRAME_B",
            "type": "Element",
            "namespace": "",
        }
    )
    euler_rot_seq: RotseqType = field(
        metadata={
            "name": "EULER_ROT_SEQ",
            "type": "Element",
            "namespace": "",
        }
    )
    angle_1: AngleType = field(
        metadata={
            "name": "ANGLE_1",
            "type": "Element",
            "namespace": "",
        }
    )
    angle_2: AngleType = field(
        metadata={
            "name": "ANGLE_2",
            "type": "Element",
            "namespace": "",
        }
    )
    angle_3: AngleType = field(
        metadata={
            "name": "ANGLE_3",
            "type": "Element",
            "namespace": "",
        }
    )
    angle_1_dot: None | AngleRateType = field(
        default=None,
        metadata={
            "name": "ANGLE_1_DOT",
            "type": "Element",
            "namespace": "",
        },
    )
    angle_2_dot: None | AngleRateType = field(
        default=None,
        metadata={
            "name": "ANGLE_2_DOT",
            "type": "Element",
            "namespace": "",
        },
    )
    angle_3_dot: None | AngleRateType = field(
        default=None,
        metadata={
            "name": "ANGLE_3_DOT",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class EulerAngleType:
    class Meta:
        name = "eulerAngleType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    epoch: str = field(
        metadata={
            "name": "EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    angle_1: AngleType = field(
        metadata={
            "name": "ANGLE_1",
            "type": "Element",
            "namespace": "",
        }
    )
    angle_2: AngleType = field(
        metadata={
            "name": "ANGLE_2",
            "type": "Element",
            "namespace": "",
        }
    )
    angle_3: AngleType = field(
        metadata={
            "name": "ANGLE_3",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class GroundImpactParametersType:
    class Meta:
        name = "groundImpactParametersType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    probability_of_impact: None | float = field(
        default=None,
        metadata={
            "name": "PROBABILITY_OF_IMPACT",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
            "max_inclusive": 1.0,
        },
    )
    probability_of_burn_up: None | float = field(
        default=None,
        metadata={
            "name": "PROBABILITY_OF_BURN_UP",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
            "max_inclusive": 1.0,
        },
    )
    probability_of_break_up: None | float = field(
        default=None,
        metadata={
            "name": "PROBABILITY_OF_BREAK_UP",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
            "max_inclusive": 1.0,
        },
    )
    probability_of_land_impact: None | float = field(
        default=None,
        metadata={
            "name": "PROBABILITY_OF_LAND_IMPACT",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
            "max_inclusive": 1.0,
        },
    )
    probability_of_casualty: None | float = field(
        default=None,
        metadata={
            "name": "PROBABILITY_OF_CASUALTY",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
            "max_inclusive": 1.0,
        },
    )
    nominal_impact_epoch: None | str = field(
        default=None,
        metadata={
            "name": "NOMINAL_IMPACT_EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    impact_window_start: None | str = field(
        default=None,
        metadata={
            "name": "IMPACT_WINDOW_START",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    impact_window_end: None | str = field(
        default=None,
        metadata={
            "name": "IMPACT_WINDOW_END",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    impact_ref_frame: None | str = field(
        default=None,
        metadata={
            "name": "IMPACT_REF_FRAME",
            "type": "Element",
            "namespace": "",
        },
    )
    nominal_impact_lon: None | LonType = field(
        default=None,
        metadata={
            "name": "NOMINAL_IMPACT_LON",
            "type": "Element",
            "namespace": "",
        },
    )
    nominal_impact_lat: None | LatType = field(
        default=None,
        metadata={
            "name": "NOMINAL_IMPACT_LAT",
            "type": "Element",
            "namespace": "",
        },
    )
    nominal_impact_alt: None | AltType = field(
        default=None,
        metadata={
            "name": "NOMINAL_IMPACT_ALT",
            "type": "Element",
            "namespace": "",
        },
    )
    impact_1_confidence: None | PercentageTypeUr = field(
        default=None,
        metadata={
            "name": "IMPACT_1_CONFIDENCE",
            "type": "Element",
            "namespace": "",
        },
    )
    impact_1_start_lon: None | LonType = field(
        default=None,
        metadata={
            "name": "IMPACT_1_START_LON",
            "type": "Element",
            "namespace": "",
        },
    )
    impact_1_start_lat: None | LatType = field(
        default=None,
        metadata={
            "name": "IMPACT_1_START_LAT",
            "type": "Element",
            "namespace": "",
        },
    )
    impact_1_stop_lon: None | LonType = field(
        default=None,
        metadata={
            "name": "IMPACT_1_STOP_LON",
            "type": "Element",
            "namespace": "",
        },
    )
    impact_1_stop_lat: None | LatType = field(
        default=None,
        metadata={
            "name": "IMPACT_1_STOP_LAT",
            "type": "Element",
            "namespace": "",
        },
    )
    impact_1_cross_track: None | DistanceType = field(
        default=None,
        metadata={
            "name": "IMPACT_1_CROSS_TRACK",
            "type": "Element",
            "namespace": "",
        },
    )
    impact_2_confidence: None | PercentageTypeUr = field(
        default=None,
        metadata={
            "name": "IMPACT_2_CONFIDENCE",
            "type": "Element",
            "namespace": "",
        },
    )
    impact_2_start_lon: None | LonType = field(
        default=None,
        metadata={
            "name": "IMPACT_2_START_LON",
            "type": "Element",
            "namespace": "",
        },
    )
    impact_2_start_lat: None | LatType = field(
        default=None,
        metadata={
            "name": "IMPACT_2_START_LAT",
            "type": "Element",
            "namespace": "",
        },
    )
    impact_2_stop_lon: None | LonType = field(
        default=None,
        metadata={
            "name": "IMPACT_2_STOP_LON",
            "type": "Element",
            "namespace": "",
        },
    )
    impact_2_stop_lat: None | LatType = field(
        default=None,
        metadata={
            "name": "IMPACT_2_STOP_LAT",
            "type": "Element",
            "namespace": "",
        },
    )
    impact_2_cross_track: None | DistanceType = field(
        default=None,
        metadata={
            "name": "IMPACT_2_CROSS_TRACK",
            "type": "Element",
            "namespace": "",
        },
    )
    impact_3_confidence: None | PercentageTypeUr = field(
        default=None,
        metadata={
            "name": "IMPACT_3_CONFIDENCE",
            "type": "Element",
            "namespace": "",
        },
    )
    impact_3_start_lon: None | LonType = field(
        default=None,
        metadata={
            "name": "IMPACT_3_START_LON",
            "type": "Element",
            "namespace": "",
        },
    )
    impact_3_start_lat: None | LatType = field(
        default=None,
        metadata={
            "name": "IMPACT_3_START_LAT",
            "type": "Element",
            "namespace": "",
        },
    )
    impact_3_stop_lon: None | LonType = field(
        default=None,
        metadata={
            "name": "IMPACT_3_STOP_LON",
            "type": "Element",
            "namespace": "",
        },
    )
    impact_3_stop_lat: None | LatType = field(
        default=None,
        metadata={
            "name": "IMPACT_3_STOP_LAT",
            "type": "Element",
            "namespace": "",
        },
    )
    impact_3_cross_track: None | DistanceType = field(
        default=None,
        metadata={
            "name": "IMPACT_3_CROSS_TRACK",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class InertiaStateType:
    class Meta:
        name = "inertiaStateType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    inertia_ref_frame: str = field(
        metadata={
            "name": "INERTIA_REF_FRAME",
            "type": "Element",
            "namespace": "",
        }
    )
    ixx: MomentType = field(
        metadata={
            "name": "IXX",
            "type": "Element",
            "namespace": "",
        }
    )
    iyy: MomentType = field(
        metadata={
            "name": "IYY",
            "type": "Element",
            "namespace": "",
        }
    )
    izz: MomentType = field(
        metadata={
            "name": "IZZ",
            "type": "Element",
            "namespace": "",
        }
    )
    ixy: MomentType = field(
        metadata={
            "name": "IXY",
            "type": "Element",
            "namespace": "",
        }
    )
    ixz: MomentType = field(
        metadata={
            "name": "IXZ",
            "type": "Element",
            "namespace": "",
        }
    )
    iyz: MomentType = field(
        metadata={
            "name": "IYZ",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class KeplerianElementsType:
    class Meta:
        name = "keplerianElementsType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    semi_major_axis: DistanceType = field(
        metadata={
            "name": "SEMI_MAJOR_AXIS",
            "type": "Element",
            "namespace": "",
        }
    )
    eccentricity: float = field(
        metadata={
            "name": "ECCENTRICITY",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        }
    )
    inclination: InclinationType = field(
        metadata={
            "name": "INCLINATION",
            "type": "Element",
            "namespace": "",
        }
    )
    ra_of_asc_node: AngleType = field(
        metadata={
            "name": "RA_OF_ASC_NODE",
            "type": "Element",
            "namespace": "",
        }
    )
    arg_of_pericenter: AngleType = field(
        metadata={
            "name": "ARG_OF_PERICENTER",
            "type": "Element",
            "namespace": "",
        }
    )
    true_anomaly: None | AngleType = field(
        default=None,
        metadata={
            "name": "TRUE_ANOMALY",
            "type": "Element",
            "namespace": "",
        },
    )
    mean_anomaly: None | AngleType = field(
        default=None,
        metadata={
            "name": "MEAN_ANOMALY",
            "type": "Element",
            "namespace": "",
        },
    )
    gm: GmType = field(
        metadata={
            "name": "GM",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class ManeuverParametersType:
    class Meta:
        name = "maneuverParametersType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    man_epoch_ignition: str = field(
        metadata={
            "name": "MAN_EPOCH_IGNITION",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    man_duration: DurationType = field(
        metadata={
            "name": "MAN_DURATION",
            "type": "Element",
            "namespace": "",
        }
    )
    man_delta_mass: DeltamassTypeZ = field(
        metadata={
            "name": "MAN_DELTA_MASS",
            "type": "Element",
            "namespace": "",
        }
    )
    man_ref_frame: str = field(
        metadata={
            "name": "MAN_REF_FRAME",
            "type": "Element",
            "namespace": "",
        }
    )
    man_dv_1: VelocityTypeUo = field(
        metadata={
            "name": "MAN_DV_1",
            "type": "Element",
            "namespace": "",
        }
    )
    man_dv_2: VelocityTypeUo = field(
        metadata={
            "name": "MAN_DV_2",
            "type": "Element",
            "namespace": "",
        }
    )
    man_dv_3: VelocityTypeUo = field(
        metadata={
            "name": "MAN_DV_3",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class MeanElementsType:
    class Meta:
        name = "meanElementsType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    epoch: str = field(
        metadata={
            "name": "EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    semi_major_axis: None | DistanceType = field(
        default=None,
        metadata={
            "name": "SEMI_MAJOR_AXIS",
            "type": "Element",
            "namespace": "",
        },
    )
    mean_motion: None | RevType = field(
        default=None,
        metadata={
            "name": "MEAN_MOTION",
            "type": "Element",
            "namespace": "",
        },
    )
    eccentricity: float = field(
        metadata={
            "name": "ECCENTRICITY",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        }
    )
    inclination: InclinationType = field(
        metadata={
            "name": "INCLINATION",
            "type": "Element",
            "namespace": "",
        }
    )
    ra_of_asc_node: AngleType = field(
        metadata={
            "name": "RA_OF_ASC_NODE",
            "type": "Element",
            "namespace": "",
        }
    )
    arg_of_pericenter: AngleType = field(
        metadata={
            "name": "ARG_OF_PERICENTER",
            "type": "Element",
            "namespace": "",
        }
    )
    mean_anomaly: AngleType = field(
        metadata={
            "name": "MEAN_ANOMALY",
            "type": "Element",
            "namespace": "",
        }
    )
    gm: None | GmType = field(
        default=None,
        metadata={
            "name": "GM",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class OcmCovarianceMatrixType:
    class Meta:
        name = "ocmCovarianceMatrixType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    cov_id: None | str = field(
        default=None,
        metadata={
            "name": "COV_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    cov_prev_id: None | str = field(
        default=None,
        metadata={
            "name": "COV_PREV_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    cov_next_id: None | str = field(
        default=None,
        metadata={
            "name": "COV_NEXT_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    cov_basis: None | CovBasisType = field(
        default=None,
        metadata={
            "name": "COV_BASIS",
            "type": "Element",
            "namespace": "",
        },
    )
    cov_basis_id: None | str = field(
        default=None,
        metadata={
            "name": "COV_BASIS_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    cov_ref_frame: str = field(
        metadata={
            "name": "COV_REF_FRAME",
            "type": "Element",
            "namespace": "",
        }
    )
    cov_frame_epoch: None | str = field(
        default=None,
        metadata={
            "name": "COV_FRAME_EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    cov_scale_min: None | float = field(
        default=None,
        metadata={
            "name": "COV_SCALE_MIN",
            "type": "Element",
            "namespace": "",
        },
    )
    cov_scale_max: None | float = field(
        default=None,
        metadata={
            "name": "COV_SCALE_MAX",
            "type": "Element",
            "namespace": "",
        },
    )
    cov_confidence: None | PercentageTypeUo = field(
        default=None,
        metadata={
            "name": "COV_CONFIDENCE",
            "type": "Element",
            "namespace": "",
        },
    )
    cov_type: str = field(
        metadata={
            "name": "COV_TYPE",
            "type": "Element",
            "namespace": "",
        }
    )
    cov_ordering: CovOrderType = field(
        metadata={
            "name": "COV_ORDERING",
            "type": "Element",
            "namespace": "",
        }
    )
    cov_units: None | str = field(
        default=None,
        metadata={
            "name": "COV_UNITS",
            "type": "Element",
            "namespace": "",
        },
    )
    cov_line: list[str] = field(
        default_factory=list,
        metadata={
            "name": "covLine",
            "type": "Element",
            "namespace": "",
            "min_occurs": 1,
        },
    )


@dataclass(kw_only=True)
class OcmManeuverParametersType:
    class Meta:
        name = "ocmManeuverParametersType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    man_id: str = field(
        metadata={
            "name": "MAN_ID",
            "type": "Element",
            "namespace": "",
        }
    )
    man_prev_id: None | str = field(
        default=None,
        metadata={
            "name": "MAN_PREV_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    man_next_id: None | str = field(
        default=None,
        metadata={
            "name": "MAN_NEXT_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    man_basis: None | ManBasisType = field(
        default=None,
        metadata={
            "name": "MAN_BASIS",
            "type": "Element",
            "namespace": "",
        },
    )
    man_basis_id: None | str = field(
        default=None,
        metadata={
            "name": "MAN_BASIS_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    man_device_id: str = field(
        metadata={
            "name": "MAN_DEVICE_ID",
            "type": "Element",
            "namespace": "",
        }
    )
    man_prev_epoch: None | str = field(
        default=None,
        metadata={
            "name": "MAN_PREV_EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    man_next_epoch: None | str = field(
        default=None,
        metadata={
            "name": "MAN_NEXT_EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    man_purpose: None | str = field(
        default=None,
        metadata={
            "name": "MAN_PURPOSE",
            "type": "Element",
            "namespace": "",
        },
    )
    man_pred_source: None | str = field(
        default=None,
        metadata={
            "name": "MAN_PRED_SOURCE",
            "type": "Element",
            "namespace": "",
        },
    )
    man_ref_frame: str = field(
        metadata={
            "name": "MAN_REF_FRAME",
            "type": "Element",
            "namespace": "",
        }
    )
    man_frame_epoch: None | str = field(
        default=None,
        metadata={
            "name": "MAN_FRAME_EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    grav_assist_name: None | str = field(
        default=None,
        metadata={
            "name": "GRAV_ASSIST_NAME",
            "type": "Element",
            "namespace": "",
        },
    )
    dc_type: ManDctype = field(
        metadata={
            "name": "DC_TYPE",
            "type": "Element",
            "namespace": "",
        }
    )
    dc_win_open: None | str = field(
        default=None,
        metadata={
            "name": "DC_WIN_OPEN",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    dc_win_close: None | str = field(
        default=None,
        metadata={
            "name": "DC_WIN_CLOSE",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    dc_min_cycles: None | int = field(
        default=None,
        metadata={
            "name": "DC_MIN_CYCLES",
            "type": "Element",
            "namespace": "",
        },
    )
    dc_max_cycles: None | int = field(
        default=None,
        metadata={
            "name": "DC_MAX_CYCLES",
            "type": "Element",
            "namespace": "",
        },
    )
    dc_exec_start: None | str = field(
        default=None,
        metadata={
            "name": "DC_EXEC_START",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    dc_exec_stop: None | str = field(
        default=None,
        metadata={
            "name": "DC_EXEC_STOP",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    dc_ref_time: None | str = field(
        default=None,
        metadata={
            "name": "DC_REF_TIME",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    dc_time_pulse_duration: None | DurationType = field(
        default=None,
        metadata={
            "name": "DC_TIME_PULSE_DURATION",
            "type": "Element",
            "namespace": "",
        },
    )
    dc_time_pulse_period: None | DurationType = field(
        default=None,
        metadata={
            "name": "DC_TIME_PULSE_PERIOD",
            "type": "Element",
            "namespace": "",
        },
    )
    dc_ref_dir: list[float] = field(
        default_factory=list,
        metadata={
            "name": "DC_REF_DIR",
            "type": "Element",
            "namespace": "",
            "length": 3,
            "tokens": True,
        },
    )
    dc_body_frame: None | str = field(
        default=None,
        metadata={
            "name": "DC_BODY_FRAME",
            "type": "Element",
            "namespace": "",
        },
    )
    dc_body_trigger: list[float] = field(
        default_factory=list,
        metadata={
            "name": "DC_BODY_TRIGGER",
            "type": "Element",
            "namespace": "",
            "length": 3,
            "tokens": True,
        },
    )
    dc_pa_start_angle: None | AngleType = field(
        default=None,
        metadata={
            "name": "DC_PA_START_ANGLE",
            "type": "Element",
            "namespace": "",
        },
    )
    dc_pa_stop_angle: None | AngleType = field(
        default=None,
        metadata={
            "name": "DC_PA_STOP_ANGLE",
            "type": "Element",
            "namespace": "",
        },
    )
    man_composition: str = field(
        metadata={
            "name": "MAN_COMPOSITION",
            "type": "Element",
            "namespace": "",
        }
    )
    man_units: None | str = field(
        default=None,
        metadata={
            "name": "MAN_UNITS",
            "type": "Element",
            "namespace": "",
        },
    )
    man_line: list[str] = field(
        default_factory=list,
        metadata={
            "name": "manLine",
            "type": "Element",
            "namespace": "",
            "min_occurs": 1,
        },
    )


@dataclass(kw_only=True)
class OcmMetadata:
    class Meta:
        name = "ocmMetadata"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    object_name: None | str = field(
        default=None,
        metadata={
            "name": "OBJECT_NAME",
            "type": "Element",
            "namespace": "",
        },
    )
    international_designator: None | str = field(
        default=None,
        metadata={
            "name": "INTERNATIONAL_DESIGNATOR",
            "type": "Element",
            "namespace": "",
        },
    )
    catalog_name: None | str = field(
        default=None,
        metadata={
            "name": "CATALOG_NAME",
            "type": "Element",
            "namespace": "",
        },
    )
    object_designator: None | str = field(
        default=None,
        metadata={
            "name": "OBJECT_DESIGNATOR",
            "type": "Element",
            "namespace": "",
        },
    )
    alternate_names: None | str = field(
        default=None,
        metadata={
            "name": "ALTERNATE_NAMES",
            "type": "Element",
            "namespace": "",
        },
    )
    originator_poc: None | str = field(
        default=None,
        metadata={
            "name": "ORIGINATOR_POC",
            "type": "Element",
            "namespace": "",
        },
    )
    originator_position: None | str = field(
        default=None,
        metadata={
            "name": "ORIGINATOR_POSITION",
            "type": "Element",
            "namespace": "",
        },
    )
    originator_phone: None | str = field(
        default=None,
        metadata={
            "name": "ORIGINATOR_PHONE",
            "type": "Element",
            "namespace": "",
        },
    )
    originator_email: None | str = field(
        default=None,
        metadata={
            "name": "ORIGINATOR_EMAIL",
            "type": "Element",
            "namespace": "",
        },
    )
    originator_address: None | str = field(
        default=None,
        metadata={
            "name": "ORIGINATOR_ADDRESS",
            "type": "Element",
            "namespace": "",
        },
    )
    tech_org: None | str = field(
        default=None,
        metadata={
            "name": "TECH_ORG",
            "type": "Element",
            "namespace": "",
        },
    )
    tech_poc: None | str = field(
        default=None,
        metadata={
            "name": "TECH_POC",
            "type": "Element",
            "namespace": "",
        },
    )
    tech_position: None | str = field(
        default=None,
        metadata={
            "name": "TECH_POSITION",
            "type": "Element",
            "namespace": "",
        },
    )
    tech_phone: None | str = field(
        default=None,
        metadata={
            "name": "TECH_PHONE",
            "type": "Element",
            "namespace": "",
        },
    )
    tech_email: None | str = field(
        default=None,
        metadata={
            "name": "TECH_EMAIL",
            "type": "Element",
            "namespace": "",
        },
    )
    tech_address: None | str = field(
        default=None,
        metadata={
            "name": "TECH_ADDRESS",
            "type": "Element",
            "namespace": "",
        },
    )
    previous_message_id: None | str = field(
        default=None,
        metadata={
            "name": "PREVIOUS_MESSAGE_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    next_message_id: None | str = field(
        default=None,
        metadata={
            "name": "NEXT_MESSAGE_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    adm_msg_link: None | str = field(
        default=None,
        metadata={
            "name": "ADM_MSG_LINK",
            "type": "Element",
            "namespace": "",
        },
    )
    cdm_msg_link: None | str = field(
        default=None,
        metadata={
            "name": "CDM_MSG_LINK",
            "type": "Element",
            "namespace": "",
        },
    )
    prm_msg_link: None | str = field(
        default=None,
        metadata={
            "name": "PRM_MSG_LINK",
            "type": "Element",
            "namespace": "",
        },
    )
    rdm_msg_link: None | str = field(
        default=None,
        metadata={
            "name": "RDM_MSG_LINK",
            "type": "Element",
            "namespace": "",
        },
    )
    tdm_msg_link: None | str = field(
        default=None,
        metadata={
            "name": "TDM_MSG_LINK",
            "type": "Element",
            "namespace": "",
        },
    )
    operator: None | str = field(
        default=None,
        metadata={
            "name": "OPERATOR",
            "type": "Element",
            "namespace": "",
        },
    )
    owner: None | str = field(
        default=None,
        metadata={
            "name": "OWNER",
            "type": "Element",
            "namespace": "",
        },
    )
    country: None | str = field(
        default=None,
        metadata={
            "name": "COUNTRY",
            "type": "Element",
            "namespace": "",
        },
    )
    constellation: None | str = field(
        default=None,
        metadata={
            "name": "CONSTELLATION",
            "type": "Element",
            "namespace": "",
        },
    )
    object_type: None | ObjectDescriptionType = field(
        default=None,
        metadata={
            "name": "OBJECT_TYPE",
            "type": "Element",
            "namespace": "",
        },
    )
    time_system: str = field(
        metadata={
            "name": "TIME_SYSTEM",
            "type": "Element",
            "namespace": "",
        }
    )
    epoch_tzero: str = field(
        metadata={
            "name": "EPOCH_TZERO",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    ops_status: None | str = field(
        default=None,
        metadata={
            "name": "OPS_STATUS",
            "type": "Element",
            "namespace": "",
        },
    )
    orbit_category: None | str = field(
        default=None,
        metadata={
            "name": "ORBIT_CATEGORY",
            "type": "Element",
            "namespace": "",
        },
    )
    ocm_data_elements: None | str = field(
        default=None,
        metadata={
            "name": "OCM_DATA_ELEMENTS",
            "type": "Element",
            "namespace": "",
        },
    )
    sclk_offset_at_epoch: None | TimeOffsetType = field(
        default=None,
        metadata={
            "name": "SCLK_OFFSET_AT_EPOCH",
            "type": "Element",
            "namespace": "",
        },
    )
    sclk_sec_per_si_sec: None | DurationType = field(
        default=None,
        metadata={
            "name": "SCLK_SEC_PER_SI_SEC",
            "type": "Element",
            "namespace": "",
        },
    )
    previous_message_epoch: None | str = field(
        default=None,
        metadata={
            "name": "PREVIOUS_MESSAGE_EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    next_message_epoch: None | str = field(
        default=None,
        metadata={
            "name": "NEXT_MESSAGE_EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    start_time: None | str = field(
        default=None,
        metadata={
            "name": "START_TIME",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    stop_time: None | str = field(
        default=None,
        metadata={
            "name": "STOP_TIME",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    time_span: None | DayIntervalTypeUo = field(
        default=None,
        metadata={
            "name": "TIME_SPAN",
            "type": "Element",
            "namespace": "",
        },
    )
    taimutc_at_tzero: None | TimeOffsetType = field(
        default=None,
        metadata={
            "name": "TAIMUTC_AT_TZERO",
            "type": "Element",
            "namespace": "",
        },
    )
    next_leap_epoch: None | str = field(
        default=None,
        metadata={
            "name": "NEXT_LEAP_EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    next_leap_taimutc: None | TimeOffsetType = field(
        default=None,
        metadata={
            "name": "NEXT_LEAP_TAIMUTC",
            "type": "Element",
            "namespace": "",
        },
    )
    ut1_mutc_at_tzero: None | TimeOffsetType = field(
        default=None,
        metadata={
            "name": "UT1MUTC_AT_TZERO",
            "type": "Element",
            "namespace": "",
        },
    )
    eop_source: None | str = field(
        default=None,
        metadata={
            "name": "EOP_SOURCE",
            "type": "Element",
            "namespace": "",
        },
    )
    interp_method_eop: None | str = field(
        default=None,
        metadata={
            "name": "INTERP_METHOD_EOP",
            "type": "Element",
            "namespace": "",
        },
    )
    celestial_source: None | str = field(
        default=None,
        metadata={
            "name": "CELESTIAL_SOURCE",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class OcmOdParametersType:
    class Meta:
        name = "ocmOdParametersType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    od_id: str = field(
        metadata={
            "name": "OD_ID",
            "type": "Element",
            "namespace": "",
        }
    )
    od_prev_id: None | str = field(
        default=None,
        metadata={
            "name": "OD_PREV_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    od_method: str = field(
        metadata={
            "name": "OD_METHOD",
            "type": "Element",
            "namespace": "",
        }
    )
    od_epoch: str = field(
        metadata={
            "name": "OD_EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    days_since_first_obs: None | DayIntervalTypeUo = field(
        default=None,
        metadata={
            "name": "DAYS_SINCE_FIRST_OBS",
            "type": "Element",
            "namespace": "",
        },
    )
    days_since_last_obs: None | DayIntervalTypeUo = field(
        default=None,
        metadata={
            "name": "DAYS_SINCE_LAST_OBS",
            "type": "Element",
            "namespace": "",
        },
    )
    recommended_od_span: None | DayIntervalTypeUo = field(
        default=None,
        metadata={
            "name": "RECOMMENDED_OD_SPAN",
            "type": "Element",
            "namespace": "",
        },
    )
    actual_od_span: None | DayIntervalTypeUo = field(
        default=None,
        metadata={
            "name": "ACTUAL_OD_SPAN",
            "type": "Element",
            "namespace": "",
        },
    )
    obs_available: None | int = field(
        default=None,
        metadata={
            "name": "OBS_AVAILABLE",
            "type": "Element",
            "namespace": "",
        },
    )
    obs_used: None | int = field(
        default=None,
        metadata={
            "name": "OBS_USED",
            "type": "Element",
            "namespace": "",
        },
    )
    tracks_available: None | int = field(
        default=None,
        metadata={
            "name": "TRACKS_AVAILABLE",
            "type": "Element",
            "namespace": "",
        },
    )
    tracks_used: None | int = field(
        default=None,
        metadata={
            "name": "TRACKS_USED",
            "type": "Element",
            "namespace": "",
        },
    )
    maximum_obs_gap: None | DayIntervalTypeUo = field(
        default=None,
        metadata={
            "name": "MAXIMUM_OBS_GAP",
            "type": "Element",
            "namespace": "",
        },
    )
    od_epoch_eigmaj: None | LengthTypeUo = field(
        default=None,
        metadata={
            "name": "OD_EPOCH_EIGMAJ",
            "type": "Element",
            "namespace": "",
        },
    )
    od_epoch_eigint: None | LengthTypeUo = field(
        default=None,
        metadata={
            "name": "OD_EPOCH_EIGINT",
            "type": "Element",
            "namespace": "",
        },
    )
    od_epoch_eigmin: None | LengthTypeUo = field(
        default=None,
        metadata={
            "name": "OD_EPOCH_EIGMIN",
            "type": "Element",
            "namespace": "",
        },
    )
    od_max_pred_eigmaj: None | LengthTypeUo = field(
        default=None,
        metadata={
            "name": "OD_MAX_PRED_EIGMAJ",
            "type": "Element",
            "namespace": "",
        },
    )
    od_min_pred_eigmin: None | LengthTypeUo = field(
        default=None,
        metadata={
            "name": "OD_MIN_PRED_EIGMIN",
            "type": "Element",
            "namespace": "",
        },
    )
    od_confidence: None | PercentageTypeUo = field(
        default=None,
        metadata={
            "name": "OD_CONFIDENCE",
            "type": "Element",
            "namespace": "",
        },
    )
    gdop: None | float = field(
        default=None,
        metadata={
            "name": "GDOP",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )
    solve_n: None | int = field(
        default=None,
        metadata={
            "name": "SOLVE_N",
            "type": "Element",
            "namespace": "",
        },
    )
    solve_states: None | str = field(
        default=None,
        metadata={
            "name": "SOLVE_STATES",
            "type": "Element",
            "namespace": "",
        },
    )
    consider_n: None | int = field(
        default=None,
        metadata={
            "name": "CONSIDER_N",
            "type": "Element",
            "namespace": "",
        },
    )
    consider_params: None | str = field(
        default=None,
        metadata={
            "name": "CONSIDER_PARAMS",
            "type": "Element",
            "namespace": "",
        },
    )
    sedr: None | WkgType = field(
        default=None,
        metadata={
            "name": "SEDR",
            "type": "Element",
            "namespace": "",
        },
    )
    sensors_n: None | int = field(
        default=None,
        metadata={
            "name": "SENSORS_N",
            "type": "Element",
            "namespace": "",
        },
    )
    sensors: None | str = field(
        default=None,
        metadata={
            "name": "SENSORS",
            "type": "Element",
            "namespace": "",
        },
    )
    weighted_rms: None | float = field(
        default=None,
        metadata={
            "name": "WEIGHTED_RMS",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )
    data_types: None | str = field(
        default=None,
        metadata={
            "name": "DATA_TYPES",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class OcmPerturbationsType:
    class Meta:
        name = "ocmPerturbationsType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    atmospheric_model: None | str = field(
        default=None,
        metadata={
            "name": "ATMOSPHERIC_MODEL",
            "type": "Element",
            "namespace": "",
        },
    )
    gravity_model: None | str = field(
        default=None,
        metadata={
            "name": "GRAVITY_MODEL",
            "type": "Element",
            "namespace": "",
        },
    )
    equatorial_radius: None | PositionTypeUo = field(
        default=None,
        metadata={
            "name": "EQUATORIAL_RADIUS",
            "type": "Element",
            "namespace": "",
        },
    )
    gm: None | GmType = field(
        default=None,
        metadata={
            "name": "GM",
            "type": "Element",
            "namespace": "",
        },
    )
    n_body_perturbations: None | str = field(
        default=None,
        metadata={
            "name": "N_BODY_PERTURBATIONS",
            "type": "Element",
            "namespace": "",
        },
    )
    central_body_rotation: None | AngleRateType = field(
        default=None,
        metadata={
            "name": "CENTRAL_BODY_ROTATION",
            "type": "Element",
            "namespace": "",
        },
    )
    oblate_flattening: None | float = field(
        default=None,
        metadata={
            "name": "OBLATE_FLATTENING",
            "type": "Element",
            "namespace": "",
            "min_exclusive": 0.0,
        },
    )
    ocean_tides_model: None | str = field(
        default=None,
        metadata={
            "name": "OCEAN_TIDES_MODEL",
            "type": "Element",
            "namespace": "",
        },
    )
    solid_tides_model: None | str = field(
        default=None,
        metadata={
            "name": "SOLID_TIDES_MODEL",
            "type": "Element",
            "namespace": "",
        },
    )
    reduction_theory: None | str = field(
        default=None,
        metadata={
            "name": "REDUCTION_THEORY",
            "type": "Element",
            "namespace": "",
        },
    )
    albedo_model: None | str = field(
        default=None,
        metadata={
            "name": "ALBEDO_MODEL",
            "type": "Element",
            "namespace": "",
        },
    )
    albedo_grid_size: None | int = field(
        default=None,
        metadata={
            "name": "ALBEDO_GRID_SIZE",
            "type": "Element",
            "namespace": "",
        },
    )
    shadow_model: None | str = field(
        default=None,
        metadata={
            "name": "SHADOW_MODEL",
            "type": "Element",
            "namespace": "",
        },
    )
    shadow_bodies: None | str = field(
        default=None,
        metadata={
            "name": "SHADOW_BODIES",
            "type": "Element",
            "namespace": "",
        },
    )
    srp_model: None | str = field(
        default=None,
        metadata={
            "name": "SRP_MODEL",
            "type": "Element",
            "namespace": "",
        },
    )
    sw_data_source: None | str = field(
        default=None,
        metadata={
            "name": "SW_DATA_SOURCE",
            "type": "Element",
            "namespace": "",
        },
    )
    sw_data_epoch: None | str = field(
        default=None,
        metadata={
            "name": "SW_DATA_EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    sw_interp_method: None | str = field(
        default=None,
        metadata={
            "name": "SW_INTERP_METHOD",
            "type": "Element",
            "namespace": "",
        },
    )
    fixed_geomag_kp: None | GeomagType = field(
        default=None,
        metadata={
            "name": "FIXED_GEOMAG_KP",
            "type": "Element",
            "namespace": "",
        },
    )
    fixed_geomag_ap: None | GeomagType = field(
        default=None,
        metadata={
            "name": "FIXED_GEOMAG_AP",
            "type": "Element",
            "namespace": "",
        },
    )
    fixed_geomag_dst: None | GeomagType = field(
        default=None,
        metadata={
            "name": "FIXED_GEOMAG_DST",
            "type": "Element",
            "namespace": "",
        },
    )
    fixed_f10_p7: None | SolarFluxType = field(
        default=None,
        metadata={
            "name": "FIXED_F10P7",
            "type": "Element",
            "namespace": "",
        },
    )
    fixed_f10_p7_mean: None | SolarFluxType = field(
        default=None,
        metadata={
            "name": "FIXED_F10P7_MEAN",
            "type": "Element",
            "namespace": "",
        },
    )
    fixed_m10_p7: None | SolarFluxType = field(
        default=None,
        metadata={
            "name": "FIXED_M10P7",
            "type": "Element",
            "namespace": "",
        },
    )
    fixed_m10_p7_mean: None | SolarFluxType = field(
        default=None,
        metadata={
            "name": "FIXED_M10P7_MEAN",
            "type": "Element",
            "namespace": "",
        },
    )
    fixed_s10_p7: None | SolarFluxType = field(
        default=None,
        metadata={
            "name": "FIXED_S10P7",
            "type": "Element",
            "namespace": "",
        },
    )
    fixed_s10_p7_mean: None | SolarFluxType = field(
        default=None,
        metadata={
            "name": "FIXED_S10P7_MEAN",
            "type": "Element",
            "namespace": "",
        },
    )
    fixed_y10_p7: None | SolarFluxType = field(
        default=None,
        metadata={
            "name": "FIXED_Y10P7",
            "type": "Element",
            "namespace": "",
        },
    )
    fixed_y10_p7_mean: None | SolarFluxType = field(
        default=None,
        metadata={
            "name": "FIXED_Y10P7_MEAN",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class OcmPhysicalDescriptionType:
    class Meta:
        name = "ocmPhysicalDescriptionType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    manufacturer: None | str = field(
        default=None,
        metadata={
            "name": "MANUFACTURER",
            "type": "Element",
            "namespace": "",
        },
    )
    bus_model: None | str = field(
        default=None,
        metadata={
            "name": "BUS_MODEL",
            "type": "Element",
            "namespace": "",
        },
    )
    docked_with: None | str = field(
        default=None,
        metadata={
            "name": "DOCKED_WITH",
            "type": "Element",
            "namespace": "",
        },
    )
    drag_const_area: None | AreaType = field(
        default=None,
        metadata={
            "name": "DRAG_CONST_AREA",
            "type": "Element",
            "namespace": "",
        },
    )
    drag_coeff_nom: None | float = field(
        default=None,
        metadata={
            "name": "DRAG_COEFF_NOM",
            "type": "Element",
            "namespace": "",
            "min_exclusive": 0.0,
        },
    )
    drag_uncertainty: None | PercentageTypeUo = field(
        default=None,
        metadata={
            "name": "DRAG_UNCERTAINTY",
            "type": "Element",
            "namespace": "",
        },
    )
    initial_wet_mass: None | MassType = field(
        default=None,
        metadata={
            "name": "INITIAL_WET_MASS",
            "type": "Element",
            "namespace": "",
        },
    )
    wet_mass: None | MassType = field(
        default=None,
        metadata={
            "name": "WET_MASS",
            "type": "Element",
            "namespace": "",
        },
    )
    dry_mass: None | MassType = field(
        default=None,
        metadata={
            "name": "DRY_MASS",
            "type": "Element",
            "namespace": "",
        },
    )
    oeb_parent_frame: None | str = field(
        default=None,
        metadata={
            "name": "OEB_PARENT_FRAME",
            "type": "Element",
            "namespace": "",
        },
    )
    oeb_parent_frame_epoch: None | str = field(
        default=None,
        metadata={
            "name": "OEB_PARENT_FRAME_EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    oeb_q1: None | float = field(
        default=None,
        metadata={
            "name": "OEB_Q1",
            "type": "Element",
            "namespace": "",
        },
    )
    oeb_q2: None | float = field(
        default=None,
        metadata={
            "name": "OEB_Q2",
            "type": "Element",
            "namespace": "",
        },
    )
    oeb_q3: None | float = field(
        default=None,
        metadata={
            "name": "OEB_Q3",
            "type": "Element",
            "namespace": "",
        },
    )
    oeb_qc: None | float = field(
        default=None,
        metadata={
            "name": "OEB_QC",
            "type": "Element",
            "namespace": "",
        },
    )
    oeb_max: None | LengthTypeUo = field(
        default=None,
        metadata={
            "name": "OEB_MAX",
            "type": "Element",
            "namespace": "",
        },
    )
    oeb_int: None | LengthTypeUo = field(
        default=None,
        metadata={
            "name": "OEB_INT",
            "type": "Element",
            "namespace": "",
        },
    )
    oeb_min: None | LengthTypeUo = field(
        default=None,
        metadata={
            "name": "OEB_MIN",
            "type": "Element",
            "namespace": "",
        },
    )
    area_along_oeb_max: None | AreaType = field(
        default=None,
        metadata={
            "name": "AREA_ALONG_OEB_MAX",
            "type": "Element",
            "namespace": "",
        },
    )
    area_along_oeb_int: None | AreaType = field(
        default=None,
        metadata={
            "name": "AREA_ALONG_OEB_INT",
            "type": "Element",
            "namespace": "",
        },
    )
    area_along_oeb_min: None | AreaType = field(
        default=None,
        metadata={
            "name": "AREA_ALONG_OEB_MIN",
            "type": "Element",
            "namespace": "",
        },
    )
    area_min_for_pc: None | AreaType = field(
        default=None,
        metadata={
            "name": "AREA_MIN_FOR_PC",
            "type": "Element",
            "namespace": "",
        },
    )
    area_max_for_pc: None | AreaType = field(
        default=None,
        metadata={
            "name": "AREA_MAX_FOR_PC",
            "type": "Element",
            "namespace": "",
        },
    )
    area_typ_for_pc: None | AreaType = field(
        default=None,
        metadata={
            "name": "AREA_TYP_FOR_PC",
            "type": "Element",
            "namespace": "",
        },
    )
    rcs: None | AreaType = field(
        default=None,
        metadata={
            "name": "RCS",
            "type": "Element",
            "namespace": "",
        },
    )
    rcs_min: None | AreaType = field(
        default=None,
        metadata={
            "name": "RCS_MIN",
            "type": "Element",
            "namespace": "",
        },
    )
    rcs_max: None | AreaType = field(
        default=None,
        metadata={
            "name": "RCS_MAX",
            "type": "Element",
            "namespace": "",
        },
    )
    srp_const_area: None | AreaType = field(
        default=None,
        metadata={
            "name": "SRP_CONST_AREA",
            "type": "Element",
            "namespace": "",
        },
    )
    solar_rad_coeff: None | float = field(
        default=None,
        metadata={
            "name": "SOLAR_RAD_COEFF",
            "type": "Element",
            "namespace": "",
        },
    )
    solar_rad_uncertainty: None | PercentageTypeUo = field(
        default=None,
        metadata={
            "name": "SOLAR_RAD_UNCERTAINTY",
            "type": "Element",
            "namespace": "",
        },
    )
    vm_absolute: None | float = field(
        default=None,
        metadata={
            "name": "VM_ABSOLUTE",
            "type": "Element",
            "namespace": "",
        },
    )
    vm_apparent_min: None | float = field(
        default=None,
        metadata={
            "name": "VM_APPARENT_MIN",
            "type": "Element",
            "namespace": "",
        },
    )
    vm_apparent: None | float = field(
        default=None,
        metadata={
            "name": "VM_APPARENT",
            "type": "Element",
            "namespace": "",
        },
    )
    vm_apparent_max: None | float = field(
        default=None,
        metadata={
            "name": "VM_APPARENT_MAX",
            "type": "Element",
            "namespace": "",
        },
    )
    reflectance: None | float = field(
        default=None,
        metadata={
            "name": "REFLECTANCE",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
            "max_inclusive": 1.0,
        },
    )
    att_control_mode: None | str = field(
        default=None,
        metadata={
            "name": "ATT_CONTROL_MODE",
            "type": "Element",
            "namespace": "",
        },
    )
    att_actuator_type: None | str = field(
        default=None,
        metadata={
            "name": "ATT_ACTUATOR_TYPE",
            "type": "Element",
            "namespace": "",
        },
    )
    att_knowledge: None | AngleType = field(
        default=None,
        metadata={
            "name": "ATT_KNOWLEDGE",
            "type": "Element",
            "namespace": "",
        },
    )
    att_control: None | AngleType = field(
        default=None,
        metadata={
            "name": "ATT_CONTROL",
            "type": "Element",
            "namespace": "",
        },
    )
    att_pointing: None | AngleType = field(
        default=None,
        metadata={
            "name": "ATT_POINTING",
            "type": "Element",
            "namespace": "",
        },
    )
    avg_maneuver_freq: None | ManeuverFreqType = field(
        default=None,
        metadata={
            "name": "AVG_MANEUVER_FREQ",
            "type": "Element",
            "namespace": "",
        },
    )
    max_thrust: None | ThrustType = field(
        default=None,
        metadata={
            "name": "MAX_THRUST",
            "type": "Element",
            "namespace": "",
        },
    )
    dv_bol: None | VelocityTypeUo = field(
        default=None,
        metadata={
            "name": "DV_BOL",
            "type": "Element",
            "namespace": "",
        },
    )
    dv_remaining: None | VelocityTypeUo = field(
        default=None,
        metadata={
            "name": "DV_REMAINING",
            "type": "Element",
            "namespace": "",
        },
    )
    ixx: None | MomentType = field(
        default=None,
        metadata={
            "name": "IXX",
            "type": "Element",
            "namespace": "",
        },
    )
    iyy: None | MomentType = field(
        default=None,
        metadata={
            "name": "IYY",
            "type": "Element",
            "namespace": "",
        },
    )
    izz: None | MomentType = field(
        default=None,
        metadata={
            "name": "IZZ",
            "type": "Element",
            "namespace": "",
        },
    )
    ixy: None | MomentType = field(
        default=None,
        metadata={
            "name": "IXY",
            "type": "Element",
            "namespace": "",
        },
    )
    ixz: None | MomentType = field(
        default=None,
        metadata={
            "name": "IXZ",
            "type": "Element",
            "namespace": "",
        },
    )
    iyz: None | MomentType = field(
        default=None,
        metadata={
            "name": "IYZ",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class OdParametersType:
    class Meta:
        name = "odParametersType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    time_lastob_start: None | str = field(
        default=None,
        metadata={
            "name": "TIME_LASTOB_START",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    time_lastob_end: None | str = field(
        default=None,
        metadata={
            "name": "TIME_LASTOB_END",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    recommended_od_span: None | DayIntervalTypeUo = field(
        default=None,
        metadata={
            "name": "RECOMMENDED_OD_SPAN",
            "type": "Element",
            "namespace": "",
        },
    )
    actual_od_span: None | DayIntervalTypeUo = field(
        default=None,
        metadata={
            "name": "ACTUAL_OD_SPAN",
            "type": "Element",
            "namespace": "",
        },
    )
    obs_available: None | int = field(
        default=None,
        metadata={
            "name": "OBS_AVAILABLE",
            "type": "Element",
            "namespace": "",
        },
    )
    obs_used: None | int = field(
        default=None,
        metadata={
            "name": "OBS_USED",
            "type": "Element",
            "namespace": "",
        },
    )
    tracks_available: None | int = field(
        default=None,
        metadata={
            "name": "TRACKS_AVAILABLE",
            "type": "Element",
            "namespace": "",
        },
    )
    tracks_used: None | int = field(
        default=None,
        metadata={
            "name": "TRACKS_USED",
            "type": "Element",
            "namespace": "",
        },
    )
    residuals_accepted: None | PercentageTypeUo = field(
        default=None,
        metadata={
            "name": "RESIDUALS_ACCEPTED",
            "type": "Element",
            "namespace": "",
        },
    )
    weighted_rms: None | float = field(
        default=None,
        metadata={
            "name": "WEIGHTED_RMS",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )


@dataclass(kw_only=True)
class OemCovarianceMatrixType(OemCovarianceMatrixAbstractType):
    class Meta:
        name = "oemCovarianceMatrixType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    cx_x: PositionCovarianceType = field(
        metadata={
            "name": "CX_X",
            "type": "Element",
            "namespace": "",
        }
    )
    cy_x: PositionCovarianceType = field(
        metadata={
            "name": "CY_X",
            "type": "Element",
            "namespace": "",
        }
    )
    cy_y: PositionCovarianceType = field(
        metadata={
            "name": "CY_Y",
            "type": "Element",
            "namespace": "",
        }
    )
    cz_x: PositionCovarianceType = field(
        metadata={
            "name": "CZ_X",
            "type": "Element",
            "namespace": "",
        }
    )
    cz_y: PositionCovarianceType = field(
        metadata={
            "name": "CZ_Y",
            "type": "Element",
            "namespace": "",
        }
    )
    cz_z: PositionCovarianceType = field(
        metadata={
            "name": "CZ_Z",
            "type": "Element",
            "namespace": "",
        }
    )
    cx_dot_x: PositionVelocityCovarianceType = field(
        metadata={
            "name": "CX_DOT_X",
            "type": "Element",
            "namespace": "",
        }
    )
    cx_dot_y: PositionVelocityCovarianceType = field(
        metadata={
            "name": "CX_DOT_Y",
            "type": "Element",
            "namespace": "",
        }
    )
    cx_dot_z: PositionVelocityCovarianceType = field(
        metadata={
            "name": "CX_DOT_Z",
            "type": "Element",
            "namespace": "",
        }
    )
    cx_dot_x_dot: VelocityCovarianceType = field(
        metadata={
            "name": "CX_DOT_X_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    cy_dot_x: PositionVelocityCovarianceType = field(
        metadata={
            "name": "CY_DOT_X",
            "type": "Element",
            "namespace": "",
        }
    )
    cy_dot_y: PositionVelocityCovarianceType = field(
        metadata={
            "name": "CY_DOT_Y",
            "type": "Element",
            "namespace": "",
        }
    )
    cy_dot_z: PositionVelocityCovarianceType = field(
        metadata={
            "name": "CY_DOT_Z",
            "type": "Element",
            "namespace": "",
        }
    )
    cy_dot_x_dot: VelocityCovarianceType = field(
        metadata={
            "name": "CY_DOT_X_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    cy_dot_y_dot: VelocityCovarianceType = field(
        metadata={
            "name": "CY_DOT_Y_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    cz_dot_x: PositionVelocityCovarianceType = field(
        metadata={
            "name": "CZ_DOT_X",
            "type": "Element",
            "namespace": "",
        }
    )
    cz_dot_y: PositionVelocityCovarianceType = field(
        metadata={
            "name": "CZ_DOT_Y",
            "type": "Element",
            "namespace": "",
        }
    )
    cz_dot_z: PositionVelocityCovarianceType = field(
        metadata={
            "name": "CZ_DOT_Z",
            "type": "Element",
            "namespace": "",
        }
    )
    cz_dot_x_dot: VelocityCovarianceType = field(
        metadata={
            "name": "CZ_DOT_X_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    cz_dot_y_dot: VelocityCovarianceType = field(
        metadata={
            "name": "CZ_DOT_Y_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    cz_dot_z_dot: VelocityCovarianceType = field(
        metadata={
            "name": "CZ_DOT_Z_DOT",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class OpmCovarianceMatrixType(OpmCovarianceMatrixAbstractType):
    class Meta:
        name = "opmCovarianceMatrixType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    cx_x: PositionCovarianceType = field(
        metadata={
            "name": "CX_X",
            "type": "Element",
            "namespace": "",
        }
    )
    cy_x: PositionCovarianceType = field(
        metadata={
            "name": "CY_X",
            "type": "Element",
            "namespace": "",
        }
    )
    cy_y: PositionCovarianceType = field(
        metadata={
            "name": "CY_Y",
            "type": "Element",
            "namespace": "",
        }
    )
    cz_x: PositionCovarianceType = field(
        metadata={
            "name": "CZ_X",
            "type": "Element",
            "namespace": "",
        }
    )
    cz_y: PositionCovarianceType = field(
        metadata={
            "name": "CZ_Y",
            "type": "Element",
            "namespace": "",
        }
    )
    cz_z: PositionCovarianceType = field(
        metadata={
            "name": "CZ_Z",
            "type": "Element",
            "namespace": "",
        }
    )
    cx_dot_x: PositionVelocityCovarianceType = field(
        metadata={
            "name": "CX_DOT_X",
            "type": "Element",
            "namespace": "",
        }
    )
    cx_dot_y: PositionVelocityCovarianceType = field(
        metadata={
            "name": "CX_DOT_Y",
            "type": "Element",
            "namespace": "",
        }
    )
    cx_dot_z: PositionVelocityCovarianceType = field(
        metadata={
            "name": "CX_DOT_Z",
            "type": "Element",
            "namespace": "",
        }
    )
    cx_dot_x_dot: VelocityCovarianceType = field(
        metadata={
            "name": "CX_DOT_X_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    cy_dot_x: PositionVelocityCovarianceType = field(
        metadata={
            "name": "CY_DOT_X",
            "type": "Element",
            "namespace": "",
        }
    )
    cy_dot_y: PositionVelocityCovarianceType = field(
        metadata={
            "name": "CY_DOT_Y",
            "type": "Element",
            "namespace": "",
        }
    )
    cy_dot_z: PositionVelocityCovarianceType = field(
        metadata={
            "name": "CY_DOT_Z",
            "type": "Element",
            "namespace": "",
        }
    )
    cy_dot_x_dot: VelocityCovarianceType = field(
        metadata={
            "name": "CY_DOT_X_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    cy_dot_y_dot: VelocityCovarianceType = field(
        metadata={
            "name": "CY_DOT_Y_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    cz_dot_x: PositionVelocityCovarianceType = field(
        metadata={
            "name": "CZ_DOT_X",
            "type": "Element",
            "namespace": "",
        }
    )
    cz_dot_y: PositionVelocityCovarianceType = field(
        metadata={
            "name": "CZ_DOT_Y",
            "type": "Element",
            "namespace": "",
        }
    )
    cz_dot_z: PositionVelocityCovarianceType = field(
        metadata={
            "name": "CZ_DOT_Z",
            "type": "Element",
            "namespace": "",
        }
    )
    cz_dot_x_dot: VelocityCovarianceType = field(
        metadata={
            "name": "CZ_DOT_X_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    cz_dot_y_dot: VelocityCovarianceType = field(
        metadata={
            "name": "CZ_DOT_Y_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    cz_dot_z_dot: VelocityCovarianceType = field(
        metadata={
            "name": "CZ_DOT_Z_DOT",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class QuaternionDotType:
    class Meta:
        name = "quaternionDotType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    q1_dot: QuaternionDotComponentType = field(
        metadata={
            "name": "Q1_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    q2_dot: QuaternionDotComponentType = field(
        metadata={
            "name": "Q2_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    q3_dot: QuaternionDotComponentType = field(
        metadata={
            "name": "Q3_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    qc_dot: QuaternionDotComponentType = field(
        metadata={
            "name": "QC_DOT",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class RdmMetadata:
    class Meta:
        name = "rdmMetadata"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    object_name: str = field(
        metadata={
            "name": "OBJECT_NAME",
            "type": "Element",
            "namespace": "",
        }
    )
    international_designator: str = field(
        metadata={
            "name": "INTERNATIONAL_DESIGNATOR",
            "type": "Element",
            "namespace": "",
        }
    )
    catalog_name: None | str = field(
        default=None,
        metadata={
            "name": "CATALOG_NAME",
            "type": "Element",
            "namespace": "",
        },
    )
    object_designator: None | str = field(
        default=None,
        metadata={
            "name": "OBJECT_DESIGNATOR",
            "type": "Element",
            "namespace": "",
        },
    )
    object_type: None | ObjectDescriptionType = field(
        default=None,
        metadata={
            "name": "OBJECT_TYPE",
            "type": "Element",
            "namespace": "",
        },
    )
    object_owner: None | str = field(
        default=None,
        metadata={
            "name": "OBJECT_OWNER",
            "type": "Element",
            "namespace": "",
        },
    )
    object_operator: None | str = field(
        default=None,
        metadata={
            "name": "OBJECT_OPERATOR",
            "type": "Element",
            "namespace": "",
        },
    )
    controlled_reentry: ControlledType = field(
        metadata={
            "name": "CONTROLLED_REENTRY",
            "type": "Element",
            "namespace": "",
        }
    )
    center_name: str = field(
        metadata={
            "name": "CENTER_NAME",
            "type": "Element",
            "namespace": "",
        }
    )
    time_system: str = field(
        metadata={
            "name": "TIME_SYSTEM",
            "type": "Element",
            "namespace": "",
        }
    )
    epoch_tzero: str = field(
        metadata={
            "name": "EPOCH_TZERO",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    ref_frame: None | str = field(
        default=None,
        metadata={
            "name": "REF_FRAME",
            "type": "Element",
            "namespace": "",
        },
    )
    ref_frame_epoch: None | str = field(
        default=None,
        metadata={
            "name": "REF_FRAME_EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    ephemeris_name: None | str = field(
        default=None,
        metadata={
            "name": "EPHEMERIS_NAME",
            "type": "Element",
            "namespace": "",
        },
    )
    gravity_model: None | str = field(
        default=None,
        metadata={
            "name": "GRAVITY_MODEL",
            "type": "Element",
            "namespace": "",
        },
    )
    atmospheric_model: None | str = field(
        default=None,
        metadata={
            "name": "ATMOSPHERIC_MODEL",
            "type": "Element",
            "namespace": "",
        },
    )
    solar_flux_prediction: None | str = field(
        default=None,
        metadata={
            "name": "SOLAR_FLUX_PREDICTION",
            "type": "Element",
            "namespace": "",
        },
    )
    n_body_perturbations: None | str = field(
        default=None,
        metadata={
            "name": "N_BODY_PERTURBATIONS",
            "type": "Element",
            "namespace": "",
        },
    )
    solar_rad_pressure: None | str = field(
        default=None,
        metadata={
            "name": "SOLAR_RAD_PRESSURE",
            "type": "Element",
            "namespace": "",
        },
    )
    earth_tides: None | str = field(
        default=None,
        metadata={
            "name": "EARTH_TIDES",
            "type": "Element",
            "namespace": "",
        },
    )
    intrack_thrust: None | YesNoType = field(
        default=None,
        metadata={
            "name": "INTRACK_THRUST",
            "type": "Element",
            "namespace": "",
        },
    )
    drag_parameters_source: None | str = field(
        default=None,
        metadata={
            "name": "DRAG_PARAMETERS_SOURCE",
            "type": "Element",
            "namespace": "",
        },
    )
    drag_parameters_altitude: None | DistanceType = field(
        default=None,
        metadata={
            "name": "DRAG_PARAMETERS_ALTITUDE",
            "type": "Element",
            "namespace": "",
        },
    )
    reentry_uncertainty_method: None | ReentryUncertaintyMethodType = field(
        default=None,
        metadata={
            "name": "REENTRY_UNCERTAINTY_METHOD",
            "type": "Element",
            "namespace": "",
        },
    )
    reentry_disintegration: None | DisintegrationType = field(
        default=None,
        metadata={
            "name": "REENTRY_DISINTEGRATION",
            "type": "Element",
            "namespace": "",
        },
    )
    impact_uncertainty_method: None | ImpactUncertaintyType = field(
        default=None,
        metadata={
            "name": "IMPACT_UNCERTAINTY_METHOD",
            "type": "Element",
            "namespace": "",
        },
    )
    previous_message_id: None | str = field(
        default=None,
        metadata={
            "name": "PREVIOUS_MESSAGE_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    previous_message_epoch: None | str = field(
        default=None,
        metadata={
            "name": "PREVIOUS_MESSAGE_EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    next_message_epoch: None | str = field(
        default=None,
        metadata={
            "name": "NEXT_MESSAGE_EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )


@dataclass(kw_only=True)
class RdmSpacecraftParametersType:
    class Meta:
        name = "rdmSpacecraftParametersType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    wet_mass: None | MassType = field(
        default=None,
        metadata={
            "name": "WET_MASS",
            "type": "Element",
            "namespace": "",
        },
    )
    dry_mass: None | MassType = field(
        default=None,
        metadata={
            "name": "DRY_MASS",
            "type": "Element",
            "namespace": "",
        },
    )
    hazardous_substances: None | str = field(
        default=None,
        metadata={
            "name": "HAZARDOUS_SUBSTANCES",
            "type": "Element",
            "namespace": "",
        },
    )
    solar_rad_area: None | AreaType = field(
        default=None,
        metadata={
            "name": "SOLAR_RAD_AREA",
            "type": "Element",
            "namespace": "",
        },
    )
    solar_rad_coeff: None | float = field(
        default=None,
        metadata={
            "name": "SOLAR_RAD_COEFF",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )
    drag_area: None | AreaType = field(
        default=None,
        metadata={
            "name": "DRAG_AREA",
            "type": "Element",
            "namespace": "",
        },
    )
    drag_coeff: None | float = field(
        default=None,
        metadata={
            "name": "DRAG_COEFF",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )
    rcs: None | AreaType = field(
        default=None,
        metadata={
            "name": "RCS",
            "type": "Element",
            "namespace": "",
        },
    )
    ballistic_coeff: None | BallisticCoeffType = field(
        default=None,
        metadata={
            "name": "BALLISTIC_COEFF",
            "type": "Element",
            "namespace": "",
        },
    )
    thrust_acceleration: None | Ms2Type = field(
        default=None,
        metadata={
            "name": "THRUST_ACCELERATION",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class RelativeStateVectorType:
    class Meta:
        name = "relativeStateVectorType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    relative_position_r: LengthTypeUo = field(
        metadata={
            "name": "RELATIVE_POSITION_R",
            "type": "Element",
            "namespace": "",
        }
    )
    relative_position_t: LengthTypeUo = field(
        metadata={
            "name": "RELATIVE_POSITION_T",
            "type": "Element",
            "namespace": "",
        }
    )
    relative_position_n: LengthTypeUo = field(
        metadata={
            "name": "RELATIVE_POSITION_N",
            "type": "Element",
            "namespace": "",
        }
    )
    relative_velocity_r: DvType = field(
        metadata={
            "name": "RELATIVE_VELOCITY_R",
            "type": "Element",
            "namespace": "",
        }
    )
    relative_velocity_t: DvType = field(
        metadata={
            "name": "RELATIVE_VELOCITY_T",
            "type": "Element",
            "namespace": "",
        }
    )
    relative_velocity_n: DvType = field(
        metadata={
            "name": "RELATIVE_VELOCITY_N",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class SensorDataType:
    class Meta:
        name = "sensorDataType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    sensor_number: None | int = field(
        default=None,
        metadata={
            "name": "SENSOR_NUMBER",
            "type": "Element",
            "namespace": "",
        },
    )
    sensor_used: None | str = field(
        default=None,
        metadata={
            "name": "SENSOR_USED",
            "type": "Element",
            "namespace": "",
        },
    )
    number_sensor_noise_covariance: None | int = field(
        default=None,
        metadata={
            "name": "NUMBER_SENSOR_NOISE_COVARIANCE",
            "type": "Element",
            "namespace": "",
        },
    )
    sensor_noise_stddev: None | SensorNoiseType = field(
        default=None,
        metadata={
            "name": "SENSOR_NOISE_STDDEV",
            "type": "Element",
            "namespace": "",
        },
    )
    sensor_frequency: None | FrequencyType = field(
        default=None,
        metadata={
            "name": "SENSOR_FREQUENCY",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class SpacecraftParametersType:
    class Meta:
        name = "spacecraftParametersType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    mass: None | MassType = field(
        default=None,
        metadata={
            "name": "MASS",
            "type": "Element",
            "namespace": "",
        },
    )
    solar_rad_area: None | AreaType = field(
        default=None,
        metadata={
            "name": "SOLAR_RAD_AREA",
            "type": "Element",
            "namespace": "",
        },
    )
    solar_rad_coeff: None | float = field(
        default=None,
        metadata={
            "name": "SOLAR_RAD_COEFF",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )
    drag_area: None | AreaType = field(
        default=None,
        metadata={
            "name": "DRAG_AREA",
            "type": "Element",
            "namespace": "",
        },
    )
    drag_coeff: None | float = field(
        default=None,
        metadata={
            "name": "DRAG_COEFF",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )


@dataclass(kw_only=True)
class SpinNutationMomType:
    class Meta:
        name = "spinNutationMomType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    epoch: str = field(
        metadata={
            "name": "EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    spin_alpha: AngleType = field(
        metadata={
            "name": "SPIN_ALPHA",
            "type": "Element",
            "namespace": "",
        }
    )
    spin_delta: AngleType = field(
        metadata={
            "name": "SPIN_DELTA",
            "type": "Element",
            "namespace": "",
        }
    )
    spin_angle: AngleType = field(
        metadata={
            "name": "SPIN_ANGLE",
            "type": "Element",
            "namespace": "",
        }
    )
    spin_angle_vel: AngleRateType = field(
        metadata={
            "name": "SPIN_ANGLE_VEL",
            "type": "Element",
            "namespace": "",
        }
    )
    momentum_alpha: AngleType = field(
        metadata={
            "name": "MOMENTUM_ALPHA",
            "type": "Element",
            "namespace": "",
        }
    )
    momentum_delta: AngleType = field(
        metadata={
            "name": "MOMENTUM_DELTA",
            "type": "Element",
            "namespace": "",
        }
    )
    nutation_vel: AngleRateType = field(
        metadata={
            "name": "NUTATION_VEL",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class SpinNutationType:
    class Meta:
        name = "spinNutationType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    epoch: str = field(
        metadata={
            "name": "EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    spin_alpha: AngleType = field(
        metadata={
            "name": "SPIN_ALPHA",
            "type": "Element",
            "namespace": "",
        }
    )
    spin_delta: AngleType = field(
        metadata={
            "name": "SPIN_DELTA",
            "type": "Element",
            "namespace": "",
        }
    )
    spin_angle: AngleType = field(
        metadata={
            "name": "SPIN_ANGLE",
            "type": "Element",
            "namespace": "",
        }
    )
    spin_angle_vel: AngleRateType = field(
        metadata={
            "name": "SPIN_ANGLE_VEL",
            "type": "Element",
            "namespace": "",
        }
    )
    nutation: AngleType = field(
        metadata={
            "name": "NUTATION",
            "type": "Element",
            "namespace": "",
        }
    )
    nutation_per: DurationType = field(
        metadata={
            "name": "NUTATION_PER",
            "type": "Element",
            "namespace": "",
        }
    )
    nutation_phase: AngleType = field(
        metadata={
            "name": "NUTATION_PHASE",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class SpinStateType:
    class Meta:
        name = "spinStateType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    ref_frame_a: str = field(
        metadata={
            "name": "REF_FRAME_A",
            "type": "Element",
            "namespace": "",
        }
    )
    ref_frame_b: str = field(
        metadata={
            "name": "REF_FRAME_B",
            "type": "Element",
            "namespace": "",
        }
    )
    spin_alpha: AngleType = field(
        metadata={
            "name": "SPIN_ALPHA",
            "type": "Element",
            "namespace": "",
        }
    )
    spin_delta: AngleType = field(
        metadata={
            "name": "SPIN_DELTA",
            "type": "Element",
            "namespace": "",
        }
    )
    spin_angle: AngleType = field(
        metadata={
            "name": "SPIN_ANGLE",
            "type": "Element",
            "namespace": "",
        }
    )
    spin_angle_vel: AngleRateType = field(
        metadata={
            "name": "SPIN_ANGLE_VEL",
            "type": "Element",
            "namespace": "",
        }
    )
    nutation: None | AngleType = field(
        default=None,
        metadata={
            "name": "NUTATION",
            "type": "Element",
            "namespace": "",
        },
    )
    nutation_per: None | DurationType = field(
        default=None,
        metadata={
            "name": "NUTATION_PER",
            "type": "Element",
            "namespace": "",
        },
    )
    nutation_phase: None | AngleType = field(
        default=None,
        metadata={
            "name": "NUTATION_PHASE",
            "type": "Element",
            "namespace": "",
        },
    )
    momentum_alpha: None | AngleType = field(
        default=None,
        metadata={
            "name": "MOMENTUM_ALPHA",
            "type": "Element",
            "namespace": "",
        },
    )
    momentum_delta: None | AngleType = field(
        default=None,
        metadata={
            "name": "MOMENTUM_DELTA",
            "type": "Element",
            "namespace": "",
        },
    )
    nutation_vel: None | AngleRateType = field(
        default=None,
        metadata={
            "name": "NUTATION_VEL",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class SpinType:
    class Meta:
        name = "spinType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    epoch: str = field(
        metadata={
            "name": "EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    spin_alpha: AngleType = field(
        metadata={
            "name": "SPIN_ALPHA",
            "type": "Element",
            "namespace": "",
        }
    )
    spin_delta: AngleType = field(
        metadata={
            "name": "SPIN_DELTA",
            "type": "Element",
            "namespace": "",
        }
    )
    spin_angle: AngleType = field(
        metadata={
            "name": "SPIN_ANGLE",
            "type": "Element",
            "namespace": "",
        }
    )
    spin_angle_vel: AngleRateType = field(
        metadata={
            "name": "SPIN_ANGLE_VEL",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class StateVectorAccType:
    class Meta:
        name = "stateVectorAccType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    epoch: str = field(
        metadata={
            "name": "EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    x: PositionTypeUo = field(
        metadata={
            "name": "X",
            "type": "Element",
            "namespace": "",
        }
    )
    y: PositionTypeUo = field(
        metadata={
            "name": "Y",
            "type": "Element",
            "namespace": "",
        }
    )
    z: PositionTypeUo = field(
        metadata={
            "name": "Z",
            "type": "Element",
            "namespace": "",
        }
    )
    x_dot: VelocityTypeUo = field(
        metadata={
            "name": "X_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    y_dot: VelocityTypeUo = field(
        metadata={
            "name": "Y_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    z_dot: VelocityTypeUo = field(
        metadata={
            "name": "Z_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    x_ddot: None | AccType = field(
        default=None,
        metadata={
            "name": "X_DDOT",
            "type": "Element",
            "namespace": "",
        },
    )
    y_ddot: None | AccType = field(
        default=None,
        metadata={
            "name": "Y_DDOT",
            "type": "Element",
            "namespace": "",
        },
    )
    z_ddot: None | AccType = field(
        default=None,
        metadata={
            "name": "Z_DDOT",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class StateVectorType:
    class Meta:
        name = "stateVectorType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    epoch: str = field(
        metadata={
            "name": "EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    x: PositionTypeUo = field(
        metadata={
            "name": "X",
            "type": "Element",
            "namespace": "",
        }
    )
    y: PositionTypeUo = field(
        metadata={
            "name": "Y",
            "type": "Element",
            "namespace": "",
        }
    )
    z: PositionTypeUo = field(
        metadata={
            "name": "Z",
            "type": "Element",
            "namespace": "",
        }
    )
    x_dot: VelocityTypeUo = field(
        metadata={
            "name": "X_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    y_dot: VelocityTypeUo = field(
        metadata={
            "name": "Y_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    z_dot: VelocityTypeUo = field(
        metadata={
            "name": "Z_DOT",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class TleParametersType:
    class Meta:
        name = "tleParametersType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    ephemeris_type: None | int = field(
        default=None,
        metadata={
            "name": "EPHEMERIS_TYPE",
            "type": "Element",
            "namespace": "",
        },
    )
    classification_type: None | str = field(
        default=None,
        metadata={
            "name": "CLASSIFICATION_TYPE",
            "type": "Element",
            "namespace": "",
        },
    )
    norad_cat_id: None | int = field(
        default=None,
        metadata={
            "name": "NORAD_CAT_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    element_set_no: None | int = field(
        default=None,
        metadata={
            "name": "ELEMENT_SET_NO",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0,
            "max_inclusive": 9999,
        },
    )
    rev_at_epoch: None | int = field(
        default=None,
        metadata={
            "name": "REV_AT_EPOCH",
            "type": "Element",
            "namespace": "",
        },
    )
    bstar: None | BStarType = field(
        default=None,
        metadata={
            "name": "BSTAR",
            "type": "Element",
            "namespace": "",
        },
    )
    bterm: None | BTermType = field(
        default=None,
        metadata={
            "name": "BTERM",
            "type": "Element",
            "namespace": "",
        },
    )
    mean_motion_dot: DRevType = field(
        metadata={
            "name": "MEAN_MOTION_DOT",
            "type": "Element",
            "namespace": "",
        }
    )
    mean_motion_ddot: None | DdRevType = field(
        default=None,
        metadata={
            "name": "MEAN_MOTION_DDOT",
            "type": "Element",
            "namespace": "",
        },
    )
    agom: None | AgomType = field(
        default=None,
        metadata={
            "name": "AGOM",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class TrackingDataObservationType:
    class Meta:
        name = "trackingDataObservationType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    epoch: str = field(
        metadata={
            "name": "EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    angle_1: None | AngleType = field(
        default=None,
        metadata={
            "name": "ANGLE_1",
            "type": "Element",
            "namespace": "",
        },
    )
    angle_2: None | AngleType = field(
        default=None,
        metadata={
            "name": "ANGLE_2",
            "type": "Element",
            "namespace": "",
        },
    )
    carrier_power: None | float = field(
        default=None,
        metadata={
            "name": "CARRIER_POWER",
            "type": "Element",
            "namespace": "",
        },
    )
    clock_bias: None | float = field(
        default=None,
        metadata={
            "name": "CLOCK_BIAS",
            "type": "Element",
            "namespace": "",
        },
    )
    clock_drift: None | float = field(
        default=None,
        metadata={
            "name": "CLOCK_DRIFT",
            "type": "Element",
            "namespace": "",
        },
    )
    doppler_count: None | float = field(
        default=None,
        metadata={
            "name": "DOPPLER_COUNT",
            "type": "Element",
            "namespace": "",
        },
    )
    doppler_instantaneous: None | float = field(
        default=None,
        metadata={
            "name": "DOPPLER_INSTANTANEOUS",
            "type": "Element",
            "namespace": "",
        },
    )
    doppler_integrated: None | float = field(
        default=None,
        metadata={
            "name": "DOPPLER_INTEGRATED",
            "type": "Element",
            "namespace": "",
        },
    )
    dor: None | float = field(
        default=None,
        metadata={
            "name": "DOR",
            "type": "Element",
            "namespace": "",
        },
    )
    mag: None | float = field(
        default=None,
        metadata={
            "name": "MAG",
            "type": "Element",
            "namespace": "",
        },
    )
    pc_n0: None | float = field(
        default=None,
        metadata={
            "name": "PC_N0",
            "type": "Element",
            "namespace": "",
        },
    )
    pr_n0: None | float = field(
        default=None,
        metadata={
            "name": "PR_N0",
            "type": "Element",
            "namespace": "",
        },
    )
    pressure: None | float = field(
        default=None,
        metadata={
            "name": "PRESSURE",
            "type": "Element",
            "namespace": "",
        },
    )
    range: None | float = field(
        default=None,
        metadata={
            "name": "RANGE",
            "type": "Element",
            "namespace": "",
        },
    )
    rcs: None | float = field(
        default=None,
        metadata={
            "name": "RCS",
            "type": "Element",
            "namespace": "",
        },
    )
    receive_freq: None | float = field(
        default=None,
        metadata={
            "name": "RECEIVE_FREQ",
            "type": "Element",
            "namespace": "",
        },
    )
    receive_freq_1: None | float = field(
        default=None,
        metadata={
            "name": "RECEIVE_FREQ_1",
            "type": "Element",
            "namespace": "",
        },
    )
    receive_freq_2: None | float = field(
        default=None,
        metadata={
            "name": "RECEIVE_FREQ_2",
            "type": "Element",
            "namespace": "",
        },
    )
    receive_freq_3: None | float = field(
        default=None,
        metadata={
            "name": "RECEIVE_FREQ_3",
            "type": "Element",
            "namespace": "",
        },
    )
    receive_freq_4: None | float = field(
        default=None,
        metadata={
            "name": "RECEIVE_FREQ_4",
            "type": "Element",
            "namespace": "",
        },
    )
    receive_freq_5: None | float = field(
        default=None,
        metadata={
            "name": "RECEIVE_FREQ_5",
            "type": "Element",
            "namespace": "",
        },
    )
    receive_phase_ct_1: None | float = field(
        default=None,
        metadata={
            "name": "RECEIVE_PHASE_CT_1",
            "type": "Element",
            "namespace": "",
        },
    )
    receive_phase_ct_2: None | float = field(
        default=None,
        metadata={
            "name": "RECEIVE_PHASE_CT_2",
            "type": "Element",
            "namespace": "",
        },
    )
    receive_phase_ct_3: None | float = field(
        default=None,
        metadata={
            "name": "RECEIVE_PHASE_CT_3",
            "type": "Element",
            "namespace": "",
        },
    )
    receive_phase_ct_4: None | float = field(
        default=None,
        metadata={
            "name": "RECEIVE_PHASE_CT_4",
            "type": "Element",
            "namespace": "",
        },
    )
    receive_phase_ct_5: None | float = field(
        default=None,
        metadata={
            "name": "RECEIVE_PHASE_CT_5",
            "type": "Element",
            "namespace": "",
        },
    )
    rhumidity: None | PercentageTypeUo = field(
        default=None,
        metadata={
            "name": "RHUMIDITY",
            "type": "Element",
            "namespace": "",
        },
    )
    stec: None | float = field(
        default=None,
        metadata={
            "name": "STEC",
            "type": "Element",
            "namespace": "",
        },
    )
    temperature: None | float = field(
        default=None,
        metadata={
            "name": "TEMPERATURE",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )
    transmit_freq_1: None | float = field(
        default=None,
        metadata={
            "name": "TRANSMIT_FREQ_1",
            "type": "Element",
            "namespace": "",
            "min_exclusive": 0.0,
        },
    )
    transmit_freq_2: None | float = field(
        default=None,
        metadata={
            "name": "TRANSMIT_FREQ_2",
            "type": "Element",
            "namespace": "",
            "min_exclusive": 0.0,
        },
    )
    transmit_freq_3: None | float = field(
        default=None,
        metadata={
            "name": "TRANSMIT_FREQ_3",
            "type": "Element",
            "namespace": "",
            "min_exclusive": 0.0,
        },
    )
    transmit_freq_4: None | float = field(
        default=None,
        metadata={
            "name": "TRANSMIT_FREQ_4",
            "type": "Element",
            "namespace": "",
            "min_exclusive": 0.0,
        },
    )
    transmit_freq_5: None | float = field(
        default=None,
        metadata={
            "name": "TRANSMIT_FREQ_5",
            "type": "Element",
            "namespace": "",
            "min_exclusive": 0.0,
        },
    )
    transmit_freq_rate_1: None | float = field(
        default=None,
        metadata={
            "name": "TRANSMIT_FREQ_RATE_1",
            "type": "Element",
            "namespace": "",
        },
    )
    transmit_freq_rate_2: None | float = field(
        default=None,
        metadata={
            "name": "TRANSMIT_FREQ_RATE_2",
            "type": "Element",
            "namespace": "",
        },
    )
    transmit_freq_rate_3: None | float = field(
        default=None,
        metadata={
            "name": "TRANSMIT_FREQ_RATE_3",
            "type": "Element",
            "namespace": "",
        },
    )
    transmit_freq_rate_4: None | float = field(
        default=None,
        metadata={
            "name": "TRANSMIT_FREQ_RATE_4",
            "type": "Element",
            "namespace": "",
        },
    )
    transmit_freq_rate_5: None | float = field(
        default=None,
        metadata={
            "name": "TRANSMIT_FREQ_RATE_5",
            "type": "Element",
            "namespace": "",
        },
    )
    transmit_phase_ct_1: None | float = field(
        default=None,
        metadata={
            "name": "TRANSMIT_PHASE_CT_1",
            "type": "Element",
            "namespace": "",
        },
    )
    transmit_phase_ct_2: None | float = field(
        default=None,
        metadata={
            "name": "TRANSMIT_PHASE_CT_2",
            "type": "Element",
            "namespace": "",
        },
    )
    transmit_phase_ct_3: None | float = field(
        default=None,
        metadata={
            "name": "TRANSMIT_PHASE_CT_3",
            "type": "Element",
            "namespace": "",
        },
    )
    transmit_phase_ct_4: None | float = field(
        default=None,
        metadata={
            "name": "TRANSMIT_PHASE_CT_4",
            "type": "Element",
            "namespace": "",
        },
    )
    transmit_phase_ct_5: None | float = field(
        default=None,
        metadata={
            "name": "TRANSMIT_PHASE_CT_5",
            "type": "Element",
            "namespace": "",
        },
    )
    tropo_dry: None | float = field(
        default=None,
        metadata={
            "name": "TROPO_DRY",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )
    tropo_wet: None | float = field(
        default=None,
        metadata={
            "name": "TROPO_WET",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
        },
    )
    vlbi_delay: None | float = field(
        default=None,
        metadata={
            "name": "VLBI_DELAY",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class AcmAdParametersType:
    class Meta:
        name = "acmAdParametersType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    ad_id: None | str = field(
        default=None,
        metadata={
            "name": "AD_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    ad_prev_id: None | str = field(
        default=None,
        metadata={
            "name": "AD_PREV_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    ad_method: None | AdMethodType = field(
        default=None,
        metadata={
            "name": "AD_METHOD",
            "type": "Element",
            "namespace": "",
        },
    )
    attitude_source: None | str = field(
        default=None,
        metadata={
            "name": "ATTITUDE_SOURCE",
            "type": "Element",
            "namespace": "",
        },
    )
    number_states: None | int = field(
        default=None,
        metadata={
            "name": "NUMBER_STATES",
            "type": "Element",
            "namespace": "",
        },
    )
    attitude_states: AcmAttitudeType = field(
        metadata={
            "name": "ATTITUDE_STATES",
            "type": "Element",
            "namespace": "",
        }
    )
    euler_rot_seq: None | RotseqType = field(
        default=None,
        metadata={
            "name": "EULER_ROT_SEQ",
            "type": "Element",
            "namespace": "",
        },
    )
    cov_type: None | AcmCovarianceLineType = field(
        default=None,
        metadata={
            "name": "COV_TYPE",
            "type": "Element",
            "namespace": "",
        },
    )
    ref_frame_a: str = field(
        metadata={
            "name": "REF_FRAME_A",
            "type": "Element",
            "namespace": "",
        }
    )
    ref_frame_b: str = field(
        metadata={
            "name": "REF_FRAME_B",
            "type": "Element",
            "namespace": "",
        }
    )
    rate_states: None | AttRateType = field(
        default=None,
        metadata={
            "name": "RATE_STATES",
            "type": "Element",
            "namespace": "",
        },
    )
    sigma_u: None | SigmaUtype = field(
        default=None,
        metadata={
            "name": "SIGMA_U",
            "type": "Element",
            "namespace": "",
        },
    )
    sigma_v: None | SigmaVtype = field(
        default=None,
        metadata={
            "name": "SIGMA_V",
            "type": "Element",
            "namespace": "",
        },
    )
    rate_process_noise_stddev: None | SigmaUtype = field(
        default=None,
        metadata={
            "name": "RATE_PROCESS_NOISE_STDDEV",
            "type": "Element",
            "namespace": "",
        },
    )
    sensor_data: list[SensorDataType] = field(
        default_factory=list,
        metadata={
            "name": "sensorData",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class CdmData:
    class Meta:
        name = "cdmData"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    od_parameters: None | OdParametersType = field(
        default=None,
        metadata={
            "name": "odParameters",
            "type": "Element",
            "namespace": "",
        },
    )
    additional_parameters: None | AdditionalParametersType = field(
        default=None,
        metadata={
            "name": "additionalParameters",
            "type": "Element",
            "namespace": "",
        },
    )
    state_vector: CdmStateVectorType = field(
        metadata={
            "name": "stateVector",
            "type": "Element",
            "namespace": "",
        }
    )
    covariance_matrix: CdmCovarianceMatrixType = field(
        metadata={
            "name": "covarianceMatrix",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class OcmData:
    class Meta:
        name = "ocmData"
        target_namespace = "urn:ccsds:schema:ndmxml"

    traj: list[OcmTrajStateType] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    phys: None | OcmPhysicalDescriptionType = field(
        default=None,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    cov: list[OcmCovarianceMatrixType] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    man: list[OcmManeuverParametersType] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    pert: None | OcmPerturbationsType = field(
        default=None,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    od: None | OcmOdParametersType = field(
        default=None,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    user: None | UserDefinedType = field(
        default=None,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class OemData:
    class Meta:
        name = "oemData"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    state_vector: list[StateVectorAccType] = field(
        default_factory=list,
        metadata={
            "name": "stateVector",
            "type": "Element",
            "namespace": "",
            "min_occurs": 1,
        },
    )
    covariance_matrix: list[OemCovarianceMatrixType] = field(
        default_factory=list,
        metadata={
            "name": "covarianceMatrix",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class OmmData:
    class Meta:
        name = "ommData"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    mean_elements: MeanElementsType = field(
        metadata={
            "name": "meanElements",
            "type": "Element",
            "namespace": "",
        }
    )
    spacecraft_parameters: None | SpacecraftParametersType = field(
        default=None,
        metadata={
            "name": "spacecraftParameters",
            "type": "Element",
            "namespace": "",
        },
    )
    tle_parameters: None | TleParametersType = field(
        default=None,
        metadata={
            "name": "tleParameters",
            "type": "Element",
            "namespace": "",
        },
    )
    covariance_matrix: None | OpmCovarianceMatrixType = field(
        default=None,
        metadata={
            "name": "covarianceMatrix",
            "type": "Element",
            "namespace": "",
        },
    )
    user_defined_parameters: None | UserDefinedType = field(
        default=None,
        metadata={
            "name": "userDefinedParameters",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class OpmData:
    class Meta:
        name = "opmData"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    state_vector: StateVectorType = field(
        metadata={
            "name": "stateVector",
            "type": "Element",
            "namespace": "",
        }
    )
    keplerian_elements: None | KeplerianElementsType = field(
        default=None,
        metadata={
            "name": "keplerianElements",
            "type": "Element",
            "namespace": "",
        },
    )
    spacecraft_parameters: None | SpacecraftParametersType = field(
        default=None,
        metadata={
            "name": "spacecraftParameters",
            "type": "Element",
            "namespace": "",
        },
    )
    covariance_matrix: None | OpmCovarianceMatrixType = field(
        default=None,
        metadata={
            "name": "covarianceMatrix",
            "type": "Element",
            "namespace": "",
        },
    )
    maneuver_parameters: list[ManeuverParametersType] = field(
        default_factory=list,
        metadata={
            "name": "maneuverParameters",
            "type": "Element",
            "namespace": "",
        },
    )
    user_defined_parameters: None | UserDefinedType = field(
        default=None,
        metadata={
            "name": "userDefinedParameters",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class QuaternionAngVelType:
    class Meta:
        name = "quaternionAngVelType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    epoch: str = field(
        metadata={
            "name": "EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    quaternion: QuaternionType = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    ang_vel: AngVelType = field(
        metadata={
            "name": "angVel",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class QuaternionDerivativeType:
    class Meta:
        name = "quaternionDerivativeType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    epoch: str = field(
        metadata={
            "name": "EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    quaternion: QuaternionType = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    quaternion_dot: QuaternionDotType = field(
        metadata={
            "name": "quaternionDot",
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class QuaternionStateType:
    class Meta:
        name = "quaternionStateType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    ref_frame_a: str = field(
        metadata={
            "name": "REF_FRAME_A",
            "type": "Element",
            "namespace": "",
        }
    )
    ref_frame_b: str = field(
        metadata={
            "name": "REF_FRAME_B",
            "type": "Element",
            "namespace": "",
        }
    )
    quaternion: QuaternionType = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    quaternion_dot: None | QuaternionDotType = field(
        default=None,
        metadata={
            "name": "quaternionDot",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class RdmData:
    class Meta:
        name = "rdmData"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    atmospheric_reentry_parameters: AtmosphericReentryParametersType = field(
        metadata={
            "name": "atmosphericReentryParameters",
            "type": "Element",
            "namespace": "",
        }
    )
    ground_impact_parameters: None | GroundImpactParametersType = field(
        default=None,
        metadata={
            "name": "groundImpactParameters",
            "type": "Element",
            "namespace": "",
        },
    )
    state_vector: None | StateVectorType = field(
        default=None,
        metadata={
            "name": "stateVector",
            "type": "Element",
            "namespace": "",
        },
    )
    covariance_matrix: None | OpmCovarianceMatrixType = field(
        default=None,
        metadata={
            "name": "covarianceMatrix",
            "type": "Element",
            "namespace": "",
        },
    )
    spacecraft_parameters: None | RdmSpacecraftParametersType = field(
        default=None,
        metadata={
            "name": "spacecraftParameters",
            "type": "Element",
            "namespace": "",
        },
    )
    od_parameters: None | OdParametersType = field(
        default=None,
        metadata={
            "name": "odParameters",
            "type": "Element",
            "namespace": "",
        },
    )
    user_defined_parameters: None | UserDefinedType = field(
        default=None,
        metadata={
            "name": "userDefinedParameters",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class RelativeMetadataData:
    class Meta:
        name = "relativeMetadataData"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    tca: str = field(
        metadata={
            "name": "TCA",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    miss_distance: LengthTypeUo = field(
        metadata={
            "name": "MISS_DISTANCE",
            "type": "Element",
            "namespace": "",
        }
    )
    relative_speed: None | DvType = field(
        default=None,
        metadata={
            "name": "RELATIVE_SPEED",
            "type": "Element",
            "namespace": "",
        },
    )
    relative_state_vector: None | RelativeStateVectorType = field(
        default=None,
        metadata={
            "name": "relativeStateVector",
            "type": "Element",
            "namespace": "",
        },
    )
    start_screen_period: None | str = field(
        default=None,
        metadata={
            "name": "START_SCREEN_PERIOD",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    stop_screen_period: None | str = field(
        default=None,
        metadata={
            "name": "STOP_SCREEN_PERIOD",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    screen_volume_frame: None | ScreenVolumeFrameType = field(
        default=None,
        metadata={
            "name": "SCREEN_VOLUME_FRAME",
            "type": "Element",
            "namespace": "",
        },
    )
    screen_volume_shape: None | ScreenVolumeShapeType = field(
        default=None,
        metadata={
            "name": "SCREEN_VOLUME_SHAPE",
            "type": "Element",
            "namespace": "",
        },
    )
    screen_volume_x: None | LengthTypeUo = field(
        default=None,
        metadata={
            "name": "SCREEN_VOLUME_X",
            "type": "Element",
            "namespace": "",
        },
    )
    screen_volume_y: None | LengthTypeUo = field(
        default=None,
        metadata={
            "name": "SCREEN_VOLUME_Y",
            "type": "Element",
            "namespace": "",
        },
    )
    screen_volume_z: None | LengthTypeUo = field(
        default=None,
        metadata={
            "name": "SCREEN_VOLUME_Z",
            "type": "Element",
            "namespace": "",
        },
    )
    screen_entry_time: None | str = field(
        default=None,
        metadata={
            "name": "SCREEN_ENTRY_TIME",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    screen_exit_time: None | str = field(
        default=None,
        metadata={
            "name": "SCREEN_EXIT_TIME",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        },
    )
    collision_probability: None | float = field(
        default=None,
        metadata={
            "name": "COLLISION_PROBABILITY",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0.0,
            "max_inclusive": 1.0,
        },
    )
    collision_probability_method: None | str = field(
        default=None,
        metadata={
            "name": "COLLISION_PROBABILITY_METHOD",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class TdmData:
    class Meta:
        name = "tdmData"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    observation: list[TrackingDataObservationType] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
            "min_occurs": 1,
        },
    )


@dataclass(kw_only=True)
class AcmData:
    class Meta:
        name = "acmData"
        target_namespace = "urn:ccsds:schema:ndmxml"

    att: list[AcmAttitudeStateType] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    phys: None | AcmPhysicalDescriptionType = field(
        default=None,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    cov: list[AcmCovarianceMatrixType] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    man: list[AcmManeuverParametersType] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    ad: None | AcmAdParametersType = field(
        default=None,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    user: None | UserDefinedType = field(
        default=None,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class ApmData:
    class Meta:
        name = "apmData"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    epoch: str = field(
        metadata={
            "name": "EPOCH",
            "type": "Element",
            "namespace": "",
            "pattern": r"\-?\d{4}\d*-((\d{2}\-\d{2})|\d{3})T\d{2}:\d{2}:\d{2}(\.\d*)?(Z|[+|\-]\d{2}:\d{2})?|[+|\-]?\d*(\.\d*)?",
        }
    )
    quaternion_state: list[QuaternionStateType] = field(
        default_factory=list,
        metadata={
            "name": "quaternionState",
            "type": "Element",
            "namespace": "",
        },
    )
    euler_angle_state: list[EulerAngleStateType] = field(
        default_factory=list,
        metadata={
            "name": "eulerAngleState",
            "type": "Element",
            "namespace": "",
        },
    )
    angular_velocity: list[AngVelStateType] = field(
        default_factory=list,
        metadata={
            "name": "angularVelocity",
            "type": "Element",
            "namespace": "",
        },
    )
    spin: list[SpinStateType] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    inertia: list[InertiaStateType] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    maneuver_parameters: list[AttManeuverStateType] = field(
        default_factory=list,
        metadata={
            "name": "maneuverParameters",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class AttitudeStateType:
    class Meta:
        name = "attitudeStateType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    quaternion_ephemeris: None | QuaternionEphemerisType = field(
        default=None,
        metadata={
            "name": "quaternionEphemeris",
            "type": "Element",
            "namespace": "",
        },
    )
    quaternion_derivative: None | QuaternionDerivativeType = field(
        default=None,
        metadata={
            "name": "quaternionDerivative",
            "type": "Element",
            "namespace": "",
        },
    )
    quaternion_ang_vel: None | QuaternionAngVelType = field(
        default=None,
        metadata={
            "name": "quaternionAngVel",
            "type": "Element",
            "namespace": "",
        },
    )
    euler_angle: None | EulerAngleType = field(
        default=None,
        metadata={
            "name": "eulerAngle",
            "type": "Element",
            "namespace": "",
        },
    )
    euler_angle_derivative: None | EulerAngleDerivativeType = field(
        default=None,
        metadata={
            "name": "eulerAngleDerivative",
            "type": "Element",
            "namespace": "",
        },
    )
    euler_angle_ang_vel: None | EulerAngleAngVelType = field(
        default=None,
        metadata={
            "name": "eulerAngleAngVel",
            "type": "Element",
            "namespace": "",
        },
    )
    spin: None | SpinType = field(
        default=None,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    spin_nutation: None | SpinNutationType = field(
        default=None,
        metadata={
            "name": "spinNutation",
            "type": "Element",
            "namespace": "",
        },
    )
    spin_nutation_mom: None | SpinNutationMomType = field(
        default=None,
        metadata={
            "name": "spinNutationMom",
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class CdmSegment:
    class Meta:
        name = "cdmSegment"
        target_namespace = "urn:ccsds:schema:ndmxml"

    metadata: CdmMetadata = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    data: CdmData = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class OcmSegment:
    class Meta:
        name = "ocmSegment"
        target_namespace = "urn:ccsds:schema:ndmxml"

    metadata: OcmMetadata = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    data: OcmData = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class OemSegment:
    class Meta:
        name = "oemSegment"
        target_namespace = "urn:ccsds:schema:ndmxml"

    metadata: OemMetadata = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    data: OemData = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class OmmSegment:
    class Meta:
        name = "ommSegment"
        target_namespace = "urn:ccsds:schema:ndmxml"

    metadata: OmmMetadata = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    data: OmmData = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class OpmSegment:
    class Meta:
        name = "opmSegment"
        target_namespace = "urn:ccsds:schema:ndmxml"

    metadata: OpmMetadata = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    data: OpmData = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class RdmSegment:
    class Meta:
        name = "rdmSegment"
        target_namespace = "urn:ccsds:schema:ndmxml"

    metadata: RdmMetadata = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    data: RdmData = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class TdmSegment:
    class Meta:
        name = "tdmSegment"
        target_namespace = "urn:ccsds:schema:ndmxml"

    metadata: TdmMetadata = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    data: TdmData = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class AcmSegment:
    class Meta:
        name = "acmSegment"
        target_namespace = "urn:ccsds:schema:ndmxml"

    metadata: AcmMetadata = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    data: AcmData = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class AemData:
    class Meta:
        name = "aemData"
        target_namespace = "urn:ccsds:schema:ndmxml"

    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    attitude_state: list[AttitudeStateType] = field(
        default_factory=list,
        metadata={
            "name": "attitudeState",
            "type": "Element",
            "namespace": "",
            "min_occurs": 1,
        },
    )


@dataclass(kw_only=True)
class ApmSegment:
    class Meta:
        name = "apmSegment"
        target_namespace = "urn:ccsds:schema:ndmxml"

    metadata: ApmMetadata = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    data: ApmData = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class CdmBody:
    class Meta:
        name = "cdmBody"
        target_namespace = "urn:ccsds:schema:ndmxml"

    relative_metadata_data: RelativeMetadataData = field(
        metadata={
            "name": "relativeMetadataData",
            "type": "Element",
            "namespace": "",
        }
    )
    segment: list[CdmSegment] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
            "min_occurs": 2,
            "max_occurs": 2,
        },
    )


@dataclass(kw_only=True)
class OcmBody:
    class Meta:
        name = "ocmBody"
        target_namespace = "urn:ccsds:schema:ndmxml"

    segment: OcmSegment = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class OemBody:
    class Meta:
        name = "oemBody"
        target_namespace = "urn:ccsds:schema:ndmxml"

    segment: list[OemSegment] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
            "min_occurs": 1,
        },
    )


@dataclass(kw_only=True)
class OmmBody:
    class Meta:
        name = "ommBody"
        target_namespace = "urn:ccsds:schema:ndmxml"

    segment: OmmSegment = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class OpmBody:
    class Meta:
        name = "opmBody"
        target_namespace = "urn:ccsds:schema:ndmxml"

    segment: OpmSegment = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class RdmBody:
    class Meta:
        name = "rdmBody"
        target_namespace = "urn:ccsds:schema:ndmxml"

    segment: RdmSegment = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class TdmBody:
    class Meta:
        name = "tdmBody"
        target_namespace = "urn:ccsds:schema:ndmxml"

    segment: list[TdmSegment] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
            "min_occurs": 1,
        },
    )


@dataclass(kw_only=True)
class AcmBody:
    class Meta:
        name = "acmBody"
        target_namespace = "urn:ccsds:schema:ndmxml"

    segment: AcmSegment = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class AemSegment:
    class Meta:
        name = "aemSegment"
        target_namespace = "urn:ccsds:schema:ndmxml"

    metadata: AemMetadata = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    data: AemData = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class ApmBody:
    class Meta:
        name = "apmBody"
        target_namespace = "urn:ccsds:schema:ndmxml"

    segment: ApmSegment = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )


@dataclass(kw_only=True)
class CdmType:
    class Meta:
        name = "cdmType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    header: CdmHeader = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    body: CdmBody = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    id: str = field(
        init=False,
        default="CCSDS_CDM_VERS",
        metadata={
            "type": "Attribute",
            "required": True,
        },
    )
    version: str = field(
        init=False,
        default="1.0",
        metadata={
            "type": "Attribute",
            "required": True,
        },
    )


@dataclass(kw_only=True)
class OcmType:
    class Meta:
        name = "ocmType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    header: OdmHeader = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    body: OcmBody = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    id: str = field(
        init=False,
        default="CCSDS_OCM_VERS",
        metadata={
            "type": "Attribute",
            "required": True,
        },
    )
    version: str = field(
        init=False,
        default="3.0",
        metadata={
            "type": "Attribute",
            "required": True,
        },
    )


@dataclass(kw_only=True)
class OemType:
    class Meta:
        name = "oemType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    header: OdmHeader = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    body: OemBody = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    id: str = field(
        init=False,
        default="CCSDS_OEM_VERS",
        metadata={
            "type": "Attribute",
            "required": True,
        },
    )
    version: str = field(
        init=False,
        default="3.0",
        metadata={
            "type": "Attribute",
            "required": True,
        },
    )


@dataclass(kw_only=True)
class OmmType:
    class Meta:
        name = "ommType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    header: OdmHeader = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    body: OmmBody = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    id: str = field(
        init=False,
        default="CCSDS_OMM_VERS",
        metadata={
            "type": "Attribute",
            "required": True,
        },
    )
    version: str = field(
        init=False,
        default="3.0",
        metadata={
            "type": "Attribute",
            "required": True,
        },
    )


@dataclass(kw_only=True)
class OpmType:
    class Meta:
        name = "opmType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    header: OdmHeader = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    body: OpmBody = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    id: str = field(
        init=False,
        default="CCSDS_OPM_VERS",
        metadata={
            "type": "Attribute",
            "required": True,
        },
    )
    version: str = field(
        init=False,
        default="3.0",
        metadata={
            "type": "Attribute",
            "required": True,
        },
    )


@dataclass(kw_only=True)
class RdmType:
    class Meta:
        name = "rdmType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    header: RdmHeader = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    body: RdmBody = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    id: str = field(
        init=False,
        default="CCSDS_RDM_VERS",
        metadata={
            "type": "Attribute",
            "required": True,
        },
    )
    version: str = field(
        init=False,
        default="1.0",
        metadata={
            "type": "Attribute",
            "required": True,
        },
    )


@dataclass(kw_only=True)
class TdmType:
    class Meta:
        name = "tdmType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    header: TdmHeader = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    body: TdmBody = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    id: str = field(
        init=False,
        default="CCSDS_TDM_VERS",
        metadata={
            "type": "Attribute",
            "required": True,
        },
    )
    version: str = field(
        init=False,
        default="2.0",
        metadata={
            "type": "Attribute",
            "required": True,
        },
    )


@dataclass(kw_only=True)
class Cdm(CdmType):
    class Meta:
        name = "cdm"


@dataclass(kw_only=True)
class Ocm(OcmType):
    class Meta:
        name = "ocm"


@dataclass(kw_only=True)
class Oem(OemType):
    class Meta:
        name = "oem"


@dataclass(kw_only=True)
class Omm(OmmType):
    class Meta:
        name = "omm"


@dataclass(kw_only=True)
class Opm(OpmType):
    class Meta:
        name = "opm"


@dataclass(kw_only=True)
class Rdm(RdmType):
    class Meta:
        name = "rdm"


@dataclass(kw_only=True)
class Tdm(TdmType):
    class Meta:
        name = "tdm"


@dataclass(kw_only=True)
class AcmType:
    class Meta:
        name = "acmType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    header: AdmHeader = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    body: AcmBody = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    id: str = field(
        init=False,
        default="CCSDS_ACM_VERS",
        metadata={
            "type": "Attribute",
            "required": True,
        },
    )
    version: str = field(
        init=False,
        default="2.0",
        metadata={
            "type": "Attribute",
            "required": True,
        },
    )


@dataclass(kw_only=True)
class AemBody:
    class Meta:
        name = "aemBody"
        target_namespace = "urn:ccsds:schema:ndmxml"

    segment: list[AemSegment] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
            "min_occurs": 1,
        },
    )


@dataclass(kw_only=True)
class ApmType:
    class Meta:
        name = "apmType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    header: AdmHeader = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    body: ApmBody = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    id: str = field(
        init=False,
        default="CCSDS_APM_VERS",
        metadata={
            "type": "Attribute",
            "required": True,
        },
    )
    version: str = field(
        init=False,
        default="2.0",
        metadata={
            "type": "Attribute",
            "required": True,
        },
    )


@dataclass(kw_only=True)
class Acm(AcmType):
    class Meta:
        name = "acm"


@dataclass(kw_only=True)
class Apm(ApmType):
    class Meta:
        name = "apm"


@dataclass(kw_only=True)
class AemType:
    class Meta:
        name = "aemType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    header: AdmHeader = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    body: AemBody = field(
        metadata={
            "type": "Element",
            "namespace": "",
        }
    )
    id: str = field(
        init=False,
        default="CCSDS_AEM_VERS",
        metadata={
            "type": "Attribute",
            "required": True,
        },
    )
    version: str = field(
        init=False,
        default="2.0",
        metadata={
            "type": "Attribute",
            "required": True,
        },
    )


@dataclass(kw_only=True)
class Aem(AemType):
    class Meta:
        name = "aem"


@dataclass(kw_only=True)
class NdmType:
    class Meta:
        name = "ndmType"
        target_namespace = "urn:ccsds:schema:ndmxml"

    message_id: None | str = field(
        default=None,
        metadata={
            "name": "MESSAGE_ID",
            "type": "Element",
            "namespace": "",
        },
    )
    comment: list[str] = field(
        default_factory=list,
        metadata={
            "name": "COMMENT",
            "type": "Element",
            "namespace": "",
        },
    )
    acm: list[AcmType] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    aem: list[AemType] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    apm: list[ApmType] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    cdm: list[CdmType] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    ocm: list[OcmType] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    oem: list[OemType] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    omm: list[OmmType] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    opm: list[OpmType] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    rdm: list[RdmType] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )
    tdm: list[TdmType] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "",
        },
    )


@dataclass(kw_only=True)
class Ndm(NdmType):
    class Meta:
        name = "ndm"
