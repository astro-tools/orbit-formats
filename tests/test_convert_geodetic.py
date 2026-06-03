"""Geodetic projection: ECEF <-> geodetic checked against astropy ``EarthLocation`` (the
independent reference the DoD names), round-trip invariants, the vectorised / scalar shapes, the
table-driven ellipsoid, the ``GeodeticLocation`` value type, and the pure-numpy (astropy-free)
implementation."""

from __future__ import annotations

import subprocess
import sys
import textwrap

import numpy as np
import pytest

from orbit_formats.convert import (
    Ellipsoid,
    GeodeticLocation,
    cartesian_to_geodetic,
    geodetic_to_cartesian,
)

# A spread of geodetic points (longitude deg, latitude deg, height km) the DoD calls for:
# the equator, mid-latitudes, the poles, high altitude (GEO), and a sub-ellipsoid (negative)
# height. Longitudes span both signs and wrap, latitudes both hemispheres.
GEODETIC_POINTS = [
    (0.0, 0.0, 0.0),  # equator, prime meridian, on the ellipsoid
    (90.0, 0.0, 0.0),  # equator, 90 E
    (-75.0, 0.0, 10.0),  # equator, west, 10 km up
    (45.0, 45.0, 0.5),  # mid-latitude
    (-123.12, -34.56, 1.234),  # southern mid-latitude, fractional everything
    (180.0, 12.3, 0.0),  # antimeridian
    (10.0, 0.0, 35786.0),  # GEO altitude over the equator
    (250.0, 80.0, 2.0),  # high northern latitude, longitude > 180
    (0.0, 90.0, 0.0),  # north pole, on the ellipsoid
    (0.0, -90.0, 100.0),  # south pole, 100 km up
    (33.0, 60.0, -0.4),  # below the ellipsoid (negative height)
]

# ECEF points (km) for the inverse direction, independent of our own forward transform.
CARTESIAN_POINTS = [
    np.array([6378.137, 0.0, 0.0]),  # on the equator
    np.array([0.0, 6378.137, 0.0]),
    np.array([4517.59, 4517.59, 0.0]),  # ~45 deg longitude on the equator
    np.array([3194.0, 3194.0, 4488.0]),  # mid-latitude
    np.array([0.0, 0.0, 6356.7523142]),  # the north pole (polar semi-minor axis)
    np.array([0.0, 0.0, -7000.0]),  # over the south pole, above the surface
    np.array([42164.0, 0.0, 0.0]),  # GEO radius on the equator
    np.array([-2000.0, -3000.0, 5500.0]),  # general northern point
]


def _astropy_to_geodetic(
    xyz_km: np.ndarray, ellipsoid: str = "WGS84"
) -> tuple[float, float, float]:
    """Project an ECEF position to geodetic with astropy — the DoD's independent reference."""
    from astropy import units as u
    from astropy.coordinates import EarthLocation

    location = EarthLocation.from_geocentric(xyz_km[0] * u.km, xyz_km[1] * u.km, xyz_km[2] * u.km)
    geodetic = location.to_geodetic(ellipsoid)
    return (
        float(geodetic.lon.to_value(u.deg)),
        float(geodetic.lat.to_value(u.deg)),
        float(geodetic.height.to_value(u.km)),
    )


def _astropy_to_cartesian(
    longitude: float, latitude: float, height: float, ellipsoid: str = "WGS84"
) -> np.ndarray:
    """Place a geodetic coordinate in ECEF with astropy — the forward-direction reference."""
    from astropy import units as u
    from astropy.coordinates import EarthLocation

    location = EarthLocation.from_geodetic(
        longitude * u.deg, latitude * u.deg, height * u.km, ellipsoid=ellipsoid
    )
    return np.array(
        [location.x.to_value(u.km), location.y.to_value(u.km), location.z.to_value(u.km)]
    )


def _wrap_longitude_difference(a: float, b: float) -> float:
    """The smallest absolute longitude difference (deg), accounting for the 360 deg wrap."""
    return abs((a - b + 180.0) % 360.0 - 180.0)


# --- forward (geodetic -> Cartesian) against astropy ---------------------------------------


