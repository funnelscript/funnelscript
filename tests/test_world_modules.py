"""H-M1 through H-M4: portable World imports and marketing library semantics."""

from importlib import resources
import json
import random
import subprocess
import sys

import pytest

from funnelscript.core import Event
from funnelscript.parser import Parser, ParserError
from funnelscript.compiler.world_ast import WorldTypeError
from funnelscript.runtime.world_executor import WorldExecutor


IMPORT_SOURCE = """world LaunchExperiment {
  import "std:marketing/lead_response.fnl" as Prospect;
}"""


def write_world(tmp_path, source=IMPORT_SOURCE, filename="entry.fnl"):
    path = tmp_path / filename
    path.write_text(source, encoding="utf-8")
    return path


def impression(time=0, p=0.7, cost=2.0, order=100.0):
    return Event(
        time, "Prospect.Impression",
        payload={"cpc": cost, "conversion_probability": p, "order_value": order},
    )


def test_standard_library_import_aliases_one_world_agent(tmp_path):
    world = Parser.from_file(write_world(tmp_path))
    assert world.name == "LaunchExperiment"
    assert [(d.kind, d.name) for d in world.declarations] == [("agent", "Prospect")]
    assert [event.name for event in world.declarations[0].events] == [
        "Impression", "Checkout"
    ]


@pytest.mark.parametrize(("seed", "converted"), [(1, True), (2, False)])
def test_marketing_journey_is_seeded_and_processes_one_checkout(tmp_path, seed, converted):
    subject = WorldExecutor(Parser.from_file(write_world(tmp_path)))
    result = subject.run([impression()], seed=seed)
    assert result.state["Prospect"] == {
        "exposed": True,
        "converted": converted,
        "spend": 2.0,
        "revenue": 100.0 if converted else 0.0,
    }
    assert (random.Random(seed).random() < 0.7) is converted
    assert [(item.name, item.time) for item in result.processed] == [
        ("Prospect.Impression", 0), ("Prospect.Checkout", 1)
    ]
    assert result.processed[1].payload == {"order_value": 100.0}
    assert result.pending == ()
    assert result.intents == ()


def test_duplicate_impression_is_ignored_without_extra_checkouts_or_draws(tmp_path):
    subject = WorldExecutor(Parser.from_file(write_world(tmp_path)))
    result = subject.run([impression(0), impression(0, p=1.0, cost=100.0)], seed=2)
    assert result.state["Prospect"] == {
        "exposed": True, "converted": False, "spend": 2.0, "revenue": 0.0
    }
    assert [item.name for item in result.processed] == [
        "Prospect.Impression", "Prospect.Impression", "Prospect.Checkout"
    ]


def test_imported_module_equals_inlined_source(tmp_path):
    module_path = resources.files("funnelscript").joinpath(
        "stdlib", "marketing", "lead_response.fnl"
    )
    module_text = module_path.read_text(encoding="utf-8")
    inline = module_text.replace("world LeadResponseLibrary", "world LaunchExperiment").replace(
        "agent Lead {", "agent Prospect {"
    )
    imported = WorldExecutor(Parser.from_file(write_world(tmp_path)))
    inlined = WorldExecutor(Parser.from_file(write_world(tmp_path, inline, "inline.fnl")))
    events = [impression()]
    assert imported.run(events, seed=13) == inlined.run(events, seed=13)


def test_local_community_module_import_uses_only_file_directory(tmp_path):
    write_world(
        tmp_path, """world Library {
          entity Ledger {
            state n: int = 0;
            rule Count on event Tick { transition n = n + 1; }
          }
        }""", filename="local.fnl",
    )
    world = Parser.from_file(write_world(
        tmp_path, 'world Own { import "./local.fnl" as CustomLedger; }'
    ))
    result = WorldExecutor(world).run([Event(0, "CustomLedger.Tick")])
    assert result.state["CustomLedger"]["n"] == 1


@pytest.mark.parametrize(
    "reference",
    [
        "../outside.fnl",
        "/tmp/secret.fnl",
        "./missing.fnl",
        "std:../../secrets.fnl",
        "std:marketing/no_such_file.fnl",
        "local.json",
    ],
)
def test_unsafe_or_missing_modules_fail_before_execution(tmp_path, reference):
    source = f'world W {{ import "{reference}" as X; }}'
    with pytest.raises((ParserError, ValueError), match="(module|Module|path|Path)"):
        Parser.from_file(write_world(tmp_path, source))


