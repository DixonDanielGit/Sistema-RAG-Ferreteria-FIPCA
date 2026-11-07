"""Esquemas del visor de auditoria (RF-05.2)."""

from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel, ConfigDict


class EventoBitacora(BaseModel):
    """Registro inmutable de una accion auditada."""

    model_config = ConfigDict(extra="ignore")

    id_bitacora: int
    id_usuario: int | None = None
    nombre_usuario: str | None = None
    fecha: date
    hora: time
    accion: str
    ip: str | None = None
    modulo: str | None = None
