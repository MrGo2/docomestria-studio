"""Default schema for v0.2.0 — a typical ES "DATOS DEL TITULAR" contract form.

Each field carries explicit ``labels`` so deterministic mode can pair them
against the words extracted from the PDF. AI mode uses the same schema; the
labels are simply unused when an LLM is plugged in.
"""

from __future__ import annotations


def build_default_schema():
    """Return the default Schema. Imported lazily to keep test imports cheap."""
    from docomestria.transform import Field, Schema
    from docomestria.transform import transformers as tr

    return Schema(
        {
            "fecha_contrato": Field(tr.date_es_long, labels=("Fecha",)),
            "datos_titular.apellidos": Field(
                tr.regex(r"^[A-ZÀ-Ú ]+$"), labels=("Apellidos",)
            ),
            "datos_titular.nombre": Field(
                tr.regex(r"^[A-ZÀ-Ú ]+$"), labels=("Nombre",)
            ),
            "datos_titular.nacionalidad": Field(
                tr.regex(r"^[A-ZÀ-Ú ]+$"), labels=("Nacionalidad",)
            ),
            "datos_titular.domicilio": Field(
                tr.regex(r".+"), labels=("Domicilio",)
            ),
            "datos_titular.numero": Field(
                tr.integer, labels=("Nº", "Numero")
            ),
            "datos_titular.piso": Field(tr.integer, labels=("Piso",)),
            "datos_titular.puerta": Field(tr.regex(r".+"), labels=("Puerta",)),
            "datos_titular.nif": Field(tr.nif_es, labels=("NIF", "DNI")),
            "datos_titular.poblacion": Field(
                tr.regex(r"^[A-ZÀ-Ú ]+$"), labels=("Población",)
            ),
            "datos_titular.cp": Field(
                tr.postal_code_es, labels=("C.P.", "CP", "Codigo postal")
            ),
            "datos_titular.provincia": Field(
                tr.regex(r"^[A-ZÀ-Ú ]+$"), labels=("Provincia",)
            ),
            "datos_titular.telefono_fijo": Field(
                tr.phone_es, labels=("Teléfono fijo", "Telefono fijo")
            ),
            "datos_titular.telefono_movil": Field(
                tr.phone_es, labels=("Teléfono móvil", "Movil", "Móvil")
            ),
            "datos_titular.email": Field(
                tr.email, labels=("Correo electrónico", "Email", "Correo")
            ),
            "datos_titular.fecha_nacimiento": Field(
                tr.date_es_short,
                labels=("Fecha de nacimiento", "F. nacimiento"),
            ),
            "datos_titular.vivienda": Field(
                tr.checkbox_choice(["propia", "alquiler", "padres", "otros"]),
                labels=("Vivienda",),
            ),
            "datos_titular.sexo": Field(
                tr.checkbox_binary("V", "H"), labels=("Sexo",)
            ),
            "datos_titular.estado_civil": Field(
                tr.checkbox_choice(
                    ["casado/a", "soltero/a", "separado/a", "otros"]
                ),
                labels=("Estado civil",),
            ),
            "datos_titular.personas_a_cargo": Field(
                tr.integer, labels=("Personas a su cargo",)
            ),
        }
    )


__all__ = ["build_default_schema"]
