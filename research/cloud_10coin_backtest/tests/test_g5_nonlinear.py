import numpy as np

from optimize.nonlinear_model import fit_nonlinear, predict_nonlinear_proba


def _xor_sample(repeats=80):
    base_x = np.array([
        [-1.0, -1.0],
        [-1.0,  1.0],
        [ 1.0, -1.0],
        [ 1.0,  1.0],
    ], dtype=float)
    base_y = np.array([0, 1, 1, 0], dtype=int)
    return np.tile(base_x, (repeats, 1)), np.tile(base_y, repeats)


def test_nonlinear_model_learns_xor_interaction():
    x, y = _xor_sample()
    model = fit_nonlinear(
        x,
        y,
        max_depth=2,
        learning_rate=0.08,
        max_iter=80,
        l2_regularization=1.0,
        random_state=17,
    )
    p = predict_nonlinear_proba(model, np.array([
        [-1.0, -1.0], [-1.0, 1.0], [1.0, -1.0], [1.0, 1.0]
    ]))
    assert p[0] < 0.30
    assert p[1] > 0.70
    assert p[2] > 0.70
    assert p[3] < 0.30


def test_nonlinear_model_is_deterministic_for_same_seed():
    x, y = _xor_sample(40)
    kwargs = dict(max_depth=3, learning_rate=0.06, max_iter=60, l2_regularization=2.0, random_state=23)
    a = fit_nonlinear(x, y, **kwargs)
    b = fit_nonlinear(x, y, **kwargs)
    pa = predict_nonlinear_proba(a, x[:20])
    pb = predict_nonlinear_proba(b, x[:20])
    assert np.allclose(pa, pb, atol=1e-12)


def test_fit_api_accepts_training_data_only():
    x, y = _xor_sample(10)
    # The training API deliberately has no validation/holdout inputs; passing one must fail.
    try:
        fit_nonlinear(x, y, validation_x=x)
    except TypeError:
        pass
    else:
        raise AssertionError("trainer unexpectedly accepted validation/holdout data")