@pytest.mark.parametrize(("longitude", "latitude", "height"), GEODETIC_POINTS)
def test_geodetic_to_cartesian_matches_astropy(
    longitude: float, latitude: float, height: float
) -> None:
    xyz = geodetic_to_cartesian(longitude, latitude, height)
    reference = _astropy_to_cartesian(longitude, latitude, height)
    assert xyz.shape == (3,)
    np.testing.assert_allclose(xyz, reference, atol=1e-9, rtol=0.0)


# --- inverse (Cartesian -> geodetic) against astropy ---------------------------------------


@pytest.mark.parametrize("xyz", CARTESIAN_POINTS)
def test_cartesian_to_geodetic_matches_astropy(xyz: np.ndarray) -> None:
    longitude, latitude, height = cartesian_to_geodetic(xyz)
    ref_lon, ref_lat, ref_height = _astropy_to_geodetic(xyz)
    # Latitude and height to ~micrometre / micro-arcsecond; longitude compared modulo the wrap
    # (it is undefined exactly on the axis, where our value and astropy's may differ by 360).
    np.testing.assert_allclose(float(latitude), ref_lat, atol=1e-9, rtol=0.0)
    np.testing.assert_allclose(float(height), ref_height, atol=1e-9, rtol=0.0)
    assert _wrap_longitude_difference(float(longitude), ref_lon) <= 1e-9


# --- round-trip invariants ----------------------------------------------------------------


@pytest.mark.parametrize("xyz", CARTESIAN_POINTS)
def test_cartesian_round_trip(xyz: np.ndarray) -> None:
    # Cartesian -> geodetic -> Cartesian is the unambiguous round trip (no pole longitude
    # degeneracy), so it must recover the position to tight tolerance.
    longitude, latitude, height = cartesian_to_geodetic(xyz)
    back = geodetic_to_cartesian(longitude, latitude, height)
    np.testing.assert_allclose(back, xyz, atol=1e-9, rtol=0.0)


@pytest.mark.parametrize(("longitude", "latitude", "height"), GEODETIC_POINTS)
def test_geodetic_round_trip(longitude: float, latitude: float, height: float) -> None:
    xyz = geodetic_to_cartesian(longitude, latitude, height)
    out_lon, out_lat, out_height = cartesian_to_geodetic(xyz)
    np.testing.assert_allclose(float(out_lat), latitude, atol=1e-9, rtol=0.0)
    np.testing.assert_allclose(float(out_height), height, atol=1e-9, rtol=0.0)
    # Longitude is undefined at the poles, where cos(lat) -> 0; only check it away from them.
    if abs(latitude) < 90.0:
        assert _wrap_longitude_difference(float(out_lon), longitude) <= 1e-9


# --- vectorisation and broadcasting -------------------------------------------------------


def test_cartesian_to_geodetic_is_vectorised() -> None:
    batch = np.array(CARTESIAN_POINTS)
    longitude, latitude, height = cartesian_to_geodetic(batch)
    assert longitude.shape == latitude.shape == height.shape == (len(CARTESIAN_POINTS),)
    for index, xyz in enumerate(CARTESIAN_POINTS):
        one_lon, one_lat, one_height = cartesian_to_geodetic(xyz)
        np.testing.assert_allclose(longitude[index], float(one_lon), atol=0.0, rtol=0.0)
        np.testing.assert_allclose(latitude[index], float(one_lat), atol=0.0, rtol=0.0)
        np.testing.assert_allclose(height[index], float(one_height), atol=0.0, rtol=0.0)


def test_geodetic_to_cartesian_broadcasts() -> None:
    longitudes = np.array([p[0] for p in GEODETIC_POINTS])
    latitudes = np.array([p[1] for p in GEODETIC_POINTS])
    heights = np.array([p[2] for p in GEODETIC_POINTS])
    batch = geodetic_to_cartesian(longitudes, latitudes, heights)
    assert batch.shape == (len(GEODETIC_POINTS), 3)
    for index, (lon, lat, height) in enumerate(GEODETIC_POINTS):
        np.testing.assert_allclose(batch[index], geodetic_to_cartesian(lon, lat, height))


def test_geodetic_to_cartesian_broadcasts_a_scalar_height() -> None:
    # A scalar height broadcasts against array longitude / latitude.
    longitudes = np.array([0.0, 90.0, 180.0])
    latitudes = np.array([0.0, 10.0, -20.0])
    batch = geodetic_to_cartesian(longitudes, latitudes, 5.0)
    assert batch.shape == (3, 3)
    for index in range(3):
        np.testing.assert_allclose(
            batch[index], geodetic_to_cartesian(longitudes[index], latitudes[index], 5.0)
        )