def test_symlink_escape_is_rejected(tmp_path):
    outside = tmp_path.parent / "external.fnl"
    outside.write_text("world External { entity E {} }", encoding="utf-8")
    link = tmp_path / "escape.fnl"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Symlink creation is unavailable on this filesystem")
    with pytest.raises(ParserError, match="(path|Path|module|Module)"):
        Parser.from_file(write_world(
            tmp_path, 'world W { import "escape.fnl" as E; }'
        ))


@pytest.mark.parametrize(
    "module_source",
    [
        "world Empty {}",
        "world Multiple { entity A {} entity B {} }",
    ],
)
def test_module_must_export_exactly_one_declaration(tmp_path, module_source):
    write_world(tmp_path, module_source, "module.fnl")
    with pytest.raises(ParserError, match="exactly one"):
        Parser.from_file(write_world(
            tmp_path, 'world W { import "module.fnl" as X; }'
        ))


def test_import_alias_cannot_collide_with_local_owner(tmp_path):
    source = """world W {
      entity Prospect {}
      import "std:marketing/lead_response.fnl" as Prospect;
    }"""
    with pytest.raises(WorldTypeError, match="Duplicate declaration"):
        Parser.from_file(write_world(tmp_path, source))


def test_module_import_cycle_fails_cleanly(tmp_path):
    write_world(tmp_path, 'world A { import "b.fnl" as B; }', "a.fnl")
    write_world(tmp_path, 'world B { import "a.fnl" as A; }', "b.fnl")
    with pytest.raises(ParserError, match="(Cyclic|cycle)"):
        Parser.from_file(tmp_path / "a.fnl")


def test_invalid_library_source_fails_existing_world_type_checker(tmp_path):
    write_world(
        tmp_path, 'world Bad { agent A { state n: int = true; } }', "bad.fnl"
    )
    with pytest.raises(WorldTypeError, match="Type mismatch"):
        Parser.from_file(write_world(
            tmp_path, 'world W { import "bad.fnl" as X; }'
        ))


def test_module_import_requires_a_real_source_path():
    from funnelscript.tokens import Lexer

    tokens = Lexer(IMPORT_SOURCE).tokenize()
    with pytest.raises(ParserError, match="file"):
        Parser(tokens).parse_world()


def test_imported_owners_preserve_legacy_source_compatibility(tmp_path):
    local = write_world(tmp_path, "world W { entity E {} }")
    assert Parser.from_file(local).declarations[0].name == "E"
    strategy = Parser.from_file("examples/black_friday_2026.fnl")
    assert strategy.strategy_name == "ECommerce_Black_Friday_2026"


def test_cli_runs_imported_marketing_library_from_elsewhere(tmp_path):
    source = write_world(tmp_path)
    command = [
        sys.executable, "-m", "funnelscript.cli", "run-world",
        str(source), "--event", json.dumps({
            "name": "Prospect.Impression", "time": 0,
            "payload": {
                "cpc": 2.0, "conversion_probability": 0.7,
                "order_value": 100.0,
            },
        }), "--seed", "1",
    ]
    process = subprocess.run(
        command, cwd=tmp_path, text=True, capture_output=True, check=True
    )
    result = json.loads(process.stdout)
    assert result["state"]["Prospect"] == {
        "exposed": True, "converted": True, "spend": 2.0, "revenue": 100.0
    }
    assert result["processed_events"] == 2


def test_two_aliases_are_separate_world_owners(tmp_path):
    source = """world W {
      import "std:marketing/lead_response.fnl" as North;
      import "std:marketing/lead_response.fnl" as South;
    }"""
    model = WorldExecutor(Parser.from_file(write_world(tmp_path, source)))
    events = [
        Event(0, "North.Impression", payload={
            "cpc": 1.0, "conversion_probability": 1.0, "order_value": 20.0
        }),
        Event(0, "South.Impression", payload={
            "cpc": 4.0, "conversion_probability": 0.0, "order_value": 50.0
        }),
    ]
    result = model.run(events, seed=5)
    assert result.state["North"] == {
        "exposed": True, "converted": True, "spend": 1.0, "revenue": 20.0
    }
    assert result.state["South"] == {
        "exposed": True, "converted": False, "spend": 4.0, "revenue": 0.0
    }
    assert len(result.processed) == 4


def test_strategy_file_cannot_masquerade_as_world_module(tmp_path):
    module = tmp_path / "legacy.fnl"
    module.write_text(
        'strategy Legacy { metadata { version = "one"; } }', encoding="utf-8"
    )
    with pytest.raises(ParserError, match="world declaration"):
        Parser.from_file(write_world(
            tmp_path, 'world W { import "legacy.fnl" as NotAllowed; }'
        ))
