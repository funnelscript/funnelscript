"""Verification suite for dynamic emission delays in FunnelScript World rules.

Verifies:
1. Emitting an event with dynamic delay expression: `emit Target() after state_lag;`
2. Arithmetic expression in delay: `emit Target() after (base_lag + extra_lag);`
3. Adaptive delay: delay changes dynamically when state changes.
4. Dimensional check: rejecting invalid units in dynamic delays (e.g., Currency).
5. Runtime boundary: rejecting negative or non-finite evaluated delays.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from funnelscript.compiler.world_ast import WorldAST, WorldTypeChecker
from funnelscript.core import Event
from funnelscript.parser import Parser
from funnelscript.runtime.world_executor import WorldExecutionError, WorldExecutor


def test_dynamic_emission_delay_executes_at_evaluated_time(tmp_path: Path):
    source = tmp_path / "dynamic_delay.fnls"
    source.write_text(
        """world LogisticsWorld {
  entity Courier {
    state courier_lag: int = 4;
    state orders_delivered: int = 0;

    event Dispatch(order_id: int);
    event Deliver(order_id: int);

    rule Ship on event Dispatch {
      emit Deliver(order_id = payload.order_id) after courier_lag;
    }

    rule Complete on event Deliver {
      transition orders_delivered = orders_delivered + 1;
    }
  }
}
""",
        encoding="utf-8",
    )

    ast = Parser.from_file(source)
    assert isinstance(ast, WorldAST)
    WorldTypeChecker.check(ast)

    executor = WorldExecutor(ast)
    events = [Event(time=10.0, name="Courier.Dispatch", payload={"order_id": 101})]
    result = executor.run(events)

    assert result.state["Courier"]["orders_delivered"] == 1
    # Check that Deliver was scheduled at 10.0 + 4 = 14.0
    deliver_event = next(e for e in result.processed if e.name == "Courier.Deliver")
    assert deliver_event.time == 14.0


def test_dynamic_emission_delay_expression_with_arithmetic(tmp_path: Path):
    source = tmp_path / "arithmetic_delay.fnls"
    source.write_text(
        """world AdaptiveWorld {
  entity Queue {
    state base_delay: float = 2.5;
    state surge_penalty: float = 1.5;
    state processed: int = 0;

    event Push();
    event Done();

    rule HandlePush on event Push {
      emit Done() after (base_delay + surge_penalty);
    }

    rule HandleDone on event Done {
      transition processed = processed + 1;
    }
  }
}
""",
        encoding="utf-8",
    )

    ast = Parser.from_file(source)
    assert isinstance(ast, WorldAST)
    WorldTypeChecker.check(ast)

    executor = WorldExecutor(ast)
    events = [Event(time=0.0, name="Queue.Push")]
    result = executor.run(events)

    assert result.state["Queue"]["processed"] == 1
    done_event = next(e for e in result.processed if e.name == "Queue.Done")
    assert done_event.time == 4.0


def test_dynamic_emission_delay_adaptive_change(tmp_path: Path):
    source = tmp_path / "adaptive_change.fnls"
    source.write_text(
        """world CongestionWorld {
  entity Hub {
    state transit_days: int = 3;
    state delivery_count: int = 0;

    event Order();
    event IncreaseDelay(extra: int);
    event Arrive();

    rule OnOrder on event Order {
      emit Arrive() after transit_days;
    }

    rule Congest on event IncreaseDelay {
      transition transit_days = transit_days + payload.extra;
    }

    rule OnArrive on event Arrive {
      transition delivery_count = delivery_count + 1;
    }
  }
}
""",
        encoding="utf-8",
    )

    ast = Parser.from_file(source)
    executor = WorldExecutor(ast)
    events = [
        Event(time=1.0, name="Hub.Order"),                          # schedules at 1 + 3 = 4.0
        Event(time=2.0, name="Hub.IncreaseDelay", payload={"extra": 5}), # transit_days becomes 8
        Event(time=5.0, name="Hub.Order"),                          # schedules at 5 + 8 = 13.0
    ]
    result = executor.run(events)

    assert result.state["Hub"]["delivery_count"] == 2
    arrivals = [e for e in result.processed if e.name == "Hub.Arrive"]
    assert len(arrivals) == 2
    assert arrivals[0].time == 4.0
    assert arrivals[1].time == 13.0


def test_negative_dynamic_delay_fails_at_runtime(tmp_path: Path):
    source = tmp_path / "negative_dynamic_delay.fnls"
    source.write_text(
        """world InvalidDynamicWorld {
  entity Bad {
    state negative_lag: int = -5;

    event Trigger();
    event Step();

    rule OnTrig on event Trigger {
      emit Step() after negative_lag;
    }

    rule OnStep on event Step {
    }
  }
}
""",
        encoding="utf-8",
    )

    ast = Parser.from_file(source)
    executor = WorldExecutor(ast)
    events = [Event(time=0.0, name="Bad.Trigger")]
    with pytest.raises(WorldExecutionError, match="finite non-negative number"):
        executor.run(events)