# --- the table-driven ellipsoid -----------------------------------------------------------


def test_unknown_ellipsoid_name_raises() -> None:
    with pytest.raises(ValueError, match="no ellipsoid known by name"):
        cartesian_to_geodetic(CARTESIAN_POINTS[0], ellipsoid="MARS")
    with pytest.raises(ValueError, match="no ellipsoid known by name"):
        geodetic_to_cartesian(0.0, 0.0, 0.0, ellipsoid="MARS")


def test_custom_ellipsoid_instance_matches_astropy_grs80() -> None:
    # GRS80 is not in the built-in table; pass it as a custom Ellipsoid and check it agrees with
    # astropy's GRS80 — proving a new body needs no new code path.
    grs80 = Ellipsoid(semi_major_axis=6378.137, inverse_flattening=298.257222101)
    point = (-123.12, 45.0, 1.5)
    xyz = geodetic_to_cartesian(*point, ellipsoid=grs80)
    np.testing.assert_allclose(xyz, _astropy_to_cartesian(*point, ellipsoid="GRS80"), atol=1e-9)
    longitude, latitude, height = cartesian_to_geodetic(xyz, ellipsoid=grs80)
    ref_lon, ref_lat, ref_height = _astropy_to_geodetic(xyz, ellipsoid="GRS80")
    np.testing.assert_allclose(float(latitude), ref_lat, atol=1e-9)
    np.testing.assert_allclose(float(height), ref_height, atol=1e-9)
    assert _wrap_longitude_difference(float(longitude), ref_lon) <= 1e-9


def test_sphere_ellipsoid_gives_geocentric_latitude() -> None:
    # A sphere (infinite inverse flattening -> zero eccentricity): geodetic latitude collapses to
    # the geocentric one and height is the radial distance minus the radius.
    sphere = Ellipsoid(semi_major_axis=6371.0, inverse_flattening=float("inf"))
    assert sphere.flattening == 0.0
    assert sphere.eccentricity_squared == 0.0
    xyz = np.array([1000.0, 0.0, 1000.0])
    longitude, latitude, height = cartesian_to_geodetic(xyz, ellipsoid=sphere)
    np.testing.assert_allclose(float(longitude), 0.0, atol=1e-12)
    np.testing.assert_allclose(float(latitude), 45.0, atol=1e-12)
    np.testing.assert_allclose(float(height), float(np.linalg.norm(xyz)) - 6371.0, atol=1e-9)


def test_wgs84_ellipsoid_constants() -> None:
    wgs84 = Ellipsoid(semi_major_axis=6378.137, inverse_flattening=298.257223563)
    np.testing.assert_allclose(wgs84.flattening, 1.0 / 298.257223563)
    np.testing.assert_allclose(wgs84.eccentricity_squared, 0.0066943799901413165, rtol=1e-12)


def test_ellipsoid_rejects_physically_impossible_parameters() -> None:
    # inverse_flattening = 0 (a plausible "no flattening" mistake) used to raise an opaque
    # ZeroDivisionError in .flattening; a non-positive axis or a sub-unity inverse flattening
    # (e^2 >= 1) used to yield silent NaN / nonsense coordinates. All now fail clearly at
    # construction, and the sphere idiom is named in the message.
    with pytest.raises(ValueError, match=r"float\('inf'\) for a sphere"):
        Ellipsoid(semi_major_axis=6378.137, inverse_flattening=0.0)
    with pytest.raises(ValueError, match="inverse_flattening must be greater than 1"):
        Ellipsoid(semi_major_axis=6378.137, inverse_flattening=0.5)
    with pytest.raises(ValueError, match="semi_major_axis must be positive"):
        Ellipsoid(semi_major_axis=-6378.137, inverse_flattening=298.257223563)
    with pytest.raises(ValueError, match="semi_major_axis must be positive"):
        Ellipsoid(semi_major_axis=0.0, inverse_flattening=298.257223563)
    # NaN is rejected too — the `not _ > _` guards catch it rather than propagating NaN.
    with pytest.raises(ValueError, match="semi_major_axis must be positive"):
        Ellipsoid(semi_major_axis=float("nan"), inverse_flattening=298.257223563)
    # A sphere (infinite inverse flattening, f = 0) stays valid.
    assert Ellipsoid(semi_major_axis=6371.0, inverse_flattening=float("inf")).flattening == 0.0


