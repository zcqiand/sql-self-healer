from sql_self_healer.state import AgentState
from sql_self_healer.llm import FakeLLM


def test_state_defaults():
    s: AgentState = {
        "query": "", "sql": "", "error": "", "retries": 0,
        "result": "", "tenant_id": "t1", "approved": False,
    }
    assert s["retries"] == 0


def test_fake_llm_returns_scripted():
    llm = FakeLLM(script=["SELECT 1", "SELECT 2"])
    assert llm.generate("x") == "SELECT 1"
    assert llm.generate("y") == "SELECT 2"


def test_fake_llm_exhausted_returns_last():
    llm = FakeLLM(script=["only"])
    assert llm.generate("a") == "only"
    assert llm.generate("b") == "only"  # exhausted → last item
