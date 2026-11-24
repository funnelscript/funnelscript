"""Tests verifying FunnelScript import resolution via .fpm/resolution-map.json bridge."""

import json
from pathlib import Path
import pytest

from funnelscript.parser import Parser, ParserError
from funnelscript.compiler.world_ast import WorldAST


def test_resolve_package_import_via_fpm_map(tmp_path: Path):
    project_root = tmp_path / "my_project"
    project_root.mkdir()

    # Create dummy package outside project
    ext_pkg_dir = tmp_path / "installed_packages" / "ecommerce" / "d2c_scale"
    ext_pkg_dir.mkdir(parents=True)

    pkg_entry = ext_pkg_dir / "index.fnls"
    pkg_entry.write_text(
        'world d2c_scale {\n'
        '  entity Cart {\n'
        '    state active: float = 100.0;\n'
        '  }\n'
        '}\n',
        encoding="utf-8",
    )

    pkg_treasury = ext_pkg_dir / "treasury.fnls"
    pkg_treasury.write_text(
        'world treasury {\n'
        '  entity BankAccount {\n'
        '    state cash: float = 50000.0;\n'
        '  }\n'
        '}\n',
        encoding="utf-8",
    )

    # Generate .fpm/resolution-map.json
    fpm_dir = project_root / ".fpm"
    fpm_dir.mkdir()
    res_map = {
        "schema_version": "1.0.0",
        "packages": {
            "ecommerce/d2c_scale": {
                "version": "0.1.0",
                "entry": str(pkg_entry.resolve()),
                "integrity": "sha256-dummy",
                "modules": {
                    "index": str(pkg_entry.resolve()),
                    "treasury": str(pkg_treasury.resolve()),
                },
            }
        },
    }
    (fpm_dir / "resolution-map.json").write_text(json.dumps(res_map), encoding="utf-8")

    # Write consumer strategy source file importing the package with 'as' syntax
    consumer_fnl = project_root / "main.fnls"
    consumer_fnl.write_text(
        'world ConsumerStrategy {\n'
        '  import "ecommerce/d2c_scale" as CartModule;\n'
        '  import "ecommerce/d2c_scale/treasury" as TreasuryModule;\n'
        '}\n',
        encoding="utf-8",
    )

    ast = Parser.from_file(consumer_fnl)
    assert isinstance(ast, WorldAST)
    assert ast.name == "ConsumerStrategy"

    decl_names = [d.name for d in ast.declarations]
    assert "CartModule" in decl_names
    assert "TreasuryModule" in decl_names


def test_missing_package_in_resolution_map(tmp_path: Path):
    project_root = tmp_path / "proj"
    project_root.mkdir()
    fpm_dir = project_root / ".fpm"
    fpm_dir.mkdir()
    (fpm_dir / "resolution-map.json").write_text(
        json.dumps({"schema_version": "1.0.0", "packages": {}}),
        encoding="utf-8",
    )

    source_fnl = project_root / "test.fnls"
    source_fnl.write_text(
        'world Test {\n'
        '  import "nonexistent/pkg" as NonExistent;\n'
        '}\n',
        encoding="utf-8",
    )

    with pytest.raises(ParserError) as exc_info:
        Parser.from_file(source_fnl)
    assert "World module not found" in str(exc_info.value)