# --- the latitude iteration's safety cap --------------------------------------------------


def test_latitude_iteration_cap_still_returns_a_sane_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The iteration normally converges and breaks well before the cap. If it is capped before
    # convergence (loop exits by exhaustion, not by break), it must still return a finite, close
    # result rather than diverge or error.
    from orbit_formats.convert import geodetic as geodetic_module

    xyz = np.array([3194.0, 3194.0, 4488.0])  # mid-latitude, needs more than one step
    _, converged_lat, _ = cartesian_to_geodetic(xyz)  # the uncapped reference, before patching

    monkeypatch.setattr(geodetic_module, "_MAX_LATITUDE_ITERATIONS", 1)
    _, capped_lat, capped_height = geodetic_module.cartesian_to_geodetic(xyz)

    assert np.isfinite(float(capped_lat))
    assert np.isfinite(float(capped_height))
    # A single step from the spherical seed is already within a hundredth of a degree.
    np.testing.assert_allclose(float(capped_lat), float(converged_lat), atol=1e-2)


# --- shape rejection ----------------------------------------------------------------------


def test_cartesian_to_geodetic_rejects_a_bad_trailing_axis() -> None:
    with pytest.raises(ValueError, match="trailing axis of length 3"):
        cartesian_to_geodetic(np.array([1.0, 2.0]))
    with pytest.raises(ValueError, match="trailing axis of length 3"):
        cartesian_to_geodetic(np.zeros((4, 2)))


# --- the GeodeticLocation value type ------------------------------------------------------


def test_geodetic_location_round_trips_through_cartesian() -> None:
    site = GeodeticLocation(longitude=-75.7, latitude=45.4, height=0.07)
    xyz = site.to_cartesian()
    assert xyz.shape == (3,)
    np.testing.assert_allclose(xyz, geodetic_to_cartesian(-75.7, 45.4, 0.07))
    recovered = GeodeticLocation.from_cartesian(xyz)
    np.testing.assert_allclose(recovered.longitude, site.longitude, atol=1e-9)
    np.testing.assert_allclose(recovered.latitude, site.latitude, atol=1e-9)
    np.testing.assert_allclose(recovered.height, site.height, atol=1e-9)


def test_geodetic_location_defaults_to_wgs84_and_is_frozen() -> None:
    site = GeodeticLocation(longitude=0.0, latitude=0.0, height=0.0)
    assert site.ellipsoid == "WGS84"
    with pytest.raises(AttributeError):
        site.latitude = 1.0  # type: ignore[misc]


def test_geodetic_location_carries_a_custom_ellipsoid() -> None:
    grs80 = Ellipsoid(semi_major_axis=6378.137, inverse_flattening=298.257222101)
    site = GeodeticLocation(longitude=10.0, latitude=50.0, height=0.3, ellipsoid=grs80)
    np.testing.assert_allclose(
        site.to_cartesian(), geodetic_to_cartesian(10.0, 50.0, 0.3, ellipsoid=grs80)
    )
    recovered = GeodeticLocation.from_cartesian(site.to_cartesian(), ellipsoid=grs80)
    np.testing.assert_allclose(recovered.latitude, 50.0, atol=1e-9)


def test_geodetic_location_from_cartesian_rejects_a_non_single_position() -> None:
    with pytest.raises(ValueError, match="single \\(3,\\) position"):
        GeodeticLocation.from_cartesian(np.zeros((2, 3)))


# --- the pure-numpy contract: no astropy in the implementation ----------------------------


def test_geodetic_projection_does_not_import_astropy() -> None:
    # The projection is closed-form geometry; unlike the frame rotation it must not pull astropy
    # in. Run out-of-process so the check is not fooled by another test importing astropy first.
    program = textwrap.dedent(
        """
        import sys
        import numpy as np
        from orbit_formats.convert import cartesian_to_geodetic, geodetic_to_cartesian

        xyz = geodetic_to_cartesian(45.0, 45.0, 0.5)
        cartesian_to_geodetic(xyz)
        assert "astropy" not in sys.modules, "astropy imported by the geodetic projection"
        print("OK")
        """
    )
    result = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("OK")
