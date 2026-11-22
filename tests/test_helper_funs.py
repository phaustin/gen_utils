import numpy as np

# import the module rather than its functions: helper_funs.test_scalar
# would otherwise be collected by pytest as a test
from gen_utils.utils import helper_funs as hf


def test_formatvar():
    fmt = hf.formatvar("{:5.2f}")
    assert fmt(3.14159) == " 3.14"


def test_scalar_check():
    assert hf.test_scalar(1, 2.0, np.float64(3))
    assert not hf.test_scalar(1, np.array([1, 2]))


def test_make_tuple():
    tup = hf.make_tuple({"a": 1, "b": 2})
    assert tup.a == 1 and tup.b == 2


def test_find_centers():
    edges = np.array([0.0, 1.0, 2.0, 4.0])
    np.testing.assert_allclose(hf.find_centers(edges), [0.5, 1.5, 3.0])


def test_nudge():
    p = np.array([1.0, 1.0, 2.0, 3.0, 3.0, 4.0])
    expected = np.array([1, 1.001, 2, 3, 3.003, 4])  # +0.1% of the repeated value
    np.testing.assert_allclose(hf.nudge(p), expected)
