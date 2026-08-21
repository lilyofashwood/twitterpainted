from engine.analyzers.statistical_steg import _parse_stegexpose_output


def test_stegexpose_suspicious_output_is_parsed_with_size():
    verdict, hidden_bytes = _parse_stegexpose_output(
        "carrier.png is suspicious. Approximate amount of hidden data is 2921 bytes.\n",
        0,
    )

    assert verdict == "suspicious"
    assert hidden_bytes == 2921


def test_stegexpose_java_exception_is_not_reported_as_clean():
    verdict, hidden_bytes = _parse_stegexpose_output(
        'Exception in thread "main" java.lang.NullPointerException\n',
        0,
    )

    assert verdict == "error"
    assert hidden_bytes is None


def test_stegexpose_nonzero_exit_is_an_error():
    verdict, _ = _parse_stegexpose_output("carrier.png is clean.\n", 2)

    assert verdict == "error"
