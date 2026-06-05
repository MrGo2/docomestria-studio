"""Default schema for v0.1.0 — a typical ES contract form.

In v0.2.0 this will be user-configurable; for now it ships hardcoded so the
viewer always has something to extract.
"""

from __future__ import annotations


def build_default_schema():
    """Return the default Schema. Imported lazily to keep test imports cheap."""
    from docomestria.transform import Field, Schema
    from docomestria.transform import transformers as tr

    return Schema(
        {
            "fecha_contrato": Field(tr.date_es_long),
            "datos_titular.apellidos": Field(tr.regex(r"^[A-ZÀ-Ú ]+$")),
            "datos_titular.nombre": Field(tr.regex(r"^[A-ZÀ-Ú ]+$")),
            "datos_titular.nif": Field(tr.nif_es),
            "datos_titular.fecha_nacimiento": Field(tr.date_es_short),
            "datos_titular.telefono_movil": Field(tr.phone_es),
            "datos_titular.email": Field(tr.email),
            "datos_titular.cp": Field(tr.postal_code_es),
            "datos_titular.vivienda": Field(
                tr.checkbox_choice(["propia", "alquiler", "padres", "otros"])
            ),
            "datos_titular.sexo": Field(tr.checkbox_binary("V", "H")),
        }
    )


__all__ = ["build_default_schema"]
