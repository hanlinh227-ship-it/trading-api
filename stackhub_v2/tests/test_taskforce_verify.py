from stackhub.taskforce_verify import solve_challenge


def test_solve_challenge_handles_arithmetic():
    assert solve_challenge("What is 17 + 25?") == "42"
    assert solve_challenge("Compute 9 * 7") == "63"


def test_solve_challenge_handles_reverse_string():
    assert solve_challenge('Reverse the string "agent42"') == "24tnega"


def test_solve_challenge_handles_word_count():
    prompt = 'How many words are in this sentence? Respond with ONLY the number, nothing else: "hotel lima romeo sierra echo"'
    assert solve_challenge(prompt) == "5"


def test_solve_challenge_refuses_unknown_prompt():
    assert solve_challenge("Explain why the sky is blue") is None
