from __future__ import annotations

import pytest

from app.integrations.mapper import apply_transformation_rule, map_fields


@pytest.mark.parametrize(
    ("rule", "value", "expected"),
    [
        ("trim", "  abc  ", "abc"),
        ("upper", "abc", "ABC"),
        ("lower", "ABC", "abc"),
        ("remover_mascara", "12.345-678", "12345678"),
        ("limpar_cnpj", "12.345.678/0001-90", "12345678000190"),
        ("limpar_cpf", "123.456.789-10", "12345678910"),
        ("converter_decimal", "10,5", 10.5),
        ("converter_data_iso", "2026-06-22T12:30:00", "2026-06-22T12:30:00"),
        ("valor_padrao", "manual", "manual"),
    ],
)
def test_apply_transformation_rule(rule: str, value: object, expected: object) -> None:
    assert apply_transformation_rule(value, rule) == expected


def test_map_fields_uses_default_value_for_missing_source_field() -> None:
    result = map_fields(
        {},
        [
            {
                "source_field": "name",
                "target_field": "customer_name",
                "transformation_rule": "trim",
                "default_value": "  Preferenza  ",
                "required": True,
            }
        ],
    )

    assert result["customer_name"] == "Preferenza"
